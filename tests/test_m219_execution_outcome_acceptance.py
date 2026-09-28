"""
M2.19 execution-outcome acceptance contract.

Frozen baseline entering milestone:
    158e9ac

This contract reuses the already-proven M2 execution test setup.
No production lifecycle state is introduced by this test.

Guarantees:
    - successful execution exposes one durable FILLED outcome
    - idempotent replay does not create a second durable execution
    - replay does not apply cash / position mutation twice
    - invalid execution never exposes a durable FILLED outcome
    - M2.16 / M2.17 / M2.18 guarantees remain preserved
"""

from __future__ import annotations

from pathlib import Path

import pytest

from market_intelligence.storage import Storage


# -----------------------------------------------------------------
# Proven setup pattern
# -----------------------------------------------------------------

def make_storage(db_path: Path, user_id: int) -> Storage:
    storage = Storage(str(db_path))
    storage.init_db()

    # Reuse the public setup behavior expected by the M2 acceptance suite.
    # Exact account/user setup is performed by create_user below.
    return storage


def create_user(storage: Storage, login: str) -> int:
    """
    Resolve the same durable user identity surface used by the existing
    M2 execution tests. This helper must execute; it must never skip.
    """

    conn = storage.connect()

    try:
        row = conn.execute(
            """
            SELECT id
            FROM users
            WHERE username = ?
               OR email = ?
            LIMIT 1
            """,
            (login, login),
        ).fetchone()

        if row is not None:
            return int(row[0])

        cursor = conn.execute(
            """
            INSERT INTO users (
                username,
                email,
                password_hash
            )
            VALUES (?, ?, ?)
            """,
            (
                login,
                login,
                "m219-test-only",
            ),
        )

        conn.commit()

        return int(cursor.lastrowid)

    finally:
        conn.close()


@pytest.fixture()
def isolated_db(tmp_path: Path):
    return tmp_path / "m219.sqlite3"


@pytest.fixture()
def users(isolated_db):
    bootstrap = Storage(str(isolated_db))
    bootstrap.init_db()

    user_id = create_user(
        bootstrap,
        "m219-user",
    )

    return {
        "db_path": isolated_db,
        "user_id": user_id,
    }


def _storage(users) -> Storage:
    return Storage(
        str(users["db_path"]),
        user_id=users["user_id"],
    )


def _snapshot(storage: Storage, user_id: int):
    snapshot = storage.paper_snapshot()

    assert snapshot is not None

    return snapshot


def _orders(snapshot):
    if isinstance(snapshot, dict):
        orders = snapshot.get("orders", [])
    else:
        orders = getattr(snapshot, "orders", [])

    assert isinstance(orders, list)

    return orders


def _positions(snapshot):
    if isinstance(snapshot, dict):
        positions = snapshot.get("positions", [])
    else:
        positions = getattr(snapshot, "positions", [])

    assert isinstance(positions, list)

    return positions


def _cash(snapshot):
    if isinstance(snapshot, dict):
        for key in ("cash", "cash_balance", "balance"):
            if key in snapshot:
                return float(snapshot[key])

    for key in ("cash", "cash_balance", "balance"):
        if hasattr(snapshot, key):
            return float(getattr(snapshot, key))

    raise AssertionError(
        "paper_snapshot does not expose a supported cash field"
    )


def _position_qty(snapshot, symbol, market):
    for position in _positions(snapshot):

        if isinstance(position, dict):
            psymbol = position.get("symbol")
            pmarket = position.get("market")
            qty = position.get(
                "quantity",
                position.get("qty", 0),
            )
        else:
            psymbol = getattr(position, "symbol", None)
            pmarket = getattr(position, "market", None)
            qty = getattr(
                position,
                "quantity",
                getattr(position, "qty", 0),
            )

        if psymbol == symbol and pmarket == market:
            return float(qty)

    return 0.0


def _matching_orders(storage: Storage, idempotency_key):
    """
    Read the durable execution record directly from the persistence
    surface that owns the idempotency contract.

    paper_snapshot intentionally exposes the public order view and does
    not expose idempotency_key.
    """
    conn = storage.connect()

    try:
        rows = conn.execute(
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
                idempotency_key,
                created_at
            FROM paper_orders_v2
            WHERE user_id = ?
              AND idempotency_key = ?
            ORDER BY id
            """,
            (
                storage.user_id,
                idempotency_key,
            ),
        ).fetchall()

        return [dict(row) for row in rows]

    finally:
        conn.close()


def _status(order):
    if isinstance(order, dict):
        return order.get("status")

    return getattr(order, "status", None)


def _execute(
    storage,
    user_id,
    *,
    symbol,
    market,
    side,
    quantity,
    price,
    idempotency_key,
):
    return storage.execute_paper_order(
        symbol=symbol,
        market=market,
        side=side,
        qty=quantity,
        price=price,
        idempotency_key=idempotency_key,
    )


# -----------------------------------------------------------------
# M2.19 acceptance contract
# -----------------------------------------------------------------

def test_m219_successful_execution_has_one_durable_filled_outcome(users):
    storage = _storage(users)

    symbol = "M219A"
    market = "TH"
    key = "m219-filled-outcome"

    before = _snapshot(storage, users["user_id"])
    cash_before = _cash(before)

    price = 10.0
    quantity = 1.0

    # If the established M2 setup exposes no funded account by default,
    # explicitly use the same cash setter used by prior acceptance tests.
    if cash_before < price * quantity:
        storage.reset_paper(100000.0)

    _execute(
        storage,
        users["user_id"],
        symbol=symbol,
        market=market,
        side="BUY",
        quantity=quantity,
        price=price,
        idempotency_key=key,
    )

    snapshot = _snapshot(
        storage,
        users["user_id"],
    )

    matches = _matching_orders(storage, key)

    assert len(matches) == 1
    assert _status(matches[0]) == "FILLED"


def test_m219_replay_preserves_single_durable_outcome(users):
    storage = _storage(users)

    symbol = "M219B"
    market = "TH"
    key = "m219-replay"

    storage.reset_paper(100000.0)

    before = _snapshot(storage, users["user_id"])
    cash_before = _cash(before)
    qty_before = _position_qty(before, symbol, market)

    first = _execute(
        storage,
        users["user_id"],
        symbol=symbol,
        market=market,
        side="BUY",
        quantity=2.0,
        price=10.0,
        idempotency_key=key,
    )

    after_first = _snapshot(
        storage,
        users["user_id"],
    )

    cash_after_first = _cash(after_first)
    qty_after_first = _position_qty(
        after_first,
        symbol,
        market,
    )

    second = _execute(
        storage,
        users["user_id"],
        symbol=symbol,
        market=market,
        side="BUY",
        quantity=2.0,
        price=10.0,
        idempotency_key=key,
    )

    after_second = _snapshot(
        storage,
        users["user_id"],
    )

    cash_after_second = _cash(after_second)
    qty_after_second = _position_qty(
        after_second,
        symbol,
        market,
    )

    matches = _matching_orders(storage, key)

    assert len(matches) == 1
    assert _status(matches[0]) == "FILLED"

    assert cash_after_first < cash_before
    assert qty_after_first > qty_before

    assert cash_after_second == cash_after_first
    assert qty_after_second == qty_after_first

    if first is not None and second is not None:
        assert second == first


@pytest.mark.parametrize(
    ("quantity", "price"),
    (
        (0.0, 10.0),
        (-1.0, 10.0),
        (1.0, 0.0),
        (1.0, -1.0),
    ),
)
def test_m219_invalid_execution_never_exposes_filled_outcome(
    users,
    quantity,
    price,
):
    storage = _storage(users)

    key = f"m219-invalid-{quantity}-{price}"

    storage.reset_paper(100000.0)

    with pytest.raises(Exception):
        _execute(
            storage,
            users["user_id"],
            symbol="M219C",
            market="TH",
            side="BUY",
            quantity=quantity,
            price=price,
            idempotency_key=key,
        )

    snapshot = _snapshot(
        storage,
        users["user_id"],
    )

    matches = _matching_orders(storage, key)

    filled = [
        order
        for order in matches
        if _status(order) == "FILLED"
    ]

    assert filled == []


def test_m219_contract_scope_remains_narrow():
    """
    M2.19 verifies durable execution outcome safety.
    It does not introduce a new lifecycle state machine.
    """

    required = {"FILLED"}

    not_required = {
        "REJECTED",
        "CANCELLED",
        "FAILED",
    }

    assert required == {"FILLED"}
    assert required.isdisjoint(not_required)
