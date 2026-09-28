import concurrent.futures

import pytest

from market_intelligence.storage import Storage


def _create_user(storage: Storage, login: str) -> int:
    with storage.connect() as con:
        cur = con.execute(
            """
            INSERT INTO users(username, email, password_hash, role, status)
            VALUES (?, ?, ?, 'user', 'active')
            """,
            (
                login,
                f"{login}@example.com",
                "m220-test-hash",
            ),
        )
        return int(cur.lastrowid)


def _make_storage(db_path, login: str, cash: float = 100_000.0):
    root = Storage(str(db_path))
    user_id = _create_user(root, login)

    scoped = Storage(
        str(db_path),
        user_id=user_id,
    )
    scoped.reset_paper(cash)

    return scoped, user_id



def _cash(storage):
    return float(storage.paper_snapshot()["cash"])


def _position(storage, symbol, market):
    symbol = symbol.upper()
    market = market.upper()

    snapshot = storage.paper_snapshot()

    for row in snapshot["positions"]:
        if (
            row["symbol"] == symbol
            and row["market"] == market
        ):
            return row

    return None


def _orders(storage):
    return storage.paper_snapshot()["orders"]


def test_m220_successful_buy_mutates_cash_and_position_exactly_once(tmp_path):
    storage, user_id = _make_storage(tmp_path / "paper.db", "m220-user")
    """
    M2.20 contract:
    one successful BUY execution must mutate persistent cash and
    position exactly once.

    This intentionally asserts the real production debit formula:

        gross = qty * price
        fee   = gross * fee_bps / 10000
        debit = gross + fee
    """

    symbol = "AAPL"
    market = "US"
    qty = 2.0
    price = 100.0
    fee_bps = 15.0

    before_cash = _cash(storage)

    before_position = _position(storage, symbol, market)
    before_qty = (
        float(before_position["qty"])
        if before_position is not None
        else 0.0
    )

    before_orders = len(_orders(storage))

    result = storage.execute_paper_order(
        symbol=symbol,
        market=market,
        side="BUY",
        qty=qty,
        price=price,
        fee_bps=fee_bps,
        idempotency_key="m220-success-exactly-once",
    )

    after_cash = _cash(storage)
    after_position = _position(storage, symbol, market)
    after_orders = len(_orders(storage))

    gross = qty * price
    fee = gross * fee_bps / 10000.0
    expected_debit = gross + fee

    assert result["status"] == "FILLED"

    assert after_cash == pytest.approx(
        before_cash - expected_debit
    )

    assert after_position is not None

    assert float(after_position["qty"]) == pytest.approx(
        before_qty + qty
    )

    assert after_orders == before_orders + 1


def test_m220_concurrent_same_key_debits_cash_exactly_once(tmp_path):
    storage, user_id = _make_storage(tmp_path / "paper.db", "m220-user")
    """
    M2.20 contract:
    concurrent submissions carrying the same idempotency key must
    produce only one persistent economic mutation.

    Cash must therefore be debited exactly once, not once per caller.
    """

    symbol = "MSFT"
    market = "US"
    qty = 3.0
    price = 120.0
    fee_bps = 15.0
    key = "m220-concurrent-cash-exactly-once"

    before_cash = _cash(storage)

    before_position = _position(storage, symbol, market)
    before_qty = (
        float(before_position["qty"])
        if before_position is not None
        else 0.0
    )

    before_orders = len(_orders(storage))

    def submit():
        return storage.execute_paper_order(
            symbol=symbol,
            market=market,
            side="BUY",
            qty=qty,
            price=price,
            fee_bps=fee_bps,
            idempotency_key=key,
        )

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=2
    ) as pool:
        future_a = pool.submit(submit)
        future_b = pool.submit(submit)

        result_a = future_a.result()
        result_b = future_b.result()

    after_cash = _cash(storage)
    after_position = _position(storage, symbol, market)
    after_orders = len(_orders(storage))

    gross = qty * price
    fee = gross * fee_bps / 10000.0
    expected_debit = gross + fee

    assert result_a["status"] == "FILLED"
    assert result_b["status"] == "FILLED"

    # Critical M2.20 missing contract:
    # persistent cash changes exactly once.
    assert after_cash == pytest.approx(
        before_cash - expected_debit
    )

    assert after_position is not None

    assert float(after_position["qty"]) == pytest.approx(
        before_qty + qty
    )

    # Same idempotency key must persist only one order.
    assert after_orders == before_orders + 1



