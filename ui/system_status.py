from __future__ import annotations

import os
from pathlib import Path
import streamlit as st

from market_intelligence.storage import Storage
from ui.auth import is_admin

if not is_admin():
    st.error("Administrator access required.")
    st.stop()

st.title("🛡️ System Status")
st.caption("Runtime checks for V2 authentication, persistent storage and market-data configuration.")
checks = []

def add_check(name: str, ok: bool, details: str):
    checks.append({"check": name, "status": "OK" if ok else "ERROR", "details": details})

try:
    storage = Storage()
    db_path = Path(storage.path)
    with storage.connect() as con:
        con.execute("CREATE TABLE IF NOT EXISTS system_health (id INTEGER PRIMARY KEY CHECK(id=1), checked_at TEXT)")
        con.execute("INSERT INTO system_health(id,checked_at) VALUES (1,CURRENT_TIMESTAMP) ON CONFLICT(id) DO UPDATE SET checked_at=CURRENT_TIMESTAMP")
        row = con.execute("SELECT checked_at FROM system_health WHERE id=1").fetchone()
        mode = con.execute("PRAGMA journal_mode").fetchone()[0]
    add_check("Persistent database", bool(row), f"SQLite: {db_path} • journal={mode}")
except Exception as exc:
    add_check("Persistent database", False, str(exc))

stats = Storage().auth_stats()
add_check("V2 authentication", stats["total"] >= 1, f"Users={stats['total']} • Active={stats['active']} • Pending={stats['pending']}")
add_check("Admin bootstrap", bool(os.getenv("APP_LOGIN_PASSWORD_HASH")), "PBKDF2 admin credential configured")
add_check("Registration", True, f"Mode: {os.getenv('REGISTRATION_MODE','open')}")
provider = os.getenv("MARKET_DATA_PROVIDER", "Yahoo Finance")
add_check("Market data", bool(provider), provider)

st.dataframe(checks, width="stretch", hide_index=True)
st.info("Railway checks /_stcore/health. External uptime monitoring also checks the public URL once per hour.")
