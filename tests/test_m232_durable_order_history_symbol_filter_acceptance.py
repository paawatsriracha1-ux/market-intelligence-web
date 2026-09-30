import sqlite3
from pathlib import Path

from market_intelligence.storage import Storage


def _create_user(
    bootstrap: Storage,
    login: str,
) -> int:
    result = bootstrap.register_user(
        username=login,
        email=f"{login}@example.com",
        password_hash="m232-test-password-hash",
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
        "M2.32 fixture could not resolve integer user_id"
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
    result = storage.execute_paper_order(
        symbol=symbol,
        market="US",
        side="BUY",
        qty=1.0,
        price=10.0,
        idempotency_key=key,
    )

    assert result is not None
    assert result["status"] == "FILLED"
    assert "order_id" in result

    return result


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


def test_m232_durable_order_history_symbol_filter_contract(
    tmp_path: Path,
):
    db_path = tmp_path / "m232.sqlite3"

    # --------------------------------------------------------
    # PHASE 1 — USERS / SCOPED STORAGE
    # --------------------------------------------------------

    bootstrap = Storage(str(db_path))

    owner_id = _create_user(
        bootstrap,
        "m232-owner",
    )

    other_id = _create_user(
        bootstrap,
        "m232-other",
    )

    owner = _scoped_storage(
        db_path,
        owner_id,
    )

    other = _scoped_storage(
        db_path,
        other_id,
    )

    unscoped = Storage(str(db_path))

    owner.reset_paper(100_000.0)
    other.reset_paper(100_000.0)

    # --------------------------------------------------------
    # PHASE 2 — M2.31 BACKWARD COMPATIBILITY
    # --------------------------------------------------------

    assert owner.list_paper_orders() == []
    assert other.list_paper_orders() == []

    # This is the first M2.32 contract call.
    # Frozen baseline ef76e87 is expected to fail here because
    # list_paper_orders() does not yet accept symbol=.
    assert unscoped.list_paper_orders(
        symbol="AAPL",
    ) == []

    assert owner.list_paper_orders(
        symbol="NO-MATCH",
    ) == []

    # --------------------------------------------------------
    # PHASE 3 — DURABLE MULTI-SYMBOL HISTORY
    # --------------------------------------------------------

    oldest_target = _execute(
        owner,
        "M232-TARGET",
        "m232-target-oldest",
    )

    oldest_target_id = int(
        oldest_target["order_id"]
    )

    # Push the first target order outside the snapshot
    # newest-200 window while keeping it in durable history.
    for index in range(205):
        _execute(
            owner,
            "M232-OTHER",
            f"m232-other-{index}",
        )

    newest_target = _execute(
        owner,
        "M232-TARGET",
        "m232-target-newest",
    )

    newest_target_id = int(
        newest_target["order_id"]
    )

    other_same_symbol = _execute(
        other,
        "M232-TARGET",
        "m232-other-owner-target",
    )

    other_same_symbol_id = int(
        other_same_symbol["order_id"]
    )

    durable_before = _durable_rows(
        db_path,
        owner_id,
    )

    count_before = _order_count(
        db_path,
        owner_id,
    )

    snapshot_before = owner.paper_snapshot()

    cash_before = snapshot_before["cash"]
    positions_before = snapshot_before["positions"]

    # --------------------------------------------------------
    # PHASE 4 — SYMBOL FILTER
    # --------------------------------------------------------

    filtered = owner.list_paper_orders(
        symbol="  m232-target  ",
    )

    # --------------------------------------------------------
    # PHASE 5 — FILTER CONTRACT
    # --------------------------------------------------------

    assert isinstance(filtered, list)
    assert len(filtered) == 2

    assert all(
        row["symbol"] == "M232-TARGET"
        for row in filtered
    )

    filtered_ids = [
        int(row["id"])
        for row in filtered
    ]

    assert filtered_ids == sorted(
        filtered_ids,
        reverse=True,
    )

    assert newest_target_id in filtered_ids
    assert oldest_target_id in filtered_ids

    assert other_same_symbol_id not in filtered_ids

    assert filtered_ids == [
        newest_target_id,
        oldest_target_id,
    ]

    # --------------------------------------------------------
    # PHASE 6 — DURABLE FIELD EQUIVALENCE / PRIVACY
    # --------------------------------------------------------

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

    for public_row in filtered:
        durable_row = durable_by_id[
            int(public_row["id"])
        ]

        for field in public_fields:
            assert field in public_row
            assert public_row[field] == durable_row[field]

        assert "idempotency_key" not in public_row
        assert "user_id" not in public_row

    # --------------------------------------------------------
    # PHASE 7 — SNAPSHOT INDEPENDENCE
    # --------------------------------------------------------

    snapshot_orders = snapshot_before["orders"]

    assert len(snapshot_orders) == 200

    snapshot_ids = {
        int(row["id"])
        for row in snapshot_orders
    }

    assert oldest_target_id not in snapshot_ids
    assert oldest_target_id in filtered_ids

    unfiltered = owner.list_paper_orders()

    unfiltered_ids = [
        int(row["id"])
        for row in unfiltered
    ]

    assert oldest_target_id in unfiltered_ids

    assert unfiltered_ids == sorted(
        unfiltered_ids,
        reverse=True,
    )

    # --------------------------------------------------------
    # PHASE 8 — READ-ONLY / OBSERVATIONAL CONTRACT
    # --------------------------------------------------------

    filtered_again = owner.list_paper_orders(
        symbol="M232-TARGET",
    )

    assert filtered_again == filtered

    count_after = _order_count(
        db_path,
        owner_id,
    )

    snapshot_after = owner.paper_snapshot()

    assert count_after == count_before
    assert snapshot_after["cash"] == cash_before
    assert snapshot_after["positions"] == positions_before

    # Other owner remains isolated even for the same symbol.
    other_filtered = other.list_paper_orders(
        symbol="M232-TARGET",
    )

    other_filtered_ids = [
        int(row["id"])
        for row in other_filtered
    ]

    assert other_same_symbol_id in other_filtered_ids
    assert newest_target_id not in other_filtered_ids
    assert oldest_target_id not in other_filtered_ids

    # M2.31 unfiltered history remains owner-scoped.
    assert all(
        int(row["id"]) != other_same_symbol_id
        for row in unfiltered
    )