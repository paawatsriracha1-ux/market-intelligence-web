"""
M2.26 paper snapshot retention-window acceptance contract.

The durable database may contain more than 200 paper orders, while the
public paper_snapshot() surface exposes only the newest 200 durable orders.

Orders outside the public snapshot window remain durable and must not be
interpreted as deleted.
"""

from pathlib import Path

from market_intelligence.storage import Storage


def _make_storage(db_path: Path) -> Storage:
    bootstrap = Storage(str(db_path))

    login = "m226-user"

    result = bootstrap.register_user(
        username=login,
        email=f"{login}@example.com",
        password_hash="m226-test-password-hash",
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
                "M2.26 fixture could not resolve integer user_id"
            )

    storage = Storage(
        str(db_path),
        user_id=user_id,
    )

    storage.reset_paper(100_000.0)

    return storage


def test_m226_paper_snapshot_exposes_only_newest_200_durable_orders(
    tmp_path: Path,
):
    storage = _make_storage(tmp_path / "m226.db")
    user_id = storage._uid()

    # Seed the durable order table directly so this acceptance contract
    # isolates snapshot retention from cash, fee, and position economics.
    with storage.connect() as con:
        for index in range(201):
            con.execute(
                """
                INSERT INTO paper_orders_v2(
                    user_id,
                    symbol,
                    market,
                    side,
                    qty,
                    price,
                    gross,
                    fee,
                    status,
                    idempotency_key
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'FILLED', ?)
                """,
                (
                    user_id,
                    f"T{index:03d}",
                    "US",
                    "BUY",
                    1.0,
                    100.0 + index,
                    100.0 + index,
                    0.0,
                    f"m226-{index:03d}",
                ),
            )

    # Prove the durable database contains all 201 executions.
    with storage.connect() as con:
        durable_rows = con.execute(
            """
            SELECT id
            FROM paper_orders_v2
            WHERE user_id=?
            ORDER BY id ASC
            """,
            (user_id,),
        ).fetchall()

    durable_ids = [
        int(row["id"])
        for row in durable_rows
    ]

    assert len(durable_ids) == 201

    oldest_id = durable_ids[0]
    expected_snapshot_ids = list(
        reversed(durable_ids[-200:])
    )

    snapshot = storage.paper_snapshot()
    orders = snapshot["orders"]

    snapshot_ids = [
        int(order["id"])
        for order in orders
    ]

    # Public retention window is exactly the newest 200 durable orders.
    assert len(snapshot_ids) == 200
    assert snapshot_ids == expected_snapshot_ids
    assert snapshot_ids == sorted(snapshot_ids, reverse=True)

    # The oldest durable order falls outside the public window.
    assert oldest_id not in snapshot_ids

    # Falling outside the public snapshot does not mean deletion.
    with storage.connect() as con:
        oldest_still_durable = con.execute(
            """
            SELECT COUNT(*)
            FROM paper_orders_v2
            WHERE user_id=? AND id=?
            """,
            (user_id, oldest_id),
        ).fetchone()[0]

    assert oldest_still_durable == 1