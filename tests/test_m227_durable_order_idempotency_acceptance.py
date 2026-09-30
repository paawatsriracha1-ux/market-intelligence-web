"""
M2.27 durable-order idempotency acceptance contract.

A successful execution using a non-empty idempotency key creates one
durable paper order. Replaying the identical execution with the same key
must not create another durable order or mutate execution state again.

The contract is verified through the public paper_snapshot() surface.
"""

from pathlib import Path

import pytest

from market_intelligence.storage import Storage


def _make_storage(db_path: Path) -> Storage:
    bootstrap = Storage(str(db_path))

    login = "m227-user"

    result = bootstrap.register_user(
        username=login,
        email=f"{login}@example.com",
        password_hash="m227-test-password-hash",
    )

    if isinstance(result, dict) and "user_id" in result:
        user_id = int(result["user_id"])
    elif isinstance(result, int):
        user_id = int(result)
    else:
        user = bootstrap.get_user_by_login(login)

        assert user is not None

        if "id" in user:
            user_id = int(user["id"])
        elif "user_id" in user:
            user_id = int(user["user_id"])
        else:
            raise AssertionError(
                "M2.27 fixture could not resolve integer user_id"
            )

    storage = Storage(
        str(db_path),
        user_id=user_id,
    )

    storage.reset_paper(100_000.0)

    return storage


def _position(snapshot, symbol: str, market: str):
    for position in snapshot["positions"]:
        if (
            str(position.get("symbol", "")).upper() == symbol.upper()
            and str(position.get("market", "")).upper() == market.upper()
        ):
            return position

    return None


def test_m227_replay_does_not_duplicate_durable_order(
    tmp_path: Path,
):
    storage = _make_storage(tmp_path / "m227.db")

    before = storage.paper_snapshot()

    before_ids = {
        int(order["id"])
        for order in before["orders"]
    }

    first = storage.execute_paper_order(
        symbol="AAPL",
        market="US",
        side="BUY",
        qty=2.0,
        price=100.0,
        idempotency_key="m227-buy-001",
    )

    assert first["status"] == "FILLED"

    after_first = storage.paper_snapshot()

    after_first_ids = {
        int(order["id"])
        for order in after_first["orders"]
    }

    first_new_ids = after_first_ids - before_ids

    assert len(first_new_ids) == 1

    durable_id = next(iter(first_new_ids))

    assert durable_id in after_first_ids

    cash_after_first = float(after_first["cash"])

    position_after_first = _position(
        after_first,
        "AAPL",
        "US",
    )

    assert position_after_first is not None

    qty_after_first = float(position_after_first["qty"])

    replay = storage.execute_paper_order(
        symbol="AAPL",
        market="US",
        side="BUY",
        qty=2.0,
        price=100.0,
        idempotency_key="m227-buy-001",
    )

    assert replay["status"] == "FILLED"

    after_replay = storage.paper_snapshot()

    after_replay_ids = [
        int(order["id"])
        for order in after_replay["orders"]
    ]

    replay_new_ids = (
        set(after_replay_ids) - after_first_ids
    )

    # Replay must create zero additional durable orders.
    assert replay_new_ids == set()

    # The original durable execution remains visible exactly once.
    assert after_replay_ids.count(durable_id) == 1

    # Replay must not mutate execution state again.
    assert float(after_replay["cash"]) == pytest.approx(
        cash_after_first
    )

    position_after_replay = _position(
        after_replay,
        "AAPL",
        "US",
    )

    assert position_after_replay is not None
    assert float(position_after_replay["qty"]) == pytest.approx(
        qty_after_first
    )