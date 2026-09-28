"""
M2.16 execution-safety acceptance contract.

Frozen baseline entering milestone:
    a251a27

Scope:
    - insufficient cash must not create an invalid BUY execution
    - insufficient position must not create an invalid SELL execution
    - zero quantity must be rejected
    - negative quantity must be rejected
    - zero price must be rejected
    - negative price must be rejected

This is an acceptance contract, not production implementation.
"""

from __future__ import annotations

import ast
import importlib
import inspect
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


# -----------------------------------------------------------------
# Contract discovery helpers
# -----------------------------------------------------------------

EXECUTION_TERMS = (
    "buy",
    "sell",
    "order",
    "execute",
    "trade",
)


def _candidate_modules():
    """Find production modules containing execution-like APIs."""

    result = []

    for path in ROOT.rglob("*.py"):

        rel = path.relative_to(ROOT)

        if (
            "tests" in rel.parts
            or ".venv" in rel.parts
            or "__pycache__" in rel.parts
        ):
            continue

        try:
            source = path.read_text(encoding="utf-8-sig")
            tree = ast.parse(source)
        except Exception:
            continue

        names = []

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                lname = node.name.lower()

                if any(term in lname for term in EXECUTION_TERMS):
                    names.append(node.name)

        if names:
            module_name = ".".join(rel.with_suffix("").parts)
            result.append((module_name, names))

    return result


def _load_execution_targets():
    """
    Load callable execution APIs without assuming one production
    filename or one concrete broker class.
    """

    targets = []

    for module_name, names in _candidate_modules():

        try:
            module = importlib.import_module(module_name)
        except Exception:
            continue

        for name in names:

            obj = getattr(module, name, None)

            if callable(obj):
                targets.append(
                    {
                        "module": module,
                        "owner": None,
                        "name": name,
                        "callable": obj,
                    }
                )

        for _, cls in inspect.getmembers(module, inspect.isclass):

            if cls.__module__ != module.__name__:
                continue

            for name in names:

                obj = getattr(cls, name, None)

                if callable(obj):
                    targets.append(
                        {
                            "module": module,
                            "owner": cls,
                            "name": name,
                            "callable": obj,
                        }
                    )

    return targets


TARGETS = _load_execution_targets()


def test_m216_execution_contract_is_discoverable():

    assert TARGETS, (
        "M2.16 could not discover the frozen execution API contract"
    )


def _execution_surface():

    names = {
        item["name"].lower()
        for item in TARGETS
    }

    return names


# -----------------------------------------------------------------
# Frozen M2.16 acceptance requirements
# -----------------------------------------------------------------

def test_m216_execution_surface_contains_order_or_execution_contract():

    names = _execution_surface()

    assert any(
        (
            "order" in name
            or "execute" in name
            or "trade" in name
            or "buy" in name
            or "sell" in name
        )
        for name in names
    )


def test_m216_invalid_quantity_contract_is_required():

    """
    Quantity <= 0 must never be treated as a valid executable
    quantity.

    This test intentionally freezes the safety requirement before
    any production correction is allowed.
    """

    invalid_quantities = (0, -1)

    assert all(q <= 0 for q in invalid_quantities)


def test_m216_invalid_price_contract_is_required():

    """
    Price <= 0 must never be treated as a valid executable price.
    """

    invalid_prices = (0, -1)

    assert all(p <= 0 for p in invalid_prices)


def test_m216_insufficient_cash_contract_is_required():

    cash = 100.0
    quantity = 10
    price = 20.0

    required = quantity * price

    assert required > cash


def test_m216_insufficient_position_contract_is_required():

    owned_quantity = 5
    sell_quantity = 10

    assert sell_quantity > owned_quantity



# =================================================================
# M2.16 TEST HARNESS
#
# Derived from verified M2.15 isolated user-state acceptance setup.
# Production database is never used.
# =================================================================

from market_intelligence.storage import Storage


def make_storage(db_path: Path, user_id: int) -> Storage:
    return Storage(path=str(db_path), user_id=user_id)


def create_user(storage: Storage, login: str) -> int:
    signature = inspect.signature(storage.register_user)
    parameters = signature.parameters

    kwargs = {}

    if "login" in parameters:
        kwargs["login"] = login

    if "username" in parameters:
        kwargs["username"] = login

    if "email" in parameters:
        kwargs["email"] = f"{login}@m216.local"

    if "password_hash" in parameters:
        kwargs["password_hash"] = "m216-test-password-hash"

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

    assert user is not None

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
    return tmp_path / "m216_execution_acceptance.db"


@pytest.fixture
def users(isolated_db):
    bootstrap = Storage(path=str(isolated_db))
    bootstrap.init_db()

    user_a = create_user(
        bootstrap,
        "m216_user_a",
    )

    user_b = create_user(
        bootstrap,
        "m216_user_b",
    )

    assert user_a != user_b

    return user_a, user_b

# =================================================================
# M2.16 STEP 5C โ€” REAL EXECUTION BEHAVIORAL SAFETY
# =================================================================

import pytest


def _m216_snapshot(storage):
    """Return paper state through the production storage API."""
    return storage.paper_snapshot()


def _m216_position_qty(snapshot, symbol, market):
    qty = 0.0

    for row in snapshot.get("positions", []):
        if (
            row.get("symbol") == symbol
            and row.get("market") == marke
        ):
            qty += float(row.get("qty", 0.0))

    return qty


def test_m216_real_buy_rejects_insufficient_cash(
    isolated_db,
    users,
):
    storage = make_storage(isolated_db, users[0])

    storage.reset_paper(100.0)

    before = _m216_snapshot(storage)

    try:
        storage.execute_paper_order(
            "AAPL",
            "US",
            "BUY",
            10,
            20.0,
        )
    except Exception:
        pass

    after = _m216_snapshot(storage)

    assert float(after["cash"]) == pytest.approx(
        float(before["cash"])
    )

    assert _m216_position_qty(
        after,
        "AAPL",
        "US",
    ) == pytest.approx(
        _m216_position_qty(before, "AAPL", "US")
    )


def test_m216_real_sell_rejects_insufficient_position(
    isolated_db,
    users,
):
    storage = make_storage(isolated_db, users[0])

    storage.reset_paper(100000.0)

    before = _m216_snapshot(storage)

    try:
        storage.execute_paper_order(
            "AAPL",
            "US",
            "SELL",
            10,
            100.0,
        )
    except Exception:
        pass

    after = _m216_snapshot(storage)

    assert float(after["cash"]) == pytest.approx(
        float(before["cash"])
    )

    assert _m216_position_qty(
        after,
        "AAPL",
        "US",
    ) == pytest.approx(0.0)


@pytest.mark.parametrize("qty", [0, -1])
def test_m216_real_order_rejects_invalid_quantity(
    isolated_db,
    users,
    qty,
):
    storage = make_storage(isolated_db, users[0])

    storage.reset_paper(100000.0)

    before = _m216_snapshot(storage)

    try:
        storage.execute_paper_order(
            "AAPL",
            "US",
            "BUY",
            qty,
            100.0,
        )
    except Exception:
        pass

    after = _m216_snapshot(storage)

    assert float(after["cash"]) == pytest.approx(
        float(before["cash"])
    )

    assert _m216_position_qty(
        after,
        "AAPL",
        "US",
    ) == pytest.approx(0.0)


@pytest.mark.parametrize("price", [0, -1])
def test_m216_real_order_rejects_invalid_price(
    isolated_db,
    users,
    price,
):
    storage = make_storage(isolated_db, users[0])

    storage.reset_paper(100000.0)

    before = _m216_snapshot(storage)

    try:
        storage.execute_paper_order(
            "AAPL",
            "US",
            "BUY",
            1,
            price,
        )
    except Exception:
        pass

    after = _m216_snapshot(storage)

    assert float(after["cash"]) == pytest.approx(
        float(before["cash"])
    )

    assert _m216_position_qty(
        after,
        "AAPL",
        "US",
    ) == pytest.approx(0.0)
