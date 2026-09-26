import streamlit as st

from market_intelligence.security import hash_password, verify_password
from market_intelligence.storage import Storage
from ui.auth import current_user, clear_session

user = current_user()
st.title("👤 Profile & Security")
st.caption("Manage your account and password.")

storage = Storage()
fresh = storage.get_user_by_id(user["id"]) or user
c1, c2, c3 = st.columns(3)
c1.metric("Username", fresh.get("username", ""))
c2.metric("Role", str(fresh.get("role", "user")).upper())
c3.metric("Status", str(fresh.get("status", "active")).upper())
st.text_input("Email", fresh.get("email", ""), disabled=True)

st.divider()
st.subheader("Change password")
with st.form("change_password"):
    current = st.text_input("Current password", type="password")
    new = st.text_input("New password", type="password")
    confirm = st.text_input("Confirm new password", type="password")
    submit = st.form_submit_button("Update password", type="primary")
if submit:
    if not verify_password(current, fresh.get("password_hash", "")):
        st.error("Current password is incorrect.")
    elif len(new) < 10 or not any(ch.isalpha() for ch in new) or not any(ch.isdigit() for ch in new):
        st.error("New password must be at least 10 characters and contain a letter and a number.")
    elif new != confirm:
        st.error("New passwords do not match.")
    else:
        storage.update_password(user["id"], hash_password(new))
        st.success("Password updated. Please sign in again.")
        clear_session()
        st.rerun()
