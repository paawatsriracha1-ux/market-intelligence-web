"""
M2.24 durable-order created_at acceptance contract.

A successful execution must:

- return FILLED
- persist exactly one new durable order
- expose that durable order through paper_snapshot()["orders"]
- persist the durable order as FILLED
- expose a non-null / non-empty created_at timestamp

This contract requires no production API expansion.
"""

from pathlib import Path

from market_intelligence.storage import Storage


def _make_storage(db_path: Path):
    bootstrap = Storage(str(db_path))

    login = "m224-user"

    result = bootstrap.register_user(
        username=login,
        email=f"{login}@example.com",
        password_hash="m224-test-password-hash",
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
                "M2.24 fixture could not resolve integer user_id"
            )

    storage = Storage(
        str(db_path),
        user_id=user_id,
    )

    storage.reset_paper(100_000.0)

    return storage


def test_m224_successful_execution_persists_created_at(
    tmp_path: Path,
):
    storage = _make_storage(
        tmp_path / "m224_created_at.db"
    )

    before = storage.paper_snapshot()

    before_orders = list(before["orders"])

    symbol = "MSFT"
    market = "US"
    side = "BUY"
    qty = 2.0
    price = 100.0

    result = storage.execute_paper_order(
        symbol=symbol,
        market=market,
        side=side,
        qty=qty,
        price=price,
    )

    assert result["status"] == "FILLED"

    after = storage.paper_snapshot()
    after_orders = list(after["orders"])

    # One successful execution must create exactly one
    # additional durable order.
    assert len(after_orders) == len(before_orders) + 1

    matching = [
        order
        for order in after_orders
        if order["symbol"] == symbol
        and order["market"] == market
        and order["side"] == side
        and float(order["qty"]) == qty
        and float(order["price"]) == price
        and order["status"] == "FILLED"
    ]

    # Exactly one durable FILLED order represents this execution.
    assert len(matching) == 1

    durable_order = matching[0]

    # M2.24 critical contract:
    # every successful durable execution must expose its
    # persistence timestamp through paper_snapshot().
    assert "created_at" in durable_order
    assert durable_order["created_at"] is not None
    assert str(durable_order["created_at"]).strip() != ""
