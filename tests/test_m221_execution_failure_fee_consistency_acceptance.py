import sqlite3
from pathlib import Path

import pytest

from market_intelligence.storage import Storage


# =====================================================================
# M2.21 — FAILURE FEE STATE CONSISTENCY ACCEPTANCE CONTRACT
#
# Contract:
#
# A rejected or failed execution must never charge or persist an
# execution fee.
#
# Failure must preserve the pre-execution financial state:
#
#   - cash must not change
#   - position must not change
#   - no durable fee-bearing order may be created
#   - persistence failure must roll back the complete execution state
#
# Production source is intentionally not modified by this test.
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
        kwargs["email"] = f"{login}@m221.local"

    if "password_hash" in parameters:
        kwargs["password_hash"] = "m221-test-password-hash"

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

    raise AssertionError("Unable to determine M2.21 test user id")


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


def _assert_failure_state_unchanged(
    before,
    after,
    before_orders,
    after_orders,
):
    assert float(after["cash"]) == pytest.approx(
        float(before["cash"])
    )

    assert after["positions"] == before["positions"]

    assert len(after_orders) == len(before_orders)

    # No new durable fee-bearing execution may exist.
    assert [
        row for row in after_orders
        if float(row["fee"]) != 0.0
    ] == [
        row for row in before_orders
        if float(row["fee"]) != 0.0
    ]


def test_m221_insufficient_cash_never_persists_or_charges_fee(
    tmp_path: Path,
):
    storage = _storage(tmp_path, "m221_cash")

    storage.reset_paper(100.0)

    before = _snapshot(storage)
    before_orders = _order_rows(storage)

    with pytest.raises(
        ValueError,
        match="Insufficient paper cash",
    ):
        storage.execute_paper_order(
            symbol="AAPL",
            market="US",
            side="BUY",
            qty=10.0,
            price=20.0,
            fee_bps=15.0,
            idempotency_key="m221-insufficient-cash",
        )

    after = _snapshot(storage)
    after_orders = _order_rows(storage)

    _assert_failure_state_unchanged(
        before,
        after,
        before_orders,
        after_orders,
    )


def test_m221_insufficient_position_never_persists_or_charges_fee(
    tmp_path: Path,
):
    storage = _storage(tmp_path, "m221_position")

    before = _snapshot(storage)
    before_orders = _order_rows(storage)

    with pytest.raises(
        ValueError,
        match="Insufficient paper position",
    ):
        storage.execute_paper_order(
            symbol="AAPL",
            market="US",
            side="SELL",
            qty=10.0,
            price=100.0,
            fee_bps=15.0,
            idempotency_key="m221-insufficient-position",
        )

    after = _snapshot(storage)
    after_orders = _order_rows(storage)

    _assert_failure_state_unchanged(
        before,
        after,
        before_orders,
        after_orders,
    )

    assert _position_qty(
        after,
        "AAPL",
        "US",
    ) == pytest.approx(0.0)


@pytest.mark.parametrize(
    ("qty", "price"),
    [
        (0.0, 100.0),
        (-1.0, 100.0),
        (1.0, 0.0),
        (1.0, -1.0),
    ],
)
def test_m221_invalid_order_never_persists_or_charges_fee(
    tmp_path: Path,
    qty,
    price,
):
    storage = _storage(
        tmp_path,
        f"m221_invalid_{abs(hash((qty, price)))}",
    )

    before = _snapshot(storage)
    before_orders = _order_rows(storage)

    with pytest.raises(ValueError):
        storage.execute_paper_order(
            symbol="AAPL",
            market="US",
            side="BUY",
            qty=qty,
            price=price,
            fee_bps=15.0,
            idempotency_key=f"m221-invalid-{qty}-{price}",
        )

    after = _snapshot(storage)
    after_orders = _order_rows(storage)

    _assert_failure_state_unchanged(
        before,
        after,
        before_orders,
        after_orders,
    )


def test_m221_persistence_failure_rolls_back_fee_state(
    tmp_path: Path,
):
    storage = _storage(tmp_path, "m221_persistence")

    before = _snapshot(storage)
    before_orders = _order_rows(storage)

    # Force failure at durable order persistence after execution
    # state mutation has begun. SQLite transaction semantics must
    # roll back cash, position and fee-bearing order together.
    with storage.connect() as con:
        con.execute(
            """
            CREATE TRIGGER m221_force_order_failure
            BEFORE INSERT ON paper_orders_v2
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'm221 forced order persistence failure'
                );
            END;
            """
        )

    with pytest.raises(
        sqlite3.DatabaseError,
        match="m221 forced order persistence failure",
    ):
        storage.execute_paper_order(
            symbol="AAPL",
            market="US",
            side="BUY",
            qty=2.0,
            price=100.0,
            fee_bps=15.0,
            idempotency_key="m221-persistence-failure",
        )

    after = _snapshot(storage)
    after_orders = _order_rows(storage)

    _assert_failure_state_unchanged(
        before,
        after,
        before_orders,
        after_orders,
    )
