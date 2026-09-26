from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from market_intelligence.storage import Storage
from ui.auth import current_user, is_admin, logout_button, require_login
from ui.web_shell import apply_web_shell

st.set_page_config(
    page_title="Market Intelligence V4",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_web_shell()
Storage()  # schema migration + admin bootstrap

if not require_login():
    st.stop()

logout_button()

sections = {
    "Overview": [
        st.Page("ui/dashboard.py", title="Dashboard", icon="📊", default=True),
        st.Page("ui/analysis.py", title="Stock Analysis", icon="🔎"),
        st.Page("ui/scanner.py", title="Market Scanner", icon="🧭"),
    ],
    "Research": [
        st.Page("ui/backtest.py", title="Backtest", icon="🧪"),
        st.Page("ui/strategy_lab.py", title="Strategy Lab", icon="⚙️"),
    ],
    "My Workspace": [
        st.Page("ui/watchlist.py", title="Watchlist", icon="⭐"),
        st.Page("ui/portfolio.py", title="Portfolio", icon="💼"),
        st.Page("ui/paper_trading.py", title="Paper Trading", icon="📝"),
        st.Page("ui/profile.py", title="Profile & Security", icon="👤"),
    ],
}
if is_admin():
    sections["Administration"] = [
        st.Page("ui/user_management.py", title="User Management", icon="👥"),
        st.Page("ui/system_status.py", title="System Status", icon="🛡️"),
    ]

st.navigation(sections, position="sidebar").run()
