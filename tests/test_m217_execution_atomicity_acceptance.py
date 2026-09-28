"""
M2.17 execution atomicity / failure-integrity acceptance contract.

Frozen baseline entering milestone:
    2826e6c

Scope:
    - BUY failure after account mutation must rollback all execution state
    - SELL failure after account mutation must rollback all execution state
    - failed execution must not create orphan order history

This file is an acceptance contract.
Production implementation must not be modified during RED phase.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from market_intelligence.storage import Storage


def _create_user(storage: Storage, login: str) -> int:
    with storage.connect() as con:
        cur = con.execute(
            """
            INSERT INTO users(username, email, password_hash, role, status)
            VALUES (?, ?, ?, 'user', 'active')
            """,
            (
                login,
                f"{login}@example.com",
                "m217-test-hash",
            ),
        )
        return int(cur.lastrowid)


def _snapshot(storage: Storage):
    snap = storage.paper_snapshot()

    return {
        "cash": float(snap["cash"]),
        "positions": [
            (
                row["symbol"],
                row["market"],
                float(row["qty"]),
                float(row["avg_price"]),
            )
            for row in snap["positions"]
        ],
        "orders": [
            (
                row["symbol"],
                row["market"],
                row["side"],
                float(row["qty"]),
                float(row["price"]),
                row["status"],
            )
            for row in snap["orders"]
        ],
    }


@pytest.fixture
def storage(tmp_path: Path):
    db_path = tmp_path / "m217_atomicity.sqlite3"

    root = Storage(str(db_path))
    user_id = _create_user(root, "m217_atomicity_user")

    scoped = Storage(str(db_path), user_id=user_id)
    scoped.reset_paper(100_000.0)

    return scoped


def _install_order_insert_failure(storage: Storage):
    """
    Force the final paper_orders_v2 INSERT to fail inside SQLite.

    The trigger fires after earlier cash/position mutations have been
    attempted, making this a transaction-boundary acceptance test.
    """

    with storage.connect() as con:
        con.execute(
            """
            CREATE TRIGGER m217_fail_order_insert
            BEFORE INSERT ON paper_orders_v2
            BEGIN
                SELECT RAISE(ABORT, 'm217 forced order persistence failure');
            END;
            """
        )


def test_m217_failed_buy_rolls_back_entire_execution(storage: Storage):
    before = _snapshot(storage)

    _install_order_insert_failure(storage)

    with pytest.raises(
        sqlite3.DatabaseError,
        match="m217 forced order persistence failure",
    ):
        storage.execute_paper_order(
            symbol="AAPL",
            market="US",
            side="BUY",
            qty=10.0,
            price=100.0,
        )

    after = _snapshot(storage)

    assert after == before


def test_m217_failed_sell_rolls_back_entire_execution(storage: Storage):
    storage.execute_paper_order(
        symbol="AAPL",
        market="US",
        side="BUY",
        qty=10.0,
        price=100.0,
    )

    before = _snapshot(storage)

    _install_order_insert_failure(storage)

    with pytest.raises(
        sqlite3.DatabaseError,
        match="m217 forced order persistence failure",
    ):
        storage.execute_paper_order(
            symbol="AAPL",
            market="US",
            side="SELL",
            qty=4.0,
            price=110.0,
        )

    after = _snapshot(storage)

    assert after == before


def test_m217_successful_execution_persists_coherent_state(storage: Storage):
    before = _snapshot(storage)

    result = storage.execute_paper_order(
        symbol="MSFT",
        market="US",
        side="BUY",
        qty=5.0,
        price=200.0,
    )

    after = _snapshot(storage)

    assert result["status"] == "FILLED"
    assert after["cash"] < before["cash"]

    assert any(
        symbol == "MSFT"
        and market == "US"
        and qty == pytest.approx(5.0)
        for symbol, market, qty, _avg_price in after["positions"]
    )

    assert len(after["orders"]) == len(before["orders"]) + 1
