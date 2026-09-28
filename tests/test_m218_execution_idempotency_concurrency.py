"""
M2.18 concurrent execution-idempotency acceptance contract.

Same user + same idempotency key + concurrent BUY requests
must produce exactly one durable execution-state mutation.

Acceptance test only.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

from market_intelligence.storage import Storage


def _create_user(storage: Storage, login: str) -> int:
    """
    Follow the same user-creation pattern already used by the
    passing M2.17 / M2.18 acceptance contracts.
    """
    with storage.connect() as con:
        cursor = con.execute(
            """
            INSERT INTO users(
                username,
                email,
                password_hash,
                role,
                status
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                login,
                f"{login}@example.com",
                "m218-concurrency-test-hash",
                "user",
                "active",
            ),
        )

        return int(cursor.lastrowid)


def test_m218_concurrent_same_buy_key_executes_once(
    tmp_path: Path,
):
    db_path = tmp_path / "m218_concurrent.sqlite3"

    root = Storage(str(db_path))

    user_id = _create_user(
        root,
        "m218_concurrent_user",
    )

    # Initialize account using the real user-scoped Storage contract.
    setup = Storage(
        str(db_path),
        user_id=user_id,
    )

    setup.reset_paper(10000.0)

    barrier = Barrier(2)

    def execute_once():
        storage = Storage(
            str(db_path),
            user_id=user_id,
        )

        barrier.wait(timeout=10)

        return storage.execute_paper_order(
            symbol="AAPL",
            market="US",
            side="BUY",
            qty=1,
            price=100,
            idempotency_key="concurrent-buy-001",
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        future_a = pool.submit(execute_once)
        future_b = pool.submit(execute_once)

        result_a = future_a.result(timeout=20)
        result_b = future_b.result(timeout=20)

    verify = Storage(
        str(db_path),
        user_id=user_id,
    )

    snapshot = verify.paper_snapshot()

    # M2.18 durable-execution oracle:
    # idempotency_key is persistence metadata and is intentionally not
    # part of the public paper_snapshot order surface. Verify the durable
    # execution directly against paper_orders_v2 instead.
    with verify.connect() as con:
        matching = con.execute(
            """SELECT id, symbol, market, side, qty, price, gross, fee,
                      status, idempotency_key
               FROM paper_orders_v2
               WHERE user_id=? AND idempotency_key=?""",
            (user_id, "concurrent-buy-001"),
        ).fetchall()

    assert len(matching) == 1, [dict(row) for row in matching]

    positions = snapshot.get("positions", [])

    aapl = [
        position
        for position in positions
        if str(position.get("symbol", "")).upper() == "AAPL"
        and str(position.get("market", "")).upper() == "US"
    ]

    assert len(aapl) == 1, aapl

    qty = (
        aapl[0].get("quantity")
        if "quantity" in aapl[0]
        else aapl[0].get("qty")
    )

    assert float(qty) == 1.0, aapl[0]

    # Both callers must receive an execution result.
    assert result_a is not None
    assert result_b is not None
