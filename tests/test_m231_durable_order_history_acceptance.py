import sqlite3
from pathlib import Path

from market_intelligence.storage import Storage


def _create_user(bootstrap: Storage, login: str) -> int:
    result = bootstrap.register_user(
        username=login,
        email=f"{login}@example.com",
        password_hash="m231-test-password-hash",
    )

    if isinstance(result, dict) and "user_id" in result:
        return int(result["user_id"])

    if isinstance(result, int):
        return int(result)

    user = bootstrap.get_user_by_login(login)

    assert user is not None

    if "id" in user:
        return int(user["id"])

    if "user_id" in user:
        return int(user["user_id"])

    raise AssertionError(
        "M2.31 fixture could not resolve integer user_id"
    )


def _scoped_storage(
    db_path: Path,
    user_id: int,
) -> Storage:
    return Storage(
        str(db_path),
        user_id=user_id,
    )


def _execute(
    storage: Storage,
    symbol: str,
    key: str,
) -> dict:
    return storage.execute_paper_order(
        symbol=symbol,
        market="US",
        side="BUY",
        qty=1.0,
        price=10.0,
        idempotency_key=key,
    )


def _durable_rows(
    db_path: Path,
    user_id: int,
) -> list[dict]:
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row

        rows = conn.execute(
            """
            SELECT
                id,
                user_id,
                symbol,
                market,
                side,
                qty,
                price,
                gross,
                fee,
                status,
                idempotency_key,
                created_at
            FROM paper_orders_v2
            WHERE user_id = ?
            ORDER BY id DESC
            """,
            (user_id,),
        ).fetchall()

    return [dict(row) for row in rows]


def _order_count(
    db_path: Path,
    user_id: int,
) -> int:
    with sqlite3.connect(str(db_path)) as conn:
        row = conn.execute(
            """
            SELECT COUNT(*)
            FROM paper_orders_v2
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

    assert row is not None
    return int(row[0])


def test_m231_durable_order_history_contract(
    tmp_path: Path,
):
    db_path = tmp_path / "m231.sqlite3"

    bootstrap = Storage(str(db_path))

    owner_id = _create_user(
        bootstrap,
        "m231-owner",
    )

    other_id = _create_user(
        bootstrap,
        "m231-other",
    )

    empty_id = _create_user(
        bootstrap,
        "m231-empty",
    )

    owner = _scoped_storage(
        db_path,
        owner_id,
    )

    other = _scoped_storage(
        db_path,
        other_id,
    )

    empty = _scoped_storage(
        db_path,
        empty_id,
    )

    unscoped = Storage(str(db_path))

    owner.reset_paper(100_000.0)
    other.reset_paper(100_000.0)
    empty.reset_paper(100_000.0)

    # Empty and unscoped durable history.
    assert unscoped.list_paper_orders() == []
    assert empty.list_paper_orders() == []

    # Create 201 durable orders for the owner.
    owner_order_ids = []

    for i in range(201):
        execution = _execute(
            owner,
            f"M231-{i:03d}",
            f"m231-owner-{i:03d}",
        )

        assert "order_id" in execution

        owner_order_ids.append(
            int(execution["order_id"])
        )

    # Create a durable order belonging to another user.
    other_execution = _execute(
        other,
        "M231-OTHER",
        "m231-other",
    )

    other_order_id = int(
        other_execution["order_id"]
    )

    durable_before = _durable_rows(
        db_path,
        owner_id,
    )

    assert len(durable_before) == 201

    # M2.26 snapshot contract must remain bounded at newest 200.
    snapshot = owner.paper_snapshot()

    assert len(snapshot["orders"]) == 200

    snapshot_ids = {
        int(row["id"])
        for row in snapshot["orders"]
    }

    oldest_order_id = owner_order_ids[0]

    assert oldest_order_id not in snapshot_ids

    # Capture state before durable history lookup.
    cash_before = snapshot["cash"]
    positions_before = snapshot["positions"]

    owner_count_before = _order_count(
        db_path,
        owner_id,
    )

    # M2.31 public durable history contract.
    history = owner.list_paper_orders()

    assert isinstance(history, list)
    assert len(history) == 201

    history_ids = [
        int(row["id"])
        for row in history
    ]

    # History is independent of the bounded snapshot window.
    assert oldest_order_id in history_ids

    # Complete owner durable history.
    assert set(history_ids) == set(owner_order_ids)

    # Newest-first durable identity ordering.
    assert history_ids == sorted(
        history_ids,
        reverse=True,
    )

    durable_by_id = {
        int(row["id"]): row
        for row in durable_before
    }

    public_fields = (
        "id",
        "symbol",
        "market",
        "side",
        "qty",
        "price",
        "gross",
        "fee",
        "status",
        "created_at",
    )

    # Public durable fields must match the durable database rows.
    for row in history:
        order_id = int(row["id"])

        assert order_id in durable_by_id

        durable = durable_by_id[order_id]

        for field in public_fields:
            assert field in row
            assert row[field] == durable[field]

        # Internal idempotency identity remains private.
        assert "idempotency_key" not in row

    # Ownership isolation.
    assert other_order_id not in history_ids

    other_history = other.list_paper_orders()

    other_history_ids = [
        int(row["id"])
        for row in other_history
    ]

    assert other_order_id in other_history_ids

    for owner_order_id in owner_order_ids:
        assert owner_order_id not in other_history_ids

    # Durable history lookup is read-only.
    owner_count_after = _order_count(
        db_path,
        owner_id,
    )

    snapshot_after = owner.paper_snapshot()

    assert owner_count_after == owner_count_before
    assert snapshot_after["cash"] == cash_before
    assert snapshot_after["positions"] == positions_before