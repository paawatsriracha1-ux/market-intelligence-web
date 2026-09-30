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
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row

        row = conn.execute(
            """
            SELECT *
            FROM paper_orders_v2
            WHERE user_id = ?
              AND id = ?
            """,
            (
                user_id,
                order_id,
            ),
        ).fetchone()

    if row is None:
        return None

    return dict(row)


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


def test_m230_durable_order_lookup_survives_storage_reopen(
    tmp_path: Path,
):
    db_path = tmp_path / "m230.sqlite3"

    # --------------------------------------------------------
    # PHASE 1 — ORIGINAL STORAGE
    # --------------------------------------------------------

    bootstrap = Storage(str(db_path))

    owner_id = _create_user(
        bootstrap,
        "m230-owner",
    )

    other_id = _create_user(
        bootstrap,
        "m230-other",
    )

    owner_a = _scoped_storage(
        db_path,
        owner_id,
    )

    owner_a.reset_paper(100_000.0)

    execution = _execute(
        owner_a,
        "M230-REOPEN",
        "m230-reopen",
    )

    assert "order_id" in execution

    order_id = int(
        execution["order_id"]
    )

    durable_before = _durable_row(
        db_path,
        owner_id,
        order_id,
    )

    assert durable_before is not None

    snapshot_before = owner_a.paper_snapshot()

    cash_before = snapshot_before["cash"]
    positions_before = snapshot_before["positions"]

    order_count_before = _order_count(
        db_path,
        owner_id,
    )

    # --------------------------------------------------------
    # PHASE 2 — NEW STORAGE / SAME DATABASE
    # --------------------------------------------------------

    owner_b = _scoped_storage(
        db_path,
        owner_id,
    )

    assert owner_b is not owner_a

    looked_up = owner_b.get_paper_order(
        order_id
    )

    # --------------------------------------------------------
    # PHASE 3 — DURABILITY CONTRACT
    # --------------------------------------------------------

    assert looked_up is not None

    assert int(looked_up["id"]) == order_id

    # Compare durable public lookup fields against the
    # original durable database row.
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
        assert looked_up[field] == durable_before[field]

    # Private idempotency identity must not become part
    # of the public lookup contract.
    assert "idempotency_key" not in looked_up

    # --------------------------------------------------------
    # PHASE 4 — READ-ONLY INVARIANTS
    # --------------------------------------------------------

    order_count_after = _order_count(
        db_path,
        owner_id,
    )

    snapshot_after = owner_b.paper_snapshot()

    assert order_count_after == order_count_before
    assert snapshot_after["cash"] == cash_before
    assert snapshot_after["positions"] == positions_before

    # --------------------------------------------------------
    # PHASE 5 — OWNERSHIP AFTER REOPEN
    # --------------------------------------------------------

    other_b = _scoped_storage(
        db_path,
        other_id,
    )

    assert other_b.get_paper_order(
        order_id
    ) is None

    # --------------------------------------------------------
    # PHASE 6 — UNKNOWN DURABLE ID
    # --------------------------------------------------------

    unknown_order_id = order_id + 1_000_000

    assert owner_b.get_paper_order(
        unknown_order_id
    ) is None
