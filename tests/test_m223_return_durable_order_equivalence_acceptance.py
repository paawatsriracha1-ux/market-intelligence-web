from pathlib import Path

import pytest

from market_intelligence.storage import Storage


def _create_user(storage: Storage, login: str) -> int:
    result = storage.register_user(
        username=login,
        email=f"{login}@example.com",
        password_hash="m223-test-password-hash",
    )

    if isinstance(result, int):
        return int(result)

    if isinstance(result, dict) and "user_id" in result:
        return int(result["user_id"])

    user = storage.get_user_by_login(login)

    if user is None:
        raise AssertionError("M2.23 fixture could not create test user")

    if isinstance(user, dict):
        if "id" in user:
            return int(user["id"])
        if "user_id" in user:
            return int(user["user_id"])

    raise AssertionError("M2.23 fixture could not resolve integer user_id")


def _make_storage(db_path: Path, login: str):
    bootstrap = Storage(str(db_path))
    user_id = _create_user(bootstrap, login)

    storage = Storage(
        str(db_path),
        user_id=user_id,
    )

    storage.reset_paper(100_000.0)

    return storage


def _orders(storage):
    if hasattr(storage, "list_paper_orders"):
        return storage.list_paper_orders()

    with storage.connect() as con:
        uid = storage._uid()
        rows = con.execute(
            """
            SELECT
                symbol,
                market,
                side,
                qty,
                price,
                fee,
                status
            FROM paper_orders_v2
            WHERE user_id=?
            ORDER BY rowid
            """,
            (uid,),
        ).fetchall()

    return [dict(row) for row in rows]


def _field(record, name):
    if isinstance(record, dict):
        return record[name]

    try:
        return record[name]
    except (TypeError, KeyError, IndexError):
        return getattr(record, name)


def test_m223_successful_execution_return_matches_durable_order(tmp_path: Path):
    """
    M2.23 contract:

    A successful execution result and its durable paper-order record
    must describe the same execution.

    Exact fields:
        symbol, market, side, status

    Numeric-equivalent fields:
        qty, price, fee

    Cardinality:
        one successful execution creates exactly one durable FILLED order.
    """

    storage = _make_storage(
        tmp_path / "paper.db",
        "m223-return-durable-equivalence",
    )

    before_orders = _orders(storage)

    result = storage.execute_paper_order(
        symbol="MSFT",
        market="US",
        side="BUY",
        qty=2.0,
        price=125.0,
        fee_bps=15.0,
    )

    after_orders = _orders(storage)

    # One successful execution must create exactly one durable order.
    assert len(after_orders) == len(before_orders) + 1

    durable = after_orders[-1]

    # Both surfaces must represent a successful execution.
    assert result["status"] == "FILLED"
    assert _field(durable, "status") == "FILLED"

    # Exact semantic identity.
    assert _field(durable, "symbol") == result["symbol"]
    assert _field(durable, "market") == result["market"]
    assert _field(durable, "side") == result["side"]
    assert _field(durable, "status") == result["status"]

    # Numeric semantic identity.
    assert float(_field(durable, "qty")) == pytest.approx(
        float(result["qty"])
    )
    assert float(_field(durable, "price")) == pytest.approx(
        float(result["price"])
    )
    assert float(_field(durable, "fee")) == pytest.approx(
        float(result["fee"])
    )

