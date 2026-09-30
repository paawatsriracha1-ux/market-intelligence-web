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
    user_id: int,
) -> Storage:
    return Storage(
        str(db_path),
        user_id=user_id,
    )


def _execute(
    storage: Storage,
    symbol: str,
    side: str,
    key: str,
) -> dict:
    result = storage.execute_paper_order(
        symbol=symbol,
        market="US",
        side=side,
        qty=1.0,
        price=10.0,
        idempotency_key=key,
    )

    assert result is not None
    assert result["status"] == "FILLED"
    assert "order_id" in result

    return result


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


def _order_count(
    db_path: Path,
    user_id: int,
) -> int:
    with sqlite3.connect(str(db_path)) as conn:
        row = conn.execute(
            """
            SELECT COUNT(*)
            FROM paper_orders_v2
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

    assert row is not None
    return int(row[0])


def _public_equivalent(
    public_row: dict,
    durable_row: dict,
) -> None:
    fields = (
        "id",
        "symbol",
        "market",
        "side",
        "qty",
        "price",
        "gross",
        "fee",
        "status",
        "created_at",
    )

    for field in fields:
        assert public_row[field] == durable_row[field]

    assert "idempotency_key" not in public_row


def test_m233_durable_order_history_side_filter_contract(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "m233.sqlite3"

    bootstrap = Storage(str(db_path))

    owner_id = _create_user(
        bootstrap,
        "m233-owner",
    )
    other_id = _create_user(
        bootstrap,
        "m233-other",
    )

    owner = _scoped_storage(
        db_path,
        owner_id,
    )
    other = _scoped_storage(
        db_path,
        other_id,
    )

    # --------------------------------------------------------
    # OWNER FIXTURE
    #
    # BUY first establishes a valid position.
    # SELL then uses the normal public execution path.
    # --------------------------------------------------------

    owner_aapl_buy_1 = _execute(
        owner,
        "AAPL",
        "BUY",
        "m233-owner-aapl-buy-1",
    )

    owner_msft_buy = _execute(
        owner,
        "MSFT",
        "BUY",
        "m233-owner-msft-buy",
    )

    owner_aapl_sell = _execute(
        owner,
        "AAPL",
        "SELL",
        "m233-owner-aapl-sell",
    )

    owner_aapl_buy_2 = _execute(
        owner,
        "AAPL",
        "BUY",
        "m233-owner-aapl-buy-2",
    )

    # Other user has matching BUY/SELL values and must never
    # leak into owner's durable history.
    _execute(
        other,
        "AAPL",
        "BUY",
        "m233-other-aapl-buy",
    )

    other_aapl_sell = _execute(
        other,
        "AAPL",
        "SELL",
        "m233-other-aapl-sell",
    )

    durable_before = _durable_rows(
        db_path,
        owner_id,
    )
    count_before = _order_count(
        db_path,
        owner_id,
    )
    snapshot_before = owner.paper_snapshot()

    assert len(durable_before) == 4

    # --------------------------------------------------------
    # M2.31 / M2.32 COMPATIBILITY
    # --------------------------------------------------------

    unfiltered = owner.list_paper_orders()
    explicit_none = owner.list_paper_orders(side=None)
    symbol_only = owner.list_paper_orders(symbol="AAPL")

    assert unfiltered == explicit_none

    assert [row["id"] for row in unfiltered] == [
        row["id"] for row in durable_before
    ]

    assert all(
        row["symbol"] == "AAPL"
        for row in symbol_only
    )

    # --------------------------------------------------------
    # M2.33 SIDE FILTER
    # --------------------------------------------------------

    buy_history = owner.list_paper_orders(
        side="BUY",
    )
    sell_history = owner.list_paper_orders(
        side="SELL",
    )

    buy_normalized = owner.list_paper_orders(
        side=" buy ",
    )
    sell_normalized = owner.list_paper_orders(
        side=" sell ",
    )

    assert buy_history == buy_normalized
    assert sell_history == sell_normalized

    assert buy_history
    assert sell_history

    assert all(
        row["side"] == "BUY"
        for row in buy_history
    )

    assert all(
        row["side"] == "SELL"
        for row in sell_history
    )

    # Newest-first durable integer id ordering.
    buy_ids = [
        int(row["id"])
        for row in buy_history
    ]
    sell_ids = [
        int(row["id"])
        for row in sell_history
    ]

    assert buy_ids == sorted(
        buy_ids,
        reverse=True,
    )
    assert sell_ids == sorted(
        sell_ids,
        reverse=True,
    )

    # --------------------------------------------------------
    # SYMBOL + SIDE AND-COMPOSITION
    # --------------------------------------------------------

    aapl_buy = owner.list_paper_orders(
        symbol=" aapl ",
        side=" buy ",
    )

    aapl_sell = owner.list_paper_orders(
        symbol="AAPL",
        side="SELL",
    )

    assert aapl_buy
    assert aapl_sell

    assert all(
        row["symbol"] == "AAPL"
        and row["side"] == "BUY"
        for row in aapl_buy
    )

    assert all(
        row["symbol"] == "AAPL"
        and row["side"] == "SELL"
        for row in aapl_sell
    )

    assert [
        int(row["id"])
        for row in aapl_buy
    ] == sorted(
        [
            int(row["id"])
            for row in aapl_buy
        ],
        reverse=True,
    )

    assert [
        int(row["id"])
        for row in aapl_sell
    ] == sorted(
        [
            int(row["id"])
            for row in aapl_sell
        ],
        reverse=True,
    )

    # --------------------------------------------------------
    # NO-MATCH
    # --------------------------------------------------------

    assert owner.list_paper_orders(
        side="M2.33-NO-MATCH",
    ) == []

    # --------------------------------------------------------
    # DURABLE EQUIVALENCE / PRIVACY
    # --------------------------------------------------------

    durable_by_id = {
        int(row["id"]): row
        for row in durable_before
    }

    for public_row in unfiltered:
        order_id = int(public_row["id"])

        assert order_id in durable_by_id

        _public_equivalent(
            public_row,
            durable_by_id[order_id],
        )

    assert int(owner_aapl_buy_1["order_id"]) in {
        int(row["id"])
        for row in buy_history
    }

    assert int(owner_msft_buy["order_id"]) in {
        int(row["id"])
        for row in buy_history
    }

    assert int(owner_aapl_buy_2["order_id"]) in {
        int(row["id"])
        for row in buy_history
    }

    assert int(owner_aapl_sell["order_id"]) in {
        int(row["id"])
        for row in sell_history
    }

    # --------------------------------------------------------
    # OWNERSHIP BOUNDARY
    # --------------------------------------------------------

    owner_public_ids = {
        int(row["id"])
        for row in unfiltered
    }

    assert int(other_aapl_sell["order_id"]) not in owner_public_ids

    other_sell_history = other.list_paper_orders(
        side="SELL",
    )

    assert int(other_aapl_sell["order_id"]) in {
        int(row["id"])
        for row in other_sell_history
    }

    assert int(owner_aapl_sell["order_id"]) not in {
        int(row["id"])
        for row in other_sell_history
    }

    # --------------------------------------------------------
    # READ-ONLY GUARANTEE
    # --------------------------------------------------------

    durable_after = _durable_rows(
        db_path,
        owner_id,
    )
    count_after = _order_count(
        db_path,
        owner_id,
    )
    snapshot_after = owner.paper_snapshot()

    assert count_after == count_before
    assert durable_after == durable_before

    assert snapshot_after["cash"] == snapshot_before["cash"]
    assert snapshot_after["positions"] == snapshot_before["positions"]
    assert snapshot_after["orders"] == snapshot_before["orders"]

    # Existing snapshot retention remains untouched.
    assert len(snapshot_after["orders"]) <= 200
