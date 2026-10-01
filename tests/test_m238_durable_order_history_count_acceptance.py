from market_intelligence.storage import Storage


def _storage(tmp_path, name="m238.db"):
    return Storage(str(tmp_path / name))


def _create_user(storage, username):
    result = storage.register_user(
        username=username,
        email=f"{username}@example.com",
        password_hash="m238-test-password-hash",
    )

    assert isinstance(result, dict)
    assert "id" in result
    return {"id": int(result["id"])}


def _create_order(
    storage,
    *,
    symbol,
    side="BUY",
    market="TH",
    qty=1,
    price=10.0,
):
    result = storage.execute_paper_order(
        symbol=symbol,
        side=side,
        qty=qty,
        price=price,
        market=market,
    )
    return {**result, "id": int(result["order_id"])}


def _set_status(storage, order_id, status):
    with storage.connect() as con:
        con.execute(
            """
            UPDATE paper_orders_v2
            SET status = ?
            WHERE id = ? AND user_id = ?
            """,
            (status, int(order_id), int(storage.user_id)),
        )


def test_m238_empty_current_user_history_returns_zero(tmp_path):
    storage = _storage(tmp_path)
    user = _create_user(storage, "m238-empty")
    storage.user_id = user["id"]

    result = storage.count_paper_orders()

    assert isinstance(result, int)
    assert result == 0


def test_m238_unfiltered_count_returns_all_current_user_orders(tmp_path):
    storage = _storage(tmp_path)
    user = _create_user(storage, "m238-all")
    storage.user_id = user["id"]

    _create_order(storage, symbol="PTT")
    _create_order(storage, symbol="AOT")
    _create_order(storage, symbol="DELTA")

    assert storage.count_paper_orders() == 3


def test_m238_count_supports_existing_history_filters(tmp_path):
    storage = _storage(tmp_path)
    user = _create_user(storage, "m238-filters")
    storage.user_id = user["id"]

    open_ptt = _create_order(
        storage,
        symbol="PTT",
        side="BUY",
        market="TH",
    )
    filled_ptt = _create_order(
        storage,
        symbol="PTT",
        side="BUY",
        market="TH",
    )
    _create_order(
        storage,
        symbol="PTT",
        side="SELL",
        market="TH",
    )
    _create_order(
        storage,
        symbol="AAPL",
        side="BUY",
        market="US",
    )

    _set_status(storage, filled_ptt["id"], "REJECTED")

    assert storage.count_paper_orders(symbol="PTT") == 3
    assert storage.count_paper_orders(side="BUY") == 3
    assert storage.count_paper_orders(market="TH") == 3
    assert storage.count_paper_orders(status="FILLED") == 3
    assert storage.count_paper_orders(status="REJECTED") == 1

    assert storage.count_paper_orders(
        symbol="PTT",
        side="BUY",
        market="TH",
        status="FILLED",
    ) == 1

    assert open_ptt["id"] != filled_ptt["id"]


def test_m238_count_uses_same_filter_normalization_as_list(tmp_path):
    storage = _storage(tmp_path)
    user = _create_user(storage, "m238-normalization")
    storage.user_id = user["id"]

    _create_order(
        storage,
        symbol="PTT",
        side="BUY",
        market="TH",
    )
    _create_order(
        storage,
        symbol="AAPL",
        side="BUY",
        market="US",
    )
    _create_order(
        storage,
        symbol="AAPL",
        side="SELL",
        market="US",
    )

    assert storage.count_paper_orders(
        symbol="ptt",
        side="buy",
        market="th",
        status="open",
    ) == len(
        storage.list_paper_orders(
            symbol="ptt",
            side="buy",
            market="th",
            status="open",
        )
    )


def test_m238_count_is_independent_of_list_pagination(tmp_path):
    storage = _storage(tmp_path)
    user = _create_user(storage, "m238-pagination")
    storage.user_id = user["id"]

    for symbol in ("PTT", "AOT", "DELTA", "CPALL"):
        _create_order(storage, symbol=symbol)

    assert storage.count_paper_orders() == 4
    assert len(storage.list_paper_orders(limit=1, offset=2)) == 1
    assert storage.count_paper_orders() == 4


def test_m238_count_preserves_current_user_isolation(tmp_path):
    storage = _storage(tmp_path)

    owner = _create_user(storage, "m238-owner")
    other = _create_user(storage, "m238-other")

    storage.user_id = owner["id"]
    _create_order(storage, symbol="PTT")
    _create_order(storage, symbol="AOT")

    storage.user_id = other["id"]
    _create_order(storage, symbol="AAPL")

    assert storage.count_paper_orders() == 1

    storage.user_id = owner["id"]
    assert storage.count_paper_orders() == 2


def test_m238_count_persists_across_storage_reopen(tmp_path):
    db_path = tmp_path / "m238-reopen.db"

    storage = Storage(str(db_path))
    user = _create_user(storage, "m238-reopen")
    storage.user_id = user["id"]

    _create_order(storage, symbol="PTT")
    _create_order(storage, symbol="AOT")

    reopened = Storage(str(db_path))
    reopened.user_id = user["id"]

    assert reopened.count_paper_orders() == 2
    assert reopened.count_paper_orders(symbol="PTT") == 1


def test_m238_existing_list_return_shape_remains_unchanged(tmp_path):
    storage = _storage(tmp_path)
    user = _create_user(storage, "m238-shape")
    storage.user_id = user["id"]

    _create_order(storage, symbol="PTT")

    rows = storage.list_paper_orders()

    assert isinstance(rows, list)
    assert len(rows) == 1
    assert isinstance(rows[0], dict)