from market_intelligence.storage import Storage


def _register_user(storage, username, email):
    result = storage.register_user(
        username=username,
        email=email,
        password_hash="m236-test-password-hash",
    )

    if isinstance(result, dict) and "user_id" in result:
        return int(result["user_id"])

    if isinstance(result, int):
        return int(result)

    user = storage.get_user_by_login(username)

    if "id" in user:
        return int(user["id"])

    if "user_id" in user:
        return int(user["user_id"])

    raise AssertionError(
        "M2.36 fixture could not resolve integer user_id"
    )


def _storage_for_user(db_path, user_id):
    return Storage(
        str(db_path),
        user_id=user_id,
    )


def _create_order(
    storage,
    *,
    symbol,
    side,
    market,
    status,
    quantity=1.0,
    order_type="market",
):
    # Fixture-only durable-history insertion.
    # M2.36 tests list/limit semantics, not paper-trading execution rules.
    qty = float(quantity)
    price = 10.0
    gross = qty * price
    fee = 0.0

    with storage.connect() as con:
        cursor = con.execute(
            """
            INSERT INTO paper_orders_v2
                (user_id, symbol, market, side, qty, price, gross, fee, status, created_at)
            VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                int(storage.user_id),
                symbol,
                market,
                side,
                qty,
                price,
                gross,
                fee,
                str(status).strip().upper(),
            ),
        )
        con.commit()
        order_id = int(cursor.lastrowid)

    return {"order_id": order_id}


def _ids(rows):
    return [row["id"] for row in rows]


def test_m236_limit_none_preserves_existing_unbounded_history(tmp_path):
    db_path = tmp_path / "m236-limit-none.db"

    bootstrap = Storage(str(db_path))
    user_id = _register_user(
        bootstrap,
        "m236-owner-none",
        "m236-owner-none@example.com",
    )
    storage = _storage_for_user(db_path, user_id)

    _create_order(
        storage,
        symbol="M236A",
        side="BUY",
        market="US",
        status="open",
    )
    _create_order(
        storage,
        symbol="M236B",
        side="SELL",
        market="TH",
        status="filled",
    )
    _create_order(
        storage,
        symbol="M236C",
        side="BUY",
        market="US",
        status="cancelled",
    )

    existing = storage.list_paper_orders()
    limited = storage.list_paper_orders(limit=None)

    assert limited == existing
    assert len(limited) == 3


def test_m236_positive_limit_returns_newest_first_prefix(tmp_path):
    db_path = tmp_path / "m236-prefix.db"

    bootstrap = Storage(str(db_path))
    user_id = _register_user(
        bootstrap,
        "m236-owner-prefix",
        "m236-owner-prefix@example.com",
    )
    storage = _storage_for_user(db_path, user_id)

    for symbol in ("M236A", "M236B", "M236C", "M236D"):
        _create_order(
            storage,
            symbol=symbol,
            side="BUY",
            market="US",
            status="open",
        )

    all_rows = storage.list_paper_orders()
    limited = storage.list_paper_orders(limit=2)

    assert len(all_rows) == 4
    assert limited == all_rows[:2]
    assert _ids(limited) == sorted(_ids(limited), reverse=True)


def test_m236_limit_one_returns_newest_matching_order(tmp_path):
    db_path = tmp_path / "m236-one.db"

    bootstrap = Storage(str(db_path))
    user_id = _register_user(
        bootstrap,
        "m236-owner-one",
        "m236-owner-one@example.com",
    )
    storage = _storage_for_user(db_path, user_id)

    _create_order(
        storage,
        symbol="M236OLD",
        side="BUY",
        market="US",
        status="open",
    )
    _create_order(
        storage,
        symbol="M236NEW",
        side="SELL",
        market="TH",
        status="filled",
    )

    all_rows = storage.list_paper_orders()
    limited = storage.list_paper_orders(limit=1)

    assert len(limited) == 1
    assert limited == all_rows[:1]
    assert limited[0]["symbol"] == "M236NEW"


def test_m236_limit_larger_than_available_returns_all(tmp_path):
    db_path = tmp_path / "m236-large.db"

    bootstrap = Storage(str(db_path))
    user_id = _register_user(
        bootstrap,
        "m236-owner-large",
        "m236-owner-large@example.com",
    )
    storage = _storage_for_user(db_path, user_id)

    for symbol in ("M236A", "M236B", "M236C"):
        _create_order(
            storage,
            symbol=symbol,
            side="BUY",
            market="US",
            status="open",
        )

    all_rows = storage.list_paper_orders()
    limited = storage.list_paper_orders(limit=50)

    assert limited == all_rows
    assert len(limited) == 3


def test_m236_limit_composes_with_existing_filters_after_filtering(tmp_path):
    db_path = tmp_path / "m236-composition.db"

    bootstrap = Storage(str(db_path))
    user_id = _register_user(
        bootstrap,
        "m236-owner-composition",
        "m236-owner-composition@example.com",
    )
    storage = _storage_for_user(db_path, user_id)

    fixtures = [
        ("MATCH", "BUY", "US", "open"),
        ("OTHER", "BUY", "US", "open"),
        ("MATCH", "SELL", "US", "open"),
        ("MATCH", "BUY", "TH", "open"),
        ("MATCH", "BUY", "US", "filled"),
        ("MATCH", "BUY", "US", "open"),
        ("MATCH", "BUY", "US", "open"),
    ]

    for symbol, side, market, status in fixtures:
        _create_order(
            storage,
            symbol=symbol,
            side=side,
            market=market,
            status=status,
        )

    symbol_rows = storage.list_paper_orders(symbol="MATCH")
    side_rows = storage.list_paper_orders(side="BUY")
    market_rows = storage.list_paper_orders(market="US")
    status_rows = storage.list_paper_orders(status="open")

    assert storage.list_paper_orders(
        symbol="MATCH",
        limit=2,
    ) == symbol_rows[:2]

    assert storage.list_paper_orders(
        side="BUY",
        limit=2,
    ) == side_rows[:2]

    assert storage.list_paper_orders(
        market="US",
        limit=2,
    ) == market_rows[:2]

    assert storage.list_paper_orders(
        status="open",
        limit=2,
    ) == status_rows[:2]

    combined = storage.list_paper_orders(
        symbol="MATCH",
        side="BUY",
        market="US",
        status="open",
    )

    combined_limited = storage.list_paper_orders(
        symbol="MATCH",
        side="BUY",
        market="US",
        status="open",
        limit=2,
    )

    assert len(combined) == 3
    assert combined_limited == combined[:2]

    assert all(row["symbol"] == "MATCH" for row in combined_limited)
    assert all(row["side"] == "BUY" for row in combined_limited)
    assert all(row["market"] == "US" for row in combined_limited)
    assert all(row["status"] == "OPEN" for row in combined_limited)


def test_m236_limit_preserves_no_match_and_existing_return_shape(tmp_path):
    db_path = tmp_path / "m236-shape.db"

    bootstrap = Storage(str(db_path))
    user_id = _register_user(
        bootstrap,
        "m236-owner-shape",
        "m236-owner-shape@example.com",
    )
    storage = _storage_for_user(db_path, user_id)

    _create_order(
        storage,
        symbol="M236SHAPE",
        side="BUY",
        market="US",
        status="open",
    )

    existing = storage.list_paper_orders()
    limited = storage.list_paper_orders(limit=1)

    assert limited == existing[:1]
    assert isinstance(limited, list)
    assert isinstance(limited[0], dict)
    assert set(limited[0].keys()) == set(existing[0].keys())

    assert storage.list_paper_orders(
        symbol="DOES-NOT-EXIST",
        limit=1,
    ) == []


def test_m236_limit_preserves_current_user_isolation(tmp_path):
    db_path = tmp_path / "m236-isolation.db"

    bootstrap = Storage(str(db_path))

    owner_id = _register_user(
        bootstrap,
        "m236-owner-isolation",
        "m236-owner-isolation@example.com",
    )

    other_id = _register_user(
        bootstrap,
        "m236-other-isolation",
        "m236-other-isolation@example.com",
    )

    owner = _storage_for_user(db_path, owner_id)
    other = _storage_for_user(db_path, other_id)

    _create_order(
        owner,
        symbol="OWNER_ONLY",
        side="BUY",
        market="US",
        status="open",
    )

    _create_order(
        other,
        symbol="OTHER_ONLY",
        side="SELL",
        market="TH",
        status="filled",
    )

    owner_rows = owner.list_paper_orders(limit=10)
    other_rows = other.list_paper_orders(limit=10)

    assert [row["symbol"] for row in owner_rows] == ["OWNER_ONLY"]
    assert [row["symbol"] for row in other_rows] == ["OTHER_ONLY"]


def test_m236_limit_persists_across_storage_reopen(tmp_path):
    db_path = tmp_path / "m236-reopen.db"

    bootstrap = Storage(str(db_path))
    user_id = _register_user(
        bootstrap,
        "m236-owner-reopen",
        "m236-owner-reopen@example.com",
    )

    storage = _storage_for_user(db_path, user_id)

    for symbol in ("M236OLD", "M236MID", "M236NEW"):
        _create_order(
            storage,
            symbol=symbol,
            side="BUY",
            market="US",
            status="open",
        )

    before = storage.list_paper_orders(limit=2)

    reopened = _storage_for_user(db_path, user_id)
    after = reopened.list_paper_orders(limit=2)

    assert after == before
    assert [row["symbol"] for row in after] == ["M236NEW", "M236MID"]