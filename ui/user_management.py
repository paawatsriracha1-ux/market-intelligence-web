import pandas as pd
import streamlit as st

from market_intelligence.storage import Storage
from ui.auth import current_user, is_admin

if not is_admin():
    st.error("Administrator access required.")
    st.stop()

st.title("👥 User Management")
st.caption("Approve users, manage roles and issue secure one-time password reset codes.")

storage = Storage()
me = current_user()
users = storage.list_users()
stats = storage.auth_stats()
for col, item in zip(st.columns(3), [("Total users", stats["total"]), ("Active", stats["active"]), ("Pending", stats["pending"]) ]):
    col.metric(*item)

st.dataframe(pd.DataFrame(users), width="stretch", hide_index=True)
st.subheader("Manage account")
options = {f"{u['username']} · {u['email']} · #{u['id']}": u for u in users}
choice = st.selectbox("User", list(options.keys())) if options else None
if choice:
    target = options[choice]
    c1, c2 = st.columns(2)
    status = c1.selectbox("Status", ["active", "pending", "disabled"], index=["active","pending","disabled"].index(target["status"]))
    role = c2.selectbox("Role", ["user", "admin"], index=["user","admin"].index(target["role"]))
    a, b = st.columns(2)
    if a.button("Save user settings", type="primary", width="stretch"):
        if int(target["id"]) == int(me["id"]) and status != "active":
            st.error("You cannot disable your own active administrator session.")
        elif int(target["id"]) == int(me["id"]) and role != "admin":
            st.error("You cannot remove your own administrator role.")
        else:
            storage.set_user_status(int(target["id"]), status)
            storage.set_user_role(int(target["id"]), role)
            st.success("User settings updated.")
            st.rerun()
    if b.button("Generate password reset code", width="stretch"):
        code = storage.create_password_reset_token(int(target["id"]), ttl_minutes=30)
        st.success(f"One-time reset code generated for {target['username']}. It expires in 30 minutes.")
        st.code(code, language=None)
        st.warning("Copy this code now and send it to the user through a trusted channel. The plaintext code is not stored and cannot be displayed again.")

st.info("Users reset their password from the Reset password tab on the sign-in screen. Registration mode remains controlled by REGISTRATION_MODE: open, approval, or closed.")
