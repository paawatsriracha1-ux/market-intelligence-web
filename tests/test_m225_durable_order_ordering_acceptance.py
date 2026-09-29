"""
M2.25 durable-order ordering acceptance contract.

The public paper snapshot must expose persisted paper orders
newest-first according to durable integer order id.

This contract intentionally verifies ordering through the public
paper_snapshot() surface rather than inspecting implementation SQL.
"""

from pathlib import Path

from market_intelligence.storage import Storage


def _make_storage(db_path: Path) -> Storage:
    bootstrap = Storage(str(db_path))

    login = "m225-user"

    result = bootstrap.register_user(
        username=login,
        email=f"{login}@example.com",
        password_hash="m225-test-password-hash",
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
                "M2.25 fixture could not resolve integer user_id"
            )

    storage = Storage(
        str(db_path),
        user_id=user_id,
    )

    storage.reset_paper(100_000.0)

    return storage


def test_m225_paper_snapshot_exposes_durable_orders_newest_first(
    tmp_path: Path,
):
    storage = _make_storage(tmp_path / "m225.db")

    before = storage.paper_snapshot()
    before_ids = {
        int(order["id"])
        for order in before["orders"]
    }

    first = storage.execute_paper_order(
        symbol="AAPL",
        market="US",
        side="BUY",
        qty=1.0,
        price=100.0,
    )

    assert first["status"] == "FILLED"

    after_first = storage.paper_snapshot()
    after_first_ids = [
        int(order["id"])
        for order in after_first["orders"]
    ]

    first_new_ids = (
        set(after_first_ids) - before_ids
    )

    assert len(first_new_ids) == 1
    first_id = next(iter(first_new_ids))

    second = storage.execute_paper_order(
        symbol="MSFT",
        market="US",
        side="BUY",
        qty=1.0,
        price=120.0,
    )

    assert second["status"] == "FILLED"

    snapshot = storage.paper_snapshot()
    orders = snapshot["orders"]

    ids = [
        int(order["id"])
        for order in orders
    ]

    second_new_ids = (
        set(ids) - set(after_first_ids)
    )

    assert len(second_new_ids) == 1
    second_id = next(iter(second_new_ids))

    # The second successful execution is persisted later and therefore
    # receives the newer durable order id.
    assert second_id > first_id

    # Both executions must be observable through the public durable
    # snapshot surface.
    assert first_id in ids
    assert second_id in ids

    first_index = ids.index(first_id)
    second_index = ids.index(second_id)

    # M2.25 contract:
    # the newer durable order must appear before the older durable order.
    assert second_index < first_index

    # Lock the public snapshot ordering itself, not merely the relative
    # position of these two executions.
    assert ids == sorted(ids, reverse=True)
