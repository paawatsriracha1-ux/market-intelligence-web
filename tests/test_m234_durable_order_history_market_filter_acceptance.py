from __future__ import annotations

import sqlite3
from pathlib import Path

from market_intelligence.storage import Storage


def _create_user(bootstrap: Storage, login: str) -> int:
    result = bootstrap.register_user(
        username=login,
        email=f"{login}@example.com",
        password_hash="m233-test-password-hash",
    )

    if isinstance(result, dict) and "user_id" in result:
        return int(result["user_id"])

    if isinstance(result, int):
        return int(result)

    user = bootstrap.get_user_by_login(login)

    assert user is not None

    if "id" in user:
        return int(user["id"])

    if "user_id" in user:
        return int(user["user_id"])

    raise AssertionError(
        "M2.33 fixture could not resolve integer user_id"
    )


def _scoped_storage(
    db_path: Path,
    user_id: int | None,
) -> Storage:
    storage = Storage(str(db_path))

    if user_id is not None:
        storage.user_id = user_id

    return storage


def _execute(
    storage: Storage,
    *,
    symbol: str,
    market: str,
    side: str,
    key: str,
    qty: float = 1.0,
    price: float = 10.0,
) -> dict:
    return storage.execute_paper_order(
        symbol=symbol,
        market=market,
        side=side,
        qty=qty,
        price=price,
        idempotency_key=key,
    )


def _durable_rows(
    db_path: Path,
    user_id: int,
) -> list[dict]:
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row

        rows = conn.execute(
            """
            SELECT
                id,
                user_id,
                symbol,
                market,
                side,
                qty,
                price,
                gross,
                fee,
                status,
                idempotency_key,
                created_at
            FROM paper_orders_v2
            WHERE user_id = ?
            ORDER BY id DESC
            """,
            (user_id,),
        ).fetchall()

    return [dict(row) for row in rows]


def _ids(rows: list[dict]) -> list[int]:
    return [int(row["id"]) for row in rows]


def _assert_public_shape(rows: list[dict]) -> None:
    for row in rows:
        assert "idempotency_key" not in row


def test_m234_durable_order_history_market_filter_contract(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "m234.sqlite3"

    bootstrap = Storage(str(db_path))

    owner_id = _create_user(bootstrap, "m234-owner")
    other_id = _create_user(bootstrap, "m234-other")

    owner = _scoped_storage(db_path, owner_id)
    other = _scoped_storage(db_path, other_id)
    unscoped = _scoped_storage(db_path, None)

    empty_id = _create_user(bootstrap, "m234-empty")
    empty = _scoped_storage(db_path, empty_id)

    # ------------------------------------------------------
    # Public execution fixtures only.
    #
    # BUY precedes SELL for each symbol + market position.
    # US and TH positions are intentionally independent.
    # ------------------------------------------------------

    us_aapl_buy = _execute(
        owner,
        symbol="AAPL",
        market="US",
        side="BUY",
        key="m234-owner-aapl-us-buy",
        qty=3.0,
    )

    us_aapl_sell = _execute(
        owner,
        symbol="AAPL",
        market="US",
        side="SELL",
        key="m234-owner-aapl-us-sell",
        qty=1.0,
    )

    th_aapl_buy = _execute(
        owner,
        symbol="AAPL",
        market="TH",
        side="BUY",
        key="m234-owner-aapl-th-buy",
        qty=3.0,
    )

    th_aapl_sell = _execute(
        owner,
        symbol="AAPL",
        market="TH",
        side="SELL",
        key="m234-owner-aapl-th-sell",
        qty=1.0,
    )

    us_msft_buy = _execute(
        owner,
        symbol="MSFT",
        market="US",
        side="BUY",
        key="m234-owner-msft-us-buy",
    )

    th_msft_buy = _execute(
        owner,
        symbol="MSFT",
        market="TH",
        side="BUY",
        key="m234-owner-msft-th-buy",
    )

    other_us = _execute(
        other,
        symbol="AAPL",
        market="US",
        side="BUY",
        key="m234-other-aapl-us-buy",
    )

    other_th = _execute(
        other,
        symbol="AAPL",
        market="TH",
        side="BUY",
        key="m234-other-aapl-th-buy",
    )

    # Fixture sanity: executions must create durable orders.
    owner_durable = _durable_rows(db_path, owner_id)
    other_durable = _durable_rows(db_path, other_id)

    assert len(owner_durable) == 6
    assert len(other_durable) == 2

    owner_ids = _ids(owner_durable)
    other_ids = _ids(other_durable)

    assert owner_ids == sorted(owner_ids, reverse=True)
    assert other_ids == sorted(other_ids, reverse=True)

    assert int(us_aapl_buy["order_id"]) in owner_ids
    assert int(us_aapl_sell["order_id"]) in owner_ids
    assert int(th_aapl_buy["order_id"]) in owner_ids
    assert int(th_aapl_sell["order_id"]) in owner_ids
    assert int(us_msft_buy["order_id"]) in owner_ids
    assert int(th_msft_buy["order_id"]) in owner_ids
    assert int(other_us["order_id"]) in other_ids
    assert int(other_th["order_id"]) in other_ids

    # ------------------------------------------------------
    # Existing contracts remain compatible.
    # ------------------------------------------------------

    assert unscoped.list_paper_orders() == []
    assert empty.list_paper_orders() == []

    unfiltered = owner.list_paper_orders()

    assert len(unfiltered) == 6
    assert _ids(unfiltered) == owner_ids

    symbol_only = owner.list_paper_orders(symbol="AAPL")
    assert symbol_only
    assert all(row["symbol"] == "AAPL" for row in symbol_only)

    side_only = owner.list_paper_orders(side="BUY")
    assert side_only
    assert all(row["side"] == "BUY" for row in side_only)

    # ------------------------------------------------------
    # M2.34 market=None / blank semantics.
    #
    # EXPECTED RED begins here on frozen baseline c4df95a:
    # list_paper_orders() does not yet accept market=.
    # ------------------------------------------------------

    assert owner.list_paper_orders(market=None) == unfiltered
    assert owner.list_paper_orders(market="") == unfiltered
    assert owner.list_paper_orders(market="   ") == unfiltered

    # ------------------------------------------------------
    # Market filtering + normalization.
    # ------------------------------------------------------

    us_rows = owner.list_paper_orders(market="US")
    th_rows = owner.list_paper_orders(market="TH")

    assert us_rows
    assert th_rows

    assert all(row["market"] == "US" for row in us_rows)
    assert all(row["market"] == "TH" for row in th_rows)

    assert owner.list_paper_orders(market="us") == us_rows
    assert owner.list_paper_orders(market="  us  ") == us_rows

    assert owner.list_paper_orders(market="th") == th_rows
    assert owner.list_paper_orders(market="  th  ") == th_rows

    assert owner.list_paper_orders(market="NO-SUCH-MARKET") == []

    # ------------------------------------------------------
    # AND composition.
    # ------------------------------------------------------

    symbol_market = owner.list_paper_orders(
        symbol="AAPL",
        market="US",
    )

    assert symbol_market
    assert all(
        row["symbol"] == "AAPL"
        and row["market"] == "US"
        for row in symbol_market
    )

    side_market = owner.list_paper_orders(
        side="SELL",
        market="TH",
    )

    assert side_market
    assert all(
        row["side"] == "SELL"
        and row["market"] == "TH"
        for row in side_market
    )

    triple = owner.list_paper_orders(
        symbol="AAPL",
        side="SELL",
        market="US",
    )

    assert triple
    assert all(
        row["symbol"] == "AAPL"
        and row["side"] == "SELL"
        and row["market"] == "US"
        for row in triple
    )

    # ------------------------------------------------------
    # Ownership isolation.
    # ------------------------------------------------------

    other_us_rows = other.list_paper_orders(market="US")
    other_th_rows = other.list_paper_orders(market="TH")

    assert _ids(other_us_rows) == [int(other_us["order_id"])]
    assert _ids(other_th_rows) == [int(other_th["order_id"])]

    assert set(_ids(us_rows)).isdisjoint(other_ids)
    assert set(_ids(th_rows)).isdisjoint(other_ids)

    # ------------------------------------------------------
    # Durable newest-first + public privacy.
    # ------------------------------------------------------

    assert _ids(us_rows) == sorted(_ids(us_rows), reverse=True)
    assert _ids(th_rows) == sorted(_ids(th_rows), reverse=True)
    assert _ids(triple) == sorted(_ids(triple), reverse=True)

    _assert_public_shape(unfiltered)
    _assert_public_shape(us_rows)
    _assert_public_shape(th_rows)
    _assert_public_shape(triple)

    # Durable source contains private key internally while
    # public history deliberately omits it.
    assert all(
        row["idempotency_key"]
        for row in owner_durable
    )
