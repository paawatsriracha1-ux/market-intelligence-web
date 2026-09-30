from __future__ import annotations

import os
import sqlite3
import hashlib
import secrets
import pickle
from pathlib import Path
from typing import Any

from .config import settings
from market_intelligence.decision.bundle import FinalDecisionBundle


class Storage:
    """SQLite persistence for Market Intelligence V3.

    V3 keeps legacy V1/V2 tables intact, adds secure password-reset tokens,
    and stores multi-user data in *_v2 tables.
    The first startup migrates the existing V1 admin data into the V2 admin account.
    """

    def __init__(self, path: str | None = None, user_id: int | None = None):
        self.path = path or settings.db_path
        self.user_id = int(user_id) if user_id is not None else None
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path, timeout=30)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("PRAGMA busy_timeout=30000")
        return con

    def init_db(self) -> None:
        schema = """
        CREATE TABLE IF NOT EXISTS app_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL COLLATE NOCASE UNIQUE,
            email TEXT NOT NULL COLLATE NOCASE UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user' CHECK(role IN ('admin','user')),
            status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','pending','disabled')),
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            last_login_at TEXT
        );

        CREATE TABLE IF NOT EXISTS watchlist_v2 (
            user_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            market TEXT NOT NULL,
            added_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(user_id, symbol, market),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS portfolio_positions_v2 (
            user_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            market TEXT NOT NULL,
            qty REAL NOT NULL,
            avg_price REAL NOT NULL,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(user_id, symbol, market),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS paper_accounts_v2 (
            user_id INTEGER PRIMARY KEY,
            cash REAL NOT NULL,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS paper_positions_v2 (
            user_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            market TEXT NOT NULL,
            qty REAL NOT NULL,
            avg_price REAL NOT NULL,
            PRIMARY KEY(user_id, symbol, market),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS paper_orders_v2 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            market TEXT NOT NULL,
            side TEXT NOT NULL,
            qty REAL NOT NULL,
            price REAL NOT NULL,
            gross REAL NOT NULL,
            fee REAL NOT NULL,
            status TEXT NOT NULL,
            idempotency_key TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS final_decision_bundles (
            user_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            market TEXT NOT NULL,
            payload BLOB NOT NULL,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(user_id, symbol, market),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS auth_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            event TEXT NOT NULL,
            details TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token_hash TEXT NOT NULL UNIQUE,
            expires_at TEXT NOT NULL,
            used_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_password_reset_user
            ON password_reset_tokens(user_id, used_at, expires_at);

        -- Legacy V1 tables are retained for safe migration / rollback.
        CREATE TABLE IF NOT EXISTS watchlist (
            symbol TEXT NOT NULL, market TEXT NOT NULL,
            added_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(symbol, market));
        CREATE TABLE IF NOT EXISTS portfolio_positions (
            symbol TEXT NOT NULL, market TEXT NOT NULL,
            qty REAL NOT NULL, avg_price REAL NOT NULL,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(symbol, market));
        CREATE TABLE IF NOT EXISTS paper_account (
            id INTEGER PRIMARY KEY CHECK(id=1), cash REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS paper_positions (
            symbol TEXT NOT NULL, market TEXT NOT NULL,
            qty REAL NOT NULL, avg_price REAL NOT NULL,
            PRIMARY KEY(symbol, market));
        CREATE TABLE IF NOT EXISTS paper_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL, market TEXT NOT NULL, side TEXT NOT NULL,
            qty REAL NOT NULL, price REAL NOT NULL, gross REAL NOT NULL,
            fee REAL NOT NULL, status TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        """
        with self.connect() as con:
            # DELETE journaling is reliable on the current Railway persistent volume.
            try:
                con.execute("PRAGMA journal_mode=DELETE")
            except sqlite3.DatabaseError:
                pass
            con.executescript(schema)

            # M2.18: migrate existing databases to durable execution idempotency.
            paper_order_columns = {
                row["name"]
                for row in con.execute("PRAGMA table_info(paper_orders_v2)")
            }
            if "idempotency_key" not in paper_order_columns:
                con.execute(
                    "ALTER TABLE paper_orders_v2 ADD COLUMN idempotency_key TEXT"
                )

            con.execute(
                """CREATE UNIQUE INDEX IF NOT EXISTS
                   idx_paper_orders_v2_user_idempotency
                   ON paper_orders_v2(user_id, idempotency_key)
                   WHERE idempotency_key IS NOT NULL"""
            )
            con.execute(
                "INSERT OR IGNORE INTO paper_account(id, cash) VALUES (1, ?)",
                (settings.default_paper_cash,),
            )
        self._bootstrap_admin()
        self._migrate_v1_admin_data()

    # ---------- users / auth ----------
    def _bootstrap_admin(self) -> None:
        username = os.getenv("APP_LOGIN_USER", "admin").strip() or "admin"
        password_hash = os.getenv("APP_LOGIN_PASSWORD_HASH", "").strip()
        if not password_hash:
            return
        email = os.getenv("APP_ADMIN_EMAIL", "admin@market-intelligence.local").strip().lower()
        with self.connect() as con:
            con.execute(
                """
                INSERT INTO users(username, email, password_hash, role, status)
                VALUES (?, ?, ?, 'admin', 'active')
                ON CONFLICT(username) DO UPDATE SET
                    password_hash=excluded.password_hash,
                    role='admin', status='active', updated_at=CURRENT_TIMESTAMP
                """,
                (username, email, password_hash),
            )

    def _migrate_v1_admin_data(self) -> None:
        with self.connect() as con:
            migrated = con.execute(
                "SELECT value FROM app_metadata WHERE key='v1_admin_migrated'"
            ).fetchone()
            if migrated:
                return
            admin = con.execute("SELECT id FROM users WHERE role='admin' ORDER BY id LIMIT 1").fetchone()
            if not admin:
                return
            uid = int(admin[0])
            con.execute(
                "INSERT OR IGNORE INTO watchlist_v2(user_id,symbol,market,added_at) "
                "SELECT ?,symbol,market,added_at FROM watchlist",
                (uid,),
            )
            con.execute(
                "INSERT OR IGNORE INTO portfolio_positions_v2(user_id,symbol,market,qty,avg_price,updated_at) "
                "SELECT ?,symbol,market,qty,avg_price,updated_at FROM portfolio_positions",
                (uid,),
            )
            legacy_cash = con.execute("SELECT cash FROM paper_account WHERE id=1").fetchone()
            cash = float(legacy_cash[0]) if legacy_cash else settings.default_paper_cash
            con.execute(
                "INSERT OR IGNORE INTO paper_accounts_v2(user_id,cash) VALUES (?,?)",
                (uid, cash),
            )
            con.execute(
                "INSERT OR IGNORE INTO paper_positions_v2(user_id,symbol,market,qty,avg_price) "
                "SELECT ?,symbol,market,qty,avg_price FROM paper_positions",
                (uid,),
            )
            existing_orders = con.execute(
                "SELECT COUNT(*) FROM paper_orders_v2 WHERE user_id=?", (uid,)
            ).fetchone()[0]
            if not existing_orders:
                con.execute(
                    """INSERT INTO paper_orders_v2(user_id,symbol,market,side,qty,price,gross,fee,status,created_at)
                       SELECT ?,symbol,market,side,qty,price,gross,fee,status,created_at FROM paper_orders""",
                    (uid,),
                )
            con.execute(
                "INSERT OR REPLACE INTO app_metadata(key,value,updated_at) "
                "VALUES('v1_admin_migrated','1',CURRENT_TIMESTAMP)"
            )

    def register_user(
        self,
        username: str,
        email: str,
        password_hash: str,
        *,
        status: str = "active",
    ) -> dict[str, Any]:
        username = username.strip()
        email = email.strip().lower()
        with self.connect() as con:
            cur = con.execute(
                "INSERT INTO users(username,email,password_hash,role,status) VALUES (?,?,?,'user',?)",
                (username, email, password_hash, status),
            )
            uid = int(cur.lastrowid)
            con.execute(
                "INSERT INTO paper_accounts_v2(user_id,cash) VALUES (?,?)",
                (uid, settings.default_paper_cash),
            )
            con.execute(
                "INSERT INTO auth_audit(user_id,event,details) VALUES (?, 'REGISTER', ?)",
                (uid, f"status={status}"),
            )
        return self.get_user_by_id(uid) or {}

    def get_user_by_login(self, login: str) -> dict[str, Any] | None:
        value = login.strip()
        with self.connect() as con:
            row = con.execute(
                "SELECT * FROM users WHERE username=? COLLATE NOCASE OR email=? COLLATE NOCASE LIMIT 1",
                (value, value),
            ).fetchone()
            return dict(row) if row else None

    def get_user_by_id(self, user_id: int) -> dict[str, Any] | None:
        with self.connect() as con:
            row = con.execute("SELECT * FROM users WHERE id=?", (int(user_id),)).fetchone()
            return dict(row) if row else None

    def list_users(self) -> list[dict[str, Any]]:
        with self.connect() as con:
            return [
                dict(r)
                for r in con.execute(
                    "SELECT id,username,email,role,status,created_at,last_login_at FROM users ORDER BY id"
                )
            ]

    def update_last_login(self, user_id: int) -> None:
        with self.connect() as con:
            con.execute("UPDATE users SET last_login_at=CURRENT_TIMESTAMP WHERE id=?", (int(user_id),))
            con.execute("INSERT INTO auth_audit(user_id,event) VALUES (?, 'LOGIN')", (int(user_id),))

    def update_password(self, user_id: int, password_hash: str) -> None:
        with self.connect() as con:
            con.execute(
                "UPDATE users SET password_hash=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (password_hash, int(user_id)),
            )
            con.execute("INSERT INTO auth_audit(user_id,event) VALUES (?, 'PASSWORD_CHANGE')", (int(user_id),))

    def create_password_reset_token(self, user_id: int, ttl_minutes: int = 30) -> str:
        """Create a single-use password reset code. The plaintext code is returned once.

        Only a SHA-256 digest is stored in SQLite. Existing unused codes for the user
        are invalidated when a new one is issued.
        """
        uid = int(user_id)
        ttl = max(5, min(int(ttl_minutes), 120))
        token = secrets.token_urlsafe(9)
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        with self.connect() as con:
            con.execute(
                "UPDATE password_reset_tokens SET used_at=CURRENT_TIMESTAMP "
                "WHERE user_id=? AND used_at IS NULL",
                (uid,),
            )
            con.execute(
                "INSERT INTO password_reset_tokens(user_id,token_hash,expires_at) "
                "VALUES (?,?,datetime('now', ?))",
                (uid, digest, f"+{ttl} minutes"),
            )
            con.execute(
                "INSERT INTO auth_audit(user_id,event,details) VALUES (?, 'RESET_TOKEN_ISSUED', ?)",
                (uid, f"ttl_minutes={ttl}"),
            )
        return token

    def reset_password_with_token(self, login: str, token: str, password_hash: str) -> bool:
        user = self.get_user_by_login(login)
        if not user or not token.strip():
            return False
        uid = int(user["id"])
        digest = hashlib.sha256(token.strip().encode("utf-8")).hexdigest()
        with self.connect() as con:
            row = con.execute(
                """SELECT id FROM password_reset_tokens
                   WHERE user_id=? AND token_hash=? AND used_at IS NULL
                     AND expires_at > CURRENT_TIMESTAMP
                   ORDER BY id DESC LIMIT 1""",
                (uid, digest),
            ).fetchone()
            if not row:
                return False
            con.execute(
                "UPDATE users SET password_hash=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (password_hash, uid),
            )
            con.execute(
                "UPDATE password_reset_tokens SET used_at=CURRENT_TIMESTAMP WHERE id=?",
                (int(row[0]),),
            )
            con.execute(
                "INSERT INTO auth_audit(user_id,event) VALUES (?, 'PASSWORD_RESET')",
                (uid,),
            )
        return True

    def set_user_status(self, user_id: int, status: str) -> None:
        if status not in {"active", "pending", "disabled"}:
            raise ValueError("Invalid user status")
        with self.connect() as con:
            con.execute(
                "UPDATE users SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (status, int(user_id)),
            )

    def set_user_role(self, user_id: int, role: str) -> None:
        if role not in {"admin", "user"}:
            raise ValueError("Invalid role")
        with self.connect() as con:
            con.execute(
                "UPDATE users SET role=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (role, int(user_id)),
            )

    def auth_stats(self) -> dict[str, int]:
        with self.connect() as con:
            total = int(con.execute("SELECT COUNT(*) FROM users").fetchone()[0])
            active = int(con.execute("SELECT COUNT(*) FROM users WHERE status='active'").fetchone()[0])
            pending = int(con.execute("SELECT COUNT(*) FROM users WHERE status='pending'").fetchone()[0])
            return {"total": total, "active": active, "pending": pending}


    def save_final_decision_bundle(
        self,
        symbol: str,
        market: str,
        bundle: FinalDecisionBundle,
    ) -> None:
        payload = pickle.dumps(
            bundle.to_dict(),
            protocol=pickle.HIGHEST_PROTOCOL,
        )

        with self.connect() as con:
            con.execute(
                """
                INSERT INTO final_decision_bundles(
                    user_id,
                    symbol,
                    market,
                    payload,
                    updated_at
                )
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id, symbol, market)
                DO UPDATE SET
                    payload=excluded.payload,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    self._uid(),
                    symbol.upper(),
                    market.upper(),
                    payload,
                ),
            )

    def load_final_decision_bundle(
        self,
        symbol: str,
        market: str,
    ) -> FinalDecisionBundle | None:
        with self.connect() as con:
            row = con.execute(
                """
                SELECT payload
                FROM final_decision_bundles
                WHERE user_id=?
                  AND symbol=?
                  AND market=?
                LIMIT 1
                """,
                (
                    self._uid(),
                    symbol.upper(),
                    market.upper(),
                ),
            ).fetchone()

        if row is None:
            return None

        payload = pickle.loads(
            row["payload"]
        )

        return self.reconstruct_final_decision_bundle(
            payload
        )

    @staticmethod
    def reconstruct_final_decision_bundle(
        payload: dict[str, object],
    ) -> FinalDecisionBundle:
        """Reconstruct a persisted final decision bundle."""
        if not isinstance(payload, dict):
            raise TypeError("bundle payload must be a dict")

        return FinalDecisionBundle.from_dict(payload)

    # ---------- current user workspace ----------
    def _uid(self) -> int:
        if self.user_id is None:
            raise ValueError("A user_id is required for this operation")
        return self.user_id

    def _ensure_paper_account(self, con: sqlite3.Connection) -> None:
        con.execute(
            "INSERT OR IGNORE INTO paper_accounts_v2(user_id,cash) VALUES (?,?)",
            (self._uid(), settings.default_paper_cash),
        )

    def get_watchlist(self):
        uid = self._uid()
        with self.connect() as con:
            return [dict(r) for r in con.execute(
                "SELECT symbol,market,added_at FROM watchlist_v2 WHERE user_id=? ORDER BY market,symbol", (uid,)
            )]

    def add_watchlist(self, symbol, market):
        with self.connect() as con:
            con.execute(
                "INSERT OR IGNORE INTO watchlist_v2(user_id,symbol,market) VALUES (?,?,?)",
                (self._uid(), symbol.upper(), market.upper()),
            )

    def remove_watchlist(self, symbol, market):
        with self.connect() as con:
            con.execute(
                "DELETE FROM watchlist_v2 WHERE user_id=? AND symbol=? AND market=?",
                (self._uid(), symbol.upper(), market.upper()),
            )

    def upsert_portfolio(self, symbol, market, qty, avg_price):
        uid = self._uid()
        with self.connect() as con:
            if qty <= 0:
                con.execute(
                    "DELETE FROM portfolio_positions_v2 WHERE user_id=? AND symbol=? AND market=?",
                    (uid, symbol.upper(), market.upper()),
                )
            else:
                con.execute(
                    """INSERT INTO portfolio_positions_v2(user_id,symbol,market,qty,avg_price,updated_at)
                       VALUES (?,?,?,?,?,CURRENT_TIMESTAMP)
                       ON CONFLICT(user_id,symbol,market) DO UPDATE SET
                       qty=excluded.qty, avg_price=excluded.avg_price, updated_at=CURRENT_TIMESTAMP""",
                    (uid, symbol.upper(), market.upper(), qty, avg_price),
                )

    def get_portfolio(self):
        with self.connect() as con:
            return [dict(r) for r in con.execute(
                "SELECT symbol,market,qty,avg_price,updated_at FROM portfolio_positions_v2 "
                "WHERE user_id=? ORDER BY market,symbol", (self._uid(),)
            )]

    def reset_paper(self, cash):
        uid = self._uid()
        with self.connect() as con:
            self._ensure_paper_account(con)
            con.execute("DELETE FROM paper_positions_v2 WHERE user_id=?", (uid,))
            con.execute("DELETE FROM paper_orders_v2 WHERE user_id=?", (uid,))
            con.execute(
                "UPDATE paper_accounts_v2 SET cash=?, updated_at=CURRENT_TIMESTAMP WHERE user_id=?",
                (cash, uid),
            )

    def get_paper_order(self, order_id: int):
        """Return one durable paper order owned by this Storage user."""
        if self.user_id is None:
            return None

        with self.connect() as conn:
            row = conn.execute(
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
                    created_at
                FROM paper_orders_v2
                WHERE user_id = ?
                  AND id = ?
                LIMIT 1
                """,
                (self.user_id, order_id),
            ).fetchone()

        if row is None:
            return None

        return dict(row)

    def list_paper_orders(self):
        """Return all durable paper orders owned by this Storage user."""
        if self.user_id is None:
            return []

        with self.connect() as conn:
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
                    created_at
                FROM paper_orders_v2
                WHERE user_id = ?
                ORDER BY id DESC
                """,
                (self.user_id,),
            ).fetchall()

        return [dict(row) for row in rows]


    def paper_snapshot(self):
        uid = self._uid()
        with self.connect() as con:
            self._ensure_paper_account(con)
            cash = float(con.execute("SELECT cash FROM paper_accounts_v2 WHERE user_id=?", (uid,)).fetchone()[0])
            positions = [dict(r) for r in con.execute(
                "SELECT symbol,market,qty,avg_price FROM paper_positions_v2 WHERE user_id=? ORDER BY market,symbol", (uid,)
            )]
            orders = [dict(r) for r in con.execute(
                "SELECT id,symbol,market,side,qty,price,gross,fee,status,created_at "
                "FROM paper_orders_v2 WHERE user_id=? ORDER BY id DESC LIMIT 200", (uid,)
            )]
            return {"cash": cash, "positions": positions, "orders": orders}

    def execute_paper_order(
        self,
        symbol,
        market,
        side,
        qty,
        price,
        fee_bps=15.0,
        idempotency_key=None,
    ):
        uid = self._uid()
        symbol, market, side = symbol.upper(), market.upper(), side.upper()

        if qty <= 0 or price <= 0 or side not in {"BUY", "SELL"}:
            raise ValueError("Invalid paper order")

        if idempotency_key is not None:
            idempotency_key = str(idempotency_key).strip()
            if not idempotency_key:
                raise ValueError("idempotency_key must not be empty")

        gross = qty * price
        fee = gross * fee_bps / 10000.0

        with self.connect() as con:
            self._ensure_paper_account(con)

            if idempotency_key is not None:
                existing = con.execute(
                    """SELECT id,symbol,market,side,qty,price,fee,status
                       FROM paper_orders_v2
                       WHERE user_id=? AND idempotency_key=?""",
                    (uid, idempotency_key),
                ).fetchone()

                if existing is not None:
                    return {
                        "order_id": int(existing["id"]),
                        "symbol": existing["symbol"],
                        "market": existing["market"],
                        "side": existing["side"],
                        "qty": existing["qty"],
                        "price": existing["price"],
                        "fee": existing["fee"],
                        "status": existing["status"],
                    }

            cash = float(
                con.execute(
                    "SELECT cash FROM paper_accounts_v2 WHERE user_id=?",
                    (uid,),
                ).fetchone()[0]
            )

            row = con.execute(
                """SELECT qty,avg_price
                   FROM paper_positions_v2
                   WHERE user_id=? AND symbol=? AND market=?""",
                (uid, symbol, market),
            ).fetchone()

            old_qty = float(row[0]) if row else 0.0
            old_avg = float(row[1]) if row else 0.0

            if side == "BUY":
                total = gross + fee

                if total > cash:
                    raise ValueError("Insufficient paper cash")

                new_qty = old_qty + qty
                new_avg = ((old_qty * old_avg) + gross) / new_qty

                con.execute(
                    """UPDATE paper_accounts_v2
                       SET cash=cash-?,updated_at=CURRENT_TIMESTAMP
                       WHERE user_id=?""",
                    (total, uid),
                )

                con.execute(
                    """INSERT INTO paper_positions_v2(
                           user_id,symbol,market,qty,avg_price
                       )
                       VALUES (?,?,?,?,?)
                       ON CONFLICT(user_id,symbol,market)
                       DO UPDATE SET
                           qty=excluded.qty,
                           avg_price=excluded.avg_price""",
                    (uid, symbol, market, new_qty, new_avg),
                )

            else:
                if qty > old_qty:
                    raise ValueError("Insufficient paper position")

                new_qty = old_qty - qty

                con.execute(
                    """UPDATE paper_accounts_v2
                       SET cash=cash+?,updated_at=CURRENT_TIMESTAMP
                       WHERE user_id=?""",
                    (gross - fee, uid),
                )

                if new_qty <= 1e-12:
                    con.execute(
                        """DELETE FROM paper_positions_v2
                           WHERE user_id=? AND symbol=? AND market=?""",
                        (uid, symbol, market),
                    )
                else:
                    con.execute(
                        """UPDATE paper_positions_v2
                           SET qty=?
                           WHERE user_id=? AND symbol=? AND market=?""",
                        (new_qty, uid, symbol, market),
                    )

            order_cur = con.execute(
                """INSERT INTO paper_orders_v2(
                       user_id,
                       symbol,
                       market,
                       side,
                       qty,
                       price,
                       gross,
                       fee,
                       status,
                       idempotency_key
                   )
                   VALUES (?,?,?,?,?,?,?,?, 'FILLED', ?)""",
                (
                    uid,
                    symbol,
                    market,
                    side,
                    qty,
                    price,
                    gross,
                    fee,
                    idempotency_key,
                ),
            )

            order_id = int(order_cur.lastrowid)

        return {
            "order_id": order_id,
            "symbol": symbol,
            "market": market,
            "side": side,
            "qty": qty,
            "price": price,
            "fee": fee,
            "status": "FILLED",
        }
