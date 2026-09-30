import sqlite3
from pathlib import Path

from market_intelligence.storage import Storage


def _create_user(bootstrap: Storage, login: str) -> int:
    result = bootstrap.register_user(
        username=login,
        email=f"{login}@example.com",
        password_hash="m229-test-password-hash",
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
        "M2.29 fixture could not resolve integer user_id"
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
    idempotency_key: str,
):
    result = storage.execute_paper_order(
        symbol=symbol,
        market="US",
        side="BUY",
        qty=1.0,
        price=10.0,
        idempotency_key=idempotency_key,
    )

    assert result is not None
    assert result["status"] == "FILLED"
    assert "order_id" in result

    return result


def _durable_row(
    db_path: Path,
    user_id: int,
    order_id: int,
):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    try:
        return conn.execute(
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
                created_at
            FROM paper_orders_v2
            WHERE user_id = ?
              AND id = ?
            """,
            (user_id, order_id),
        ).fetchone()
    finally:
        conn.close()


def _order_count(
    db_path: Path,
    user_id: int,
) -> int:
    conn = sqlite3.connect(str(db_path))

    try:
        return int(
            conn.execute(
                """
                SELECT COUNT(*)
                FROM paper_orders_v2
                WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()[0]
        )
    finally:
        conn.close()


def test_m229_durable_order_lookup_contract(
    tmp_path: Path,
):
    db_path = tmp_path / "m229.sqlite3"

    bootstrap = Storage(str(db_path))

    owner_id = _create_user(
        bootstrap,
        "m229-owner",
    )

    other_id = _create_user(
        bootstrap,
        "m229-other",
    )

    owner = _scoped_storage(
        db_path,
        owner_id,
    )

    owner.reset_paper(100_000.0)

    first = _execute(
        owner,
        "M229-FIRST",
        "m229-first",
    )

    first_order_id = int(first["order_id"])

    # Push the first durable order outside the bounded newest-200
    # paper_snapshot() window.
    for i in range(200):
        _execute(
            owner,
            f"M229-{i:03d}",
            f"m229-{i:03d}",
        )

    snapshot = owner.paper_snapshot()

    snapshot_ids = {
        int(row["id"])
        for row in snapshot["orders"]
    }

    assert first_order_id not in snapshot_ids

    durable = _durable_row(
        db_path,
        owner_id,
        first_order_id,
    )

    assert durable is not None

    cash_before = owner.paper_snapshot()["cash"]
    positions_before = owner.paper_snapshot()["positions"]

    order_count_before = _order_count(
        db_path,
        owner_id,
    )

    # M2.29 public contract:
    # durable lookup must not depend on the bounded snapshot window.
    looked_up = owner.get_paper_order(first_order_id)

    assert looked_up is not None
    assert int(looked_up["id"]) == first_order_id

    for field in (
        "symbol",
        "market",
        "side",
        "qty",
        "price",
        "gross",
        "fee",
        "status",
        "created_at",
    ):
        assert looked_up[field] == durable[field]

    # Persistence-only idempotency metadata remains private.
    assert "idempotency_key" not in looked_up

    # Unknown durable identity must not fabricate an order.
    assert owner.get_paper_order(999999999) is None

    # Lookup is scoped to the Storage user's ownership boundary.
    other = _scoped_storage(
        db_path,
        other_id,
    )

    assert other.get_paper_order(first_order_id) is None

    # Lookup itself must remain read-only.
    assert owner.paper_snapshot()["cash"] == cash_before
    assert owner.paper_snapshot()["positions"] == positions_before

    assert (
        _order_count(
            db_path,
            owner_id,
        )
        == order_count_before
    )

    # Sanity-check ownership fixture.
    assert owner_id != other_id
