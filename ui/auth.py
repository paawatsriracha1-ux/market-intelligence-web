from __future__ import annotations

import os
import re
import sqlite3
import time

import streamlit as st

from market_intelligence.security import hash_password, verify_password
from market_intelligence.storage import Storage

MAX_ATTEMPTS = 5
LOCKOUT_SECONDS = 15 * 60
SESSION_SECONDS = 12 * 60 * 60
USERNAME_RE = re.compile(r"^[A-Za-z0-9._-]{3,32}$")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _registration_mode() -> str:
    return os.getenv("REGISTRATION_MODE", "open").strip().lower() or "open"


def _session_valid() -> bool:
    if st.session_state.get("authenticated") is not True:
        return False
    authenticated_at = float(st.session_state.get("authenticated_at", 0.0))
    if time.time() - authenticated_at > SESSION_SECONDS:
        clear_session()
        return False
    uid = st.session_state.get("authenticated_user_id")
    if not uid:
        clear_session()
        return False
    user = Storage().get_user_by_id(int(uid))
    if not user or user.get("status") != "active":
        clear_session()
        return False
    return True


def clear_session() -> None:
    for key in (
        "authenticated", "authenticated_at", "authenticated_user_id",
        "authenticated_user", "authenticated_email", "authenticated_role",
    ):
        st.session_state.pop(key, None)


def current_user() -> dict:
    if not _session_valid():
        return {}
    return {
        "id": int(st.session_state["authenticated_user_id"]),
        "username": st.session_state.get("authenticated_user", ""),
        "email": st.session_state.get("authenticated_email", ""),
        "role": st.session_state.get("authenticated_role", "user"),
    }


def user_storage() -> Storage:
    user = current_user()
    if not user:
        raise RuntimeError("User is not authenticated")
    return Storage(user_id=int(user["id"]))


def is_admin() -> bool:
    return current_user().get("role") == "admin"


def _set_session(user: dict) -> None:
    now = time.time()
    st.session_state["authenticated"] = True
    st.session_state["authenticated_at"] = now
    st.session_state["authenticated_user_id"] = int(user["id"])
    st.session_state["authenticated_user"] = user["username"]
    st.session_state["authenticated_email"] = user["email"]
    st.session_state["authenticated_role"] = user["role"]
    st.session_state["login_attempts"] = 0
    st.session_state.pop("login_locked_until", None)


def _password_error(password: str) -> str | None:
    if len(password) < 10:
        return "Password must contain at least 10 characters."
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        return "Password must contain at least one letter and one number."
    return None


def _login_panel(storage: Storage) -> None:
    now = time.time()
    locked_until = float(st.session_state.get("login_locked_until", 0.0))
    if locked_until > now:
        remaining = max(1, int((locked_until - now) // 60) + 1)
        st.error(f"Too many failed attempts. Try again in about {remaining} minute(s).")
        return

    with st.form("v4_login_form", clear_on_submit=False):
        login = st.text_input("Username or email", placeholder="username@example.com", autocomplete="username")
        password = st.text_input("Password", type="password", autocomplete="current-password")
        submitted = st.form_submit_button("Sign in", type="primary", width="stretch")
    if submitted:
        user = storage.get_user_by_login(login)
        ok = bool(user and verify_password(password, str(user.get("password_hash", ""))))
        if ok and user.get("status") == "active":
            storage.update_last_login(int(user["id"]))
            _set_session(user)
            st.rerun()
        if ok and user.get("status") == "pending":
            st.warning("Your account is waiting for administrator approval.")
            return
        if ok and user.get("status") == "disabled":
            st.error("This account has been disabled. Please contact the administrator.")
            return
        attempts = int(st.session_state.get("login_attempts", 0)) + 1
        st.session_state["login_attempts"] = attempts
        if attempts >= MAX_ATTEMPTS:
            st.session_state["login_locked_until"] = now + LOCKOUT_SECONDS
            st.session_state["login_attempts"] = 0
            st.error("Too many failed attempts. Login is temporarily locked for 15 minutes.")
        else:
            st.error(f"Incorrect username/email or password. {MAX_ATTEMPTS - attempts} attempt(s) remaining.")


def _signup_panel(storage: Storage) -> None:
    mode = _registration_mode()
    if mode == "closed":
        st.info("New account registration is currently closed.")
        return
    with st.form("v4_signup_form", clear_on_submit=False):
        username = st.text_input("Username", placeholder="3–32 letters, numbers, . _ -")
        email = st.text_input("Email", placeholder="name@example.com")
        password = st.text_input("Create password", type="password", autocomplete="new-password")
        confirm = st.text_input("Confirm password", type="password", autocomplete="new-password")
        agree = st.checkbox("I agree to use this system for research and paper trading purposes.")
        submitted = st.form_submit_button("Create account", type="primary", width="stretch")
    if submitted:
        username = username.strip()
        email = email.strip().lower()
        if not USERNAME_RE.fullmatch(username):
            st.error("Username must be 3–32 characters and may contain letters, numbers, dot, underscore or hyphen.")
            return
        if not EMAIL_RE.fullmatch(email):
            st.error("Please enter a valid email address.")
            return
        err = _password_error(password)
        if err:
            st.error(err); return
        if password != confirm:
            st.error("Passwords do not match."); return
        if not agree:
            st.error("Please accept the usage acknowledgement before creating an account."); return
        status = "pending" if mode == "approval" else "active"
        try:
            storage.register_user(username, email, hash_password(password), status=status)
        except sqlite3.IntegrityError:
            st.error("That username or email is already registered."); return
        if status == "pending":
            st.success("Account created. An administrator must approve it before you can sign in.")
        else:
            st.success("Account created successfully. You can sign in now.")


def _reset_panel(storage: Storage) -> None:
    st.caption("Forgot your password? Ask an administrator for a one-time reset code. Codes expire after 30 minutes.")
    with st.form("v4_reset_form", clear_on_submit=False):
        login = st.text_input("Username or email", key="reset_login")
        token = st.text_input("Reset code", key="reset_code")
        password = st.text_input("New password", type="password", autocomplete="new-password", key="reset_new")
        confirm = st.text_input("Confirm new password", type="password", autocomplete="new-password", key="reset_confirm")
        submitted = st.form_submit_button("Reset password", type="primary", width="stretch")
    if submitted:
        err = _password_error(password)
        if err:
            st.error(err); return
        if password != confirm:
            st.error("Passwords do not match."); return
        if storage.reset_password_with_token(login, token, hash_password(password)):
            st.success("Password reset successfully. You can now sign in with your new password.")
        else:
            st.error("Reset code is invalid, expired, or already used. Please request a new code from an administrator.")


def require_login() -> bool:
    storage = Storage()
    if _session_valid():
        return True
    st.markdown(
        """
        <div class="auth-hero">
          <div class="auth-kicker">MARKET INTELLIGENCE V4</div>
          <div class="auth-title">Research smarter. Validate every setup.</div>
          <div class="auth-subtitle">Thai + US equities • Multi-timeframe analytics • Backtest • Paper trading</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    left, center, right = st.columns([1.05, 1.55, 1.05])
    with center:
        login_tab, signup_tab, reset_tab = st.tabs(["Sign in", "Create account", "Reset password"])
        with login_tab: _login_panel(storage)
        with signup_tab: _signup_panel(storage)
        with reset_tab: _reset_panel(storage)
        st.caption("Passwords are stored as PBKDF2-SHA256 hashes. Reset codes are single-use and stored only as SHA-256 digests.")
    return False


def logout_button() -> None:
    if not _session_valid():
        return
    user = current_user()
    st.sidebar.markdown(
        f"<div class='user-chip'><b>{user.get('username','')}</b><br><span>{user.get('role','user').upper()}</span></div>",
        unsafe_allow_html=True,
    )
    if st.sidebar.button("Sign out", width="stretch", key="signout_v4"):
        clear_session(); st.rerun()
