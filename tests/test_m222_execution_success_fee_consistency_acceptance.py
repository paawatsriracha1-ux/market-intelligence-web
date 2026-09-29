from pathlib import Path

import pytest

from market_intelligence.storage import Storage


# =====================================================================
# M2.22 — SUCCESS FEE STATE CONSISTENCY ACCEPTANCE CONTRACT
#
# Contract:
#
# A successful execution must apply its execution fee exactly once and
# persist a financial state consistent with the durable FILLED order.
#
# BUY:
#   cash delta = gross + fee
#
# SELL:
#   cash delta = gross - fee
#
# In both directions:
#   - position mutation must match executed quantity
#   - durable order gross must match qty * price
#   - durable order fee must match fee_bps exactly once
#   - durable order must be FILLED
# =====================================================================


def _create_user(storage: Storage, login: str) -> int:
    import inspect

    signature = inspect.signature(storage.register_user)
    parameters = signature.parameters

    kwargs = {}

    if "login" in parameters:
        kwargs["login"] = login

    if "username" in parameters:
        kwargs["username"] = login

    if "email" in parameters:
        kwargs["email"] = f"{login}@m222.local"

    if "password_hash" in parameters:
        kwargs["password_hash"] = "m222-test-password-hash"

    if "role" in parameters:
        kwargs["role"] = "user"

    if "status" in parameters:
        kwargs["status"] = "active"

    result = storage.register_user(**kwargs)

    if isinstance(result, int):
        return result

    if isinstance(result, dict):
        if "id" in result:
            return int(result["id"])
        if "user_id" in result:
            return int(result["user_id"])

    user = storage.get_user_by_login(login)

    assert user is not None

    if isinstance(user, dict):
        if "id" in user:
            return int(user["id"])
        if "user_id" in user:
            return int(user["user_id"])

    raise AssertionError("Unable to determine M2.22 test user id")


def _storage(tmp_path: Path, name: str) -> Storage:
    db_path = tmp_path / f"{name}.sqlite3"

    bootstrap = Storage(path=str(db_path))
    bootstrap.init_db()

    user_id = _create_user(bootstrap, name)

    storage = Storage(
        path=str(db_path),
        user_id=user_id,
    )

    storage.reset_paper(100000.0)

    return storage


def _snapshot(storage: Storage):
    return storage.paper_snapshot()


def _order_rows(storage: Storage):
    uid = storage._uid()

    with storage.connect() as con:
        return con.execute(
            """
            SELECT
                id,
                symbol,
                market,
                side,
                qty,
                price,
                gross,
                fee,
                status,
                idempotency_key
            FROM paper_orders_v2
            WHERE user_id = ?
            ORDER BY id
            """,
            (uid,),
        ).fetchall()


def _position_qty(snapshot, symbol, market):
    qty = 0.0

    for row in snapshot.get("positions", []):
        if (
            row.get("symbol") == symbol
            and row.get("market") == market
        ):
            qty += float(row.get("qty", 0.0))

    return qty


def _expected_fee(qty, price, fee_bps):
    gross = qty * price
    return gross * fee_bps / 10000.0


def test_m222_successful_buy_applies_fee_exactly_once(
    tmp_path: Path,
):
    storage = _storage(tmp_path, "m222_buy")

    symbol = "AAPL"
    market = "US"
    qty = 10.0
    price = 100.0
    fee_bps = 15.0

    gross = qty * price
    expected_fee = _expected_fee(qty, price, fee_bps)

    before = _snapshot(storage)
    before_orders = _order_rows(storage)

    storage.execute_paper_order(
        symbol=symbol,
        market=market,
        side="BUY",
        qty=qty,
        price=price,
        fee_bps=fee_bps,
        idempotency_key="m222-success-buy",
    )

    after = _snapshot(storage)
    after_orders = _order_rows(storage)

    assert float(after["cash"]) == pytest.approx(
        float(before["cash"]) - gross - expected_fee
    )

    assert _position_qty(
        after,
        symbol,
        market,
    ) == pytest.approx(
        _position_qty(before, symbol, market) + qty
    )

    assert len(after_orders) == len(before_orders) + 1

    order = after_orders[-1]

    assert order["symbol"] == symbol
    assert order["market"] == market
    assert order["side"] == "BUY"
    assert float(order["qty"]) == pytest.approx(qty)
    assert float(order["price"]) == pytest.approx(price)
    assert float(order["gross"]) == pytest.approx(gross)
    assert float(order["fee"]) == pytest.approx(expected_fee)
    assert order["status"] == "FILLED"
    assert order["idempotency_key"] == "m222-success-buy"


def test_m222_successful_sell_applies_fee_exactly_once(
    tmp_path: Path,
):
    storage = _storage(tmp_path, "m222_sell")

    symbol = "AAPL"
    market = "US"
    qty = 10.0
    price = 100.0
    fee_bps = 15.0

    gross = qty * price
    expected_fee = _expected_fee(qty, price, fee_bps)

    # Establish position first.
    storage.execute_paper_order(
        symbol=symbol,
        market=market,
        side="BUY",
        qty=qty,
        price=price,
        fee_bps=0.0,
        idempotency_key="m222-seed-position",
    )

    before = _snapshot(storage)
    before_orders = _order_rows(storage)

    storage.execute_paper_order(
        symbol=symbol,
        market=market,
        side="SELL",
        qty=qty,
        price=price,
        fee_bps=fee_bps,
        idempotency_key="m222-success-sell",
    )

    after = _snapshot(storage)
    after_orders = _order_rows(storage)

    assert float(after["cash"]) == pytest.approx(
        float(before["cash"]) + gross - expected_fee
    )

    assert _position_qty(
        after,
        symbol,
        market,
    ) == pytest.approx(
        _position_qty(before, symbol, market) - qty
    )

    assert len(after_orders) == len(before_orders) + 1

    order = after_orders[-1]

    assert order["symbol"] == symbol
    assert order["market"] == market
    assert order["side"] == "SELL"
    assert float(order["qty"]) == pytest.approx(qty)
    assert float(order["price"]) == pytest.approx(price)
    assert float(order["gross"]) == pytest.approx(gross)
    assert float(order["fee"]) == pytest.approx(expected_fee)
    assert order["status"] == "FILLED"
    assert order["idempotency_key"] == "m222-success-sell"
