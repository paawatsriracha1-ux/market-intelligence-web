from market_intelligence.storage import Storage


def _register_user(storage, username, email):
    result = storage.register_user(
        username=username,
        email=email,
        password_hash="m237-test-password-hash",
    )

    if isinstance(result, dict) and "user_id" in result:
        return int(result["user_id"])

    if isinstance(result, int):
        return int(result)

    user = storage.get_user_by_login(username)

    if user is not None and "id" in user:
        return int(user["id"])

    if user is not None and "user_id" in user:
        return int(user["user_id"])

    raise AssertionError(
        "M2.37 fixture could not resolve integer user_id"
    )


def _make_storage(
    tmp_path,
    name="m237-offset.db",
    username="m237-owner",
):
    db_path = tmp_path / name

    bootstrap = Storage(str(db_path))

    user_id = _register_user(
        bootstrap,
        username,
        f"{username}@example.com",
    )

    return Storage(
        str(db_path),
        user_id=user_id,
    )


def _insert_order(storage, symbol, status="OPEN"):
    with storage.connect() as con:
        cursor = con.execute(
            """
            INSERT INTO paper_orders_v2
            (user_id, symbol, market, side, qty, price, gross, fee, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                int(storage.user_id),
                symbol,
                "US",
                "BUY",
                1.0,
                100.0,
                100.0,
                0.0,
                status,
            ),
        )
        return int(cursor.lastrowid)


def _symbols(rows):
    return [row["symbol"] for row in rows]


def test_m237_offset_none_preserves_existing_history(tmp_path):
    storage = _make_storage(
        tmp_path,
        name="m237-none.db",
        username="m237-owner-none",
    )

    _insert_order(storage, "A")
    _insert_order(storage, "B")
    _insert_order(storage, "C")

    existing = storage.list_paper_orders()
    actual = storage.list_paper_orders(offset=None)

    assert actual == existing


def test_m237_offset_zero_preserves_existing_history(tmp_path):
    storage = _make_storage(
        tmp_path,
        name="m237-zero.db",
        username="m237-owner-zero",
    )

    _insert_order(storage, "A")
    _insert_order(storage, "B")
    _insert_order(storage, "C")

    existing = storage.list_paper_orders()
    actual = storage.list_paper_orders(offset=0)

    assert actual == existing


def test_m237_positive_offset_skips_newest_rows(tmp_path):
    storage = _make_storage(
        tmp_path,
        name="m237-positive.db",
        username="m237-owner-positive",
    )

    _insert_order(storage, "OLD")
    _insert_order(storage, "MID")
    _insert_order(storage, "NEW")

    all_rows = storage.list_paper_orders()
    actual = storage.list_paper_orders(offset=1)

    assert actual == all_rows[1:]
    assert _symbols(actual) == ["MID", "OLD"]


def test_m237_offset_larger_than_available_returns_empty(tmp_path):
    storage = _make_storage(
        tmp_path,
        name="m237-large.db",
        username="m237-owner-large",
    )

    _insert_order(storage, "A")
    _insert_order(storage, "B")

    actual = storage.list_paper_orders(offset=50)

    assert actual == []


def test_m237_offset_composes_with_limit(tmp_path):
    storage = _make_storage(
        tmp_path,
        name="m237-limit.db",
        username="m237-owner-limit",
    )

    for symbol in ("A", "B", "C", "D", "E"):
        _insert_order(storage, symbol)

    all_rows = storage.list_paper_orders()

    actual = storage.list_paper_orders(
        limit=2,
        offset=1,
    )

    assert actual == all_rows[1:3]
    assert _symbols(actual) == ["D", "C"]


def test_m237_offset_applies_after_existing_filters(tmp_path):
    storage = _make_storage(
        tmp_path,
        name="m237-filter.db",
        username="m237-owner-filter",
    )

    _insert_order(storage, "OTHER", status="OPEN")
    _insert_order(storage, "MATCH", status="OPEN")
    _insert_order(storage, "MATCH", status="CLOSED")
    _insert_order(storage, "MATCH", status="OPEN")
    _insert_order(storage, "MATCH", status="OPEN")

    matching = storage.list_paper_orders(
        symbol="MATCH",
        status="OPEN",
    )

    actual = storage.list_paper_orders(
        symbol="MATCH",
        status="OPEN",
        offset=1,
    )

    assert actual == matching[1:]


def test_m237_offset_preserves_current_user_isolation(tmp_path):
    db_path = tmp_path / "m237-user-isolation.db"

    bootstrap = Storage(str(db_path))

    owner_id = _register_user(
        bootstrap,
        "m237-owner-isolation",
        "m237-owner-isolation@example.com",
    )

    other_id = _register_user(
        bootstrap,
        "m237-other-isolation",
        "m237-other-isolation@example.com",
    )

    owner = Storage(
        str(db_path),
        user_id=owner_id,
    )

    other = Storage(
        str(db_path),
        user_id=other_id,
    )

    _insert_order(owner, "OWNER1")
    _insert_order(owner, "OWNER2")
    _insert_order(owner, "OWNER3")

    _insert_order(other, "OTHER1")
    _insert_order(other, "OTHER2")

    owner_rows = owner.list_paper_orders()
    actual = owner.list_paper_orders(offset=1)

    assert actual == owner_rows[1:]
    assert all(
        row["symbol"].startswith("OWNER")
        for row in actual
    )


def test_m237_offset_persists_across_storage_reopen(tmp_path):
    db_path = tmp_path / "m237-reopen.db"

    bootstrap = Storage(str(db_path))

    user_id = _register_user(
        bootstrap,
        "m237-owner-reopen",
        "m237-owner-reopen@example.com",
    )

    storage = Storage(
        str(db_path),
        user_id=user_id,
    )

    _insert_order(storage, "A")
    _insert_order(storage, "B")
    _insert_order(storage, "C")
    _insert_order(storage, "D")

    before = storage.list_paper_orders(
        limit=2,
    )

    reopened = Storage(
        str(db_path),
        user_id=user_id,
    )

    after = reopened.list_paper_orders(
        limit=2,
        offset=1,
    )

    all_rows = reopened.list_paper_orders()

    assert after == all_rows[1:3]
    assert after != before
