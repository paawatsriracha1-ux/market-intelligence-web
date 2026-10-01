"""M2.35 acceptance contract for durable paper-order history status filtering.

Contract:
- list_paper_orders() accepts optional status=
- nonblank status is trimmed and uppercased
- None, empty, and whitespace-only status mean no status filter
- status composes with symbol, side, and market using AND semantics
- history remains owner-scoped, durable across Storage reopen, newest-first,
  and preserves the existing durable-order dictionary row shape
"""

import inspect

from market_intelligence.storage import Storage


def _make_storage(tmp_path, user_id):
    """Create Storage using the constructor shape supported by this repository."""
    parameters = inspect.signature(Storage).parameters
    kwargs = {}

    db_path = tmp_path / "m235_status_filter.db"

    if "db_path" in parameters:
        kwargs["db_path"] = str(db_path)
    elif "path" in parameters:
        kwargs["path"] = str(db_path)
    elif "database" in parameters:
        kwargs["database"] = str(db_path)

    if "user_id" in parameters:
        kwargs["user_id"] = user_id

    storage = Storage(**kwargs)

    # Some repository revisions expose user_id as mutable Storage state.
    if getattr(storage, "user_id", None) is None:
        storage.user_id = user_id

    return storage


def _insert_order(
    storage,
    *,
    user_id,
    symbol,
    market,
    side,
    status,
    qty=1.0,
    price=100.0,
):
    """Insert a durable paper order directly into the M2 durable source."""
    gross = float(qty) * float(price)
    fee = 0.0

    with storage.connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO paper_orders_v2
                (user_id, symbol, market, side, qty, price, gross, fee, status, created_at)
            VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                user_id,
                symbol,
                market,
                side,
                qty,
                price,
                gross,
                fee,
                status,
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)


def _ids(rows):
    return [row["id"] for row in rows]



def _m235_register_user(bootstrap, username: str) -> int:
    result = bootstrap.register_user(
        username=username,
        email=f"{username}@example.com",
        password_hash="m235-test-password-hash",
    )

    if isinstance(result, int):
        return int(result)

    if isinstance(result, dict):
        if "user_id" in result:
            return int(result["user_id"])
        if "id" in result:
            return int(result["id"])

    user = bootstrap.get_user(username)

    if isinstance(user, dict):
        if "user_id" in user:
            return int(user["user_id"])
        if "id" in user:
            return int(user["id"])

    raise AssertionError(
        "M2.35 fixture could not resolve integer user_id"
    )

def test_m235_durable_order_history_status_filter_contract(tmp_path):
    bootstrap = _make_storage(tmp_path, None)
    owner = _m235_register_user(bootstrap, "m235-owner")
    other_user = _m235_register_user(bootstrap, "m235-other")
    storage = _make_storage(tmp_path, owner)

    # Owner rows deliberately span all existing filter dimensions and status.
    id_a = _insert_order(
        storage,
        user_id=owner,
        symbol="AAPL",
        market="US",
        side="BUY",
        status="FILLED",
        price=101.0,
    )
    id_b = _insert_order(
        storage,
        user_id=owner,
        symbol="AAPL",
        market="US",
        side="SELL",
        status="REJECTED",
        price=102.0,
    )
    id_c = _insert_order(
        storage,
        user_id=owner,
        symbol="MSFT",
        market="US",
        side="BUY",
        status="FILLED",
        price=103.0,
    )
    id_d = _insert_order(
        storage,
        user_id=owner,
        symbol="PTT",
        market="TH",
        side="BUY",
        status="FILLED",
        price=104.0,
    )
    id_e = _insert_order(
        storage,
        user_id=owner,
        symbol="AAPL",
        market="US",
        side="BUY",
        status="FILLED",
        price=105.0,
    )

    # Foreign-user row must never leak into owner's history.
    foreign_id = _insert_order(
        storage,
        user_id=other_user,
        symbol="AAPL",
        market="US",
        side="BUY",
        status="FILLED",
        price=999.0,
    )

    expected_unfiltered = [id_e, id_d, id_c, id_b, id_a]

    # 01 โ€” Existing unfiltered history remains intact and newest-first.
    unfiltered = storage.list_paper_orders()
    assert _ids(unfiltered) == expected_unfiltered
    assert foreign_id not in _ids(unfiltered)

    # 02 โ€” Exact status match.
    filled = storage.list_paper_orders(status="FILLED")
    assert _ids(filled) == [id_e, id_d, id_c, id_a]
    assert all(row["status"] == "FILLED" for row in filled)

    # 03 โ€” trim + uppercase normalization.
    normalized = storage.list_paper_orders(status="  filled  ")
    assert _ids(normalized) == [id_e, id_d, id_c, id_a]

    # 04 โ€” None means no status filter.
    assert _ids(storage.list_paper_orders(status=None)) == expected_unfiltered

    # 05 โ€” empty string means no status filter.
    assert _ids(storage.list_paper_orders(status="")) == expected_unfiltered

    # 06 โ€” whitespace-only means no status filter.
    assert _ids(storage.list_paper_orders(status="   ")) == expected_unfiltered

    # 07 โ€” no match returns [].
    assert storage.list_paper_orders(status="CANCELLED") == []

    # 08 โ€” compose status + symbol.
    rows = storage.list_paper_orders(symbol=" aapl ", status=" filled ")
    assert _ids(rows) == [id_e, id_a]

    # 09 โ€” compose status + side.
    rows = storage.list_paper_orders(side=" buy ", status=" filled ")
    assert _ids(rows) == [id_e, id_d, id_c, id_a]

    # 10 โ€” compose status + market.
    rows = storage.list_paper_orders(market=" us ", status=" filled ")
    assert _ids(rows) == [id_e, id_c, id_a]

    # 11 โ€” four-way AND composition.
    rows = storage.list_paper_orders(
        symbol=" aapl ",
        side=" buy ",
        market=" us ",
        status=" filled ",
    )
    assert _ids(rows) == [id_e, id_a]

    # 12 โ€” current-user isolation remains enforced under status filtering.
    assert foreign_id not in _ids(
        storage.list_paper_orders(
            symbol="AAPL",
            side="BUY",
            market="US",
            status="FILLED",
        )
    )

    # 13 โ€” reopen persistence.
    reopened = _make_storage(tmp_path, owner)
    reopened_rows = reopened.list_paper_orders(status=" filled ")
    assert _ids(reopened_rows) == [id_e, id_d, id_c, id_a]
    assert foreign_id not in _ids(reopened_rows)

    # 14 โ€” newest-first ordering is preserved.
    reopened_ids = _ids(reopened_rows)
    assert reopened_ids == sorted(reopened_ids, reverse=True)

    # 15 โ€” existing durable-order return shape is preserved.
    required_keys = {
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
    }
    assert reopened_rows
    assert all(isinstance(row, dict) for row in reopened_rows)
    assert all(required_keys.issubset(row.keys()) for row in reopened_rows)
