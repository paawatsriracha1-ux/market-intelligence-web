import pathlib

import pytest

from market_intelligence.storage import Storage


def make_storage(db_path: pathlib.Path, user_id: int) -> Storage:
    """
    Create a Storage instance using an isolated temporary database.

    The production database is never used by this acceptance suite.
    """
    return Storage(path=str(db_path), user_id=user_id)


def create_user(storage: Storage, login: str) -> int:
    """
    Create a real parent user through the production Storage contract.

    register_user signatures have changed during development, so inspect
    the supported contract without modifying production code.
    """
    import inspect

    signature = inspect.signature(storage.register_user)
    parameters = signature.parameters

    kwargs = {}

    if "login" in parameters:
        kwargs["login"] = login

    if "username" in parameters:
        kwargs["username"] = login

    if "email" in parameters:
        kwargs["email"] = f"{login}@m215.local"

    if "password_hash" in parameters:
        kwargs["password_hash"] = "m215-test-password-hash"

    if "role" in parameters:
        kwargs["role"] = "user"

    if "status" in parameters:
        kwargs["status"] = "active"

    result = storage.register_user(**kwargs)

    if isinstance(result, int):
        return result

    if isinstance(result, dict):
        if "id" in result:
            return int(result["id"])
        if "user_id" in result:
            return int(result["user_id"])

    user = storage.get_user_by_login(login)

    assert user is not None, (
        "register_user completed but user could not be recovered"
    )

    if isinstance(user, dict):
        if "id" in user:
            return int(user["id"])
        if "user_id" in user:
            return int(user["user_id"])

    raise AssertionError(
        "Unable to determine registered user id from Storage contract"
    )


@pytest.fixture
def isolated_db(tmp_path):
    return tmp_path / "m215_acceptance.db"


@pytest.fixture
def users(isolated_db):
    """
    Bootstrap database and create two real parent users.

    This deliberately satisfies the FK contract before user-scoped
    child state is written.
    """
    bootstrap = Storage(path=str(isolated_db))
    bootstrap.init_db()

    user_a = create_user(bootstrap, "m215_user_a")
    user_b = create_user(bootstrap, "m215_user_b")

    assert user_a != user_b

    return user_a, user_b


def test_m215_watchlist_is_user_scoped_and_survives_reload(
    isolated_db,
    users,
):
    user_a, user_b = users

    a = make_storage(isolated_db, user_a)
    b = make_storage(isolated_db, user_b)

    a.add_watchlist("AAPL", "US")

    a_reloaded = make_storage(isolated_db, user_a)
    b_reloaded = make_storage(isolated_db, user_b)

    a_rows = a_reloaded.get_watchlist()
    b_rows = b_reloaded.get_watchlist()

    assert any(
        row["symbol"] == "AAPL" and row["market"] == "US"
        for row in a_rows
    )

    assert not any(
        row["symbol"] == "AAPL" and row["market"] == "US"
        for row in b_rows
    )


def test_m215_portfolio_is_user_scoped_and_survives_reload(
    isolated_db,
    users,
):
    user_a, user_b = users

    a = make_storage(isolated_db, user_a)
    b = make_storage(isolated_db, user_b)

    a.upsert_portfolio(
        "AAPL",
        "US",
        10,
        150.0,
    )

    a_reloaded = make_storage(isolated_db, user_a)
    b_reloaded = make_storage(isolated_db, user_b)

    a_rows = a_reloaded.get_portfolio()
    b_rows = b_reloaded.get_portfolio()

    assert any(
        row["symbol"] == "AAPL"
        and row["market"] == "US"
        and float(row["qty"]) == 10.0
        for row in a_rows
    )

    assert not any(
        row["symbol"] == "AAPL" and row["market"] == "US"
        for row in b_rows
    )


def test_m215_paper_account_is_user_scoped_and_survives_reload(
    isolated_db,
    users,
):
    user_a, user_b = users

    a = make_storage(isolated_db, user_a)
    b = make_storage(isolated_db, user_b)

    a.reset_paper(250000.0)
    b.reset_paper(900000.0)

    a_snapshot = make_storage(
        isolated_db,
        user_a,
    ).paper_snapshot()

    b_snapshot = make_storage(
        isolated_db,
        user_b,
    ).paper_snapshot()

    assert float(a_snapshot["cash"]) == pytest.approx(250000.0)
    assert float(b_snapshot["cash"]) == pytest.approx(900000.0)


def test_m215_paper_buy_order_and_position_are_user_scoped(
    isolated_db,
    users,
):
    user_a, user_b = users

    a = make_storage(isolated_db, user_a)
    b = make_storage(isolated_db, user_b)

    a.reset_paper(1000000.0)
    b.reset_paper(1000000.0)

    result = a.execute_paper_order(
        "AAPL",
        "US",
        "BUY",
        10,
        100.0,
    )

    assert result is not None

    a_snapshot = make_storage(
        isolated_db,
        user_a,
    ).paper_snapshot()

    b_snapshot = make_storage(
        isolated_db,
        user_b,
    ).paper_snapshot()

    a_positions = a_snapshot.get("positions", [])
    b_positions = b_snapshot.get("positions", [])

    assert any(
        row["symbol"] == "AAPL"
        and row["market"] == "US"
        and float(row["qty"]) > 0
        for row in a_positions
    )

    assert not any(
        row["symbol"] == "AAPL" and row["market"] == "US"
        for row in b_positions
    )


def test_m215_user_b_cannot_remove_user_a_watchlist_state(
    isolated_db,
    users,
):
    user_a, user_b = users

    a = make_storage(isolated_db, user_a)
    b = make_storage(isolated_db, user_b)

    a.add_watchlist("MSFT", "US")

    b.remove_watchlist("MSFT", "US")

    a_rows = make_storage(
        isolated_db,
        user_a,
    ).get_watchlist()

    assert any(
        row["symbol"] == "MSFT" and row["market"] == "US"
        for row in a_rows
    )


def test_m215_legacy_tables_do_not_leak_into_user_scoped_state(
    isolated_db,
    users,
):
    user_a, user_b = users

    a = make_storage(isolated_db, user_a)
    b = make_storage(isolated_db, user_b)

    a.add_watchlist("NVDA", "US")
    a.upsert_portfolio("NVDA", "US", 5, 120.0)

    b_watchlist = b.get_watchlist()
    b_portfolio = b.get_portfolio()

    assert not any(
        row["symbol"] == "NVDA" and row["market"] == "US"
        for row in b_watchlist
    )

    assert not any(
        row["symbol"] == "NVDA" and row["market"] == "US"
        for row in b_portfolio
    )
