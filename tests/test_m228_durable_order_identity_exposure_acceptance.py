"""
M2.28 durable-order identity exposure acceptance contract.

A successful paper execution must expose the durable order identity
through the public execution result.

Contract:

- successful execution returns FILLED
- public result exposes order_id
- order_id is a positive integer
- order_id identifies the exact durable order created by execution
- replay with the same idempotency key returns the same order_id
- replay does not create another durable order
- idempotency_key remains private
"""

from pathlib import Path

from market_intelligence.storage import Storage


def _make_storage(db_path: Path) -> Storage:
    bootstrap = Storage(str(db_path))

    login = "m228-user"

    result = bootstrap.register_user(
        username=login,
        email=f"{login}@example.com",
        password_hash="m228-test-password-hash",
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
                "M2.28 fixture could not resolve integer user_id"
            )

    storage = Storage(
        str(db_path),
        user_id=user_id,
    )

    storage.reset_paper(100_000.0)

    return storage


def _order_ids(storage: Storage) -> list[int]:
    return [
        int(order["id"])
        for order in storage.paper_snapshot()["orders"]
    ]


def test_m228_execution_exposes_exact_durable_order_identity(
    tmp_path: Path,
):
    storage = _make_storage(tmp_path / "m228.db")

    before_ids = _order_ids(storage)

    idempotency_key = "m228-durable-order-identity"

    first = storage.execute_paper_order(
        symbol="AAPL",
        market="US",
        side="BUY",
        qty=1.0,
        price=100.0,
        idempotency_key=idempotency_key,
    )

    assert first["status"] == "FILLED"

    # M2.28 public identity contract.
    assert "order_id" in first

    first_order_id = int(first["order_id"])
    assert first_order_id > 0

    # idempotency_key remains persistence metadata and must not become
    # part of the public execution result.
    assert "idempotency_key" not in first

    after_first_ids = _order_ids(storage)

    new_ids = set(after_first_ids) - set(before_ids)

    # The first execution must create exactly one durable order.
    assert len(new_ids) == 1

    durable_order_id = next(iter(new_ids))

    # The public identity must point to the exact durable record.
    assert first_order_id == durable_order_id

    durable_orders = storage.paper_snapshot()["orders"]

    matching = [
        order
        for order in durable_orders
        if int(order["id"]) == first_order_id
    ]

    assert len(matching) == 1

    durable = matching[0]

    # Identity linkage must not weaken the existing semantic contract.
    assert durable["symbol"] == first["symbol"]
    assert durable["market"] == first["market"]
    assert durable["side"] == first["side"]
    assert durable["status"] == first["status"]
    assert float(durable["qty"]) == float(first["qty"])
    assert float(durable["price"]) == float(first["price"])
    assert float(durable["fee"]) == float(first["fee"])

    replay = storage.execute_paper_order(
        symbol="AAPL",
        market="US",
        side="BUY",
        qty=1.0,
        price=100.0,
        idempotency_key=idempotency_key,
    )

    assert replay["status"] == "FILLED"

    # Replay must expose the same durable identity.
    assert "order_id" in replay
    assert int(replay["order_id"]) == first_order_id

    assert "idempotency_key" not in replay

    after_replay_ids = _order_ids(storage)

    # Replay must not create a second durable order.
    assert after_replay_ids == after_first_ids