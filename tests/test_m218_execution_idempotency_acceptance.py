"""
M2.18 execution idempotency acceptance contract.

Contract:
- user identity follows the production INTEGER users.id contract
- same user + same idempotency key mutates execution state once
- repeated BUY returns the original execution result
- repeated SELL returns the original execution result
- different keys execute independently
- the same key may be used independently by different users
- empty keys are rejected
- legacy execution without a key remains supported
"""

from __future__ import annotations

from pathlib import Path

import pytest

from market_intelligence.storage import Storage


def _create_user(storage: Storage, login: str) -> int:
    with storage.connect() as con:
        cur = con.execute(
            """
            INSERT INTO users(
                username,
                email,
                password_hash,
                role,
                status
            )
            VALUES (?, ?, ?, 'user', 'active')
            """,
            (
                login,
                f"{login}@example.com",
                "m218-test-hash",
            ),
        )
        return int(cur.lastrowid)


def _scoped_storage(
    db_path: Path,
    login: str,
    cash: float = 100_000.0,
) -> Storage:
    root = Storage(str(db_path))
    user_id = _create_user(root, login)

    scoped = Storage(
        str(db_path),
        user_id=user_id,
    )
    scoped.reset_paper(cash)

    return scoped


def _cash(storage: Storage) -> float:
    return float(storage.paper_snapshot()["cash"])


def _positions(storage: Storage):
    return storage.paper_snapshot()["positions"]


def _orders(storage: Storage):
    return storage.paper_snapshot()["orders"]


def _position(
    storage: Storage,
    symbol: str,
    market: str,
):
    for row in _positions(storage):
        if (
            row["symbol"] == symbol.upper()
            and row["market"] == market.upper()
        ):
            return row
    return None


def _order_count(storage: Storage) -> int:
    return len(_orders(storage))


def test_m218_same_buy_key_executes_once(tmp_path: Path):
    storage = _scoped_storage(
        tmp_path / "buy_once.sqlite3",
        "m218_buy_once",
    )

    before_cash = _cash(storage)

    first = storage.execute_paper_order(
        symbol="AAPL",
        market="US",
        side="BUY",
        qty=10.0,
        price=100.0,
        idempotency_key="buy-001",
    )

    after_first_cash = _cash(storage)
    after_first_orders = _order_count(storage)

    second = storage.execute_paper_order(
        symbol="AAPL",
        market="US",
        side="BUY",
        qty=10.0,
        price=100.0,
        idempotency_key="buy-001",
    )

    after_second_cash = _cash(storage)
    position = _position(storage, "AAPL", "US")

    assert first == second
    assert after_first_cash < before_cash
    assert after_second_cash == pytest.approx(after_first_cash)
    assert _order_count(storage) == after_first_orders == 1

    assert position is not None
    assert float(position["qty"]) == pytest.approx(10.0)


def test_m218_same_sell_key_executes_once(tmp_path: Path):
    storage = _scoped_storage(
        tmp_path / "sell_once.sqlite3",
        "m218_sell_once",
    )

    storage.execute_paper_order(
        symbol="AAPL",
        market="US",
        side="BUY",
        qty=10.0,
        price=100.0,
    )

    before_sell_cash = _cash(storage)
    before_orders = _order_count(storage)

    first = storage.execute_paper_order(
        symbol="AAPL",
        market="US",
        side="SELL",
        qty=4.0,
        price=110.0,
        idempotency_key="sell-001",
    )

    after_first_cash = _cash(storage)
    after_first_orders = _order_count(storage)

    second = storage.execute_paper_order(
        symbol="AAPL",
        market="US",
        side="SELL",
        qty=4.0,
        price=110.0,
        idempotency_key="sell-001",
    )

    position = _position(storage, "AAPL", "US")

    assert first == second
    assert after_first_cash > before_sell_cash
    assert _cash(storage) == pytest.approx(after_first_cash)
    assert after_first_orders == before_orders + 1
    assert _order_count(storage) == after_first_orders

    assert position is not None
    assert float(position["qty"]) == pytest.approx(6.0)


def test_m218_retry_returns_original_result(tmp_path: Path):
    storage = _scoped_storage(
        tmp_path / "original_result.sqlite3",
        "m218_original_result",
    )

    first = storage.execute_paper_order(
        symbol="MSFT",
        market="US",
        side="BUY",
        qty=3.0,
        price=200.0,
        fee_bps=15.0,
        idempotency_key="original-result-001",
    )

    second = storage.execute_paper_order(
        symbol="MSFT",
        market="US",
        side="BUY",
        qty=999.0,
        price=999.0,
        fee_bps=999.0,
        idempotency_key="original-result-001",
    )

    assert second == first
    assert second["qty"] == pytest.approx(3.0)
    assert second["price"] == pytest.approx(200.0)
    assert _order_count(storage) == 1

    position = _position(storage, "MSFT", "US")
    assert position is not None
    assert float(position["qty"]) == pytest.approx(3.0)


def test_m218_different_keys_execute_independently(tmp_path: Path):
    storage = _scoped_storage(
        tmp_path / "different_keys.sqlite3",
        "m218_different_keys",
    )

    storage.execute_paper_order(
        symbol="AAPL",
        market="US",
        side="BUY",
        qty=2.0,
        price=100.0,
        idempotency_key="key-A",
    )

    storage.execute_paper_order(
        symbol="AAPL",
        market="US",
        side="BUY",
        qty=3.0,
        price=100.0,
        idempotency_key="key-B",
    )

    position = _position(storage, "AAPL", "US")

    assert _order_count(storage) == 2
    assert position is not None
    assert float(position["qty"]) == pytest.approx(5.0)


def test_m218_same_key_is_scoped_per_user(tmp_path: Path):
    db_path = tmp_path / "user_scope.sqlite3"

    user_a = _scoped_storage(
        db_path,
        "m218_user_a",
    )

    user_b = _scoped_storage(
        db_path,
        "m218_user_b",
    )

    result_a = user_a.execute_paper_order(
        symbol="AAPL",
        market="US",
        side="BUY",
        qty=1.0,
        price=100.0,
        idempotency_key="shared-key",
    )

    result_b = user_b.execute_paper_order(
        symbol="MSFT",
        market="US",
        side="BUY",
        qty=2.0,
        price=200.0,
        idempotency_key="shared-key",
    )

    assert result_a["status"] == "FILLED"
    assert result_b["status"] == "FILLED"

    assert _order_count(user_a) == 1
    assert _order_count(user_b) == 1

    assert _position(user_a, "AAPL", "US") is not None
    assert _position(user_b, "MSFT", "US") is not None


@pytest.mark.parametrize(
    "bad_key",
    [
        "",
        "   ",
        "\t",
        "\n",
    ],
)
def test_m218_empty_idempotency_key_rejected(
    tmp_path: Path,
    bad_key: str,
):
    storage = _scoped_storage(
        tmp_path / f"bad_key_{repr(bad_key)}.sqlite3",
        "m218_bad_key_" + str(abs(hash(bad_key))),
    )

    before_cash = _cash(storage)

    with pytest.raises(
        ValueError,
        match="idempotency_key must not be empty",
    ):
        storage.execute_paper_order(
            symbol="AAPL",
            market="US",
            side="BUY",
            qty=1.0,
            price=100.0,
            idempotency_key=bad_key,
        )

    assert _cash(storage) == pytest.approx(before_cash)
    assert _order_count(storage) == 0
    assert _position(storage, "AAPL", "US") is None


def test_m218_none_key_preserves_legacy_behavior(tmp_path: Path):
    storage = _scoped_storage(
        tmp_path / "legacy_none.sqlite3",
        "m218_legacy_none",
    )

    storage.execute_paper_order(
        symbol="AAPL",
        market="US",
        side="BUY",
        qty=1.0,
        price=100.0,
    )

    storage.execute_paper_order(
        symbol="AAPL",
        market="US",
        side="BUY",
        qty=1.0,
        price=100.0,
    )

    position = _position(storage, "AAPL", "US")

    assert _order_count(storage) == 2
    assert position is not None
    assert float(position["qty"]) == pytest.approx(2.0)
