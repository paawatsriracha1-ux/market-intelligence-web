import streamlit as st
from ui.auth import user_storage

st.title("⭐ Watchlist")
st.caption("Track symbols in your own private workspace.")
s = user_storage()
a, b, c = st.columns([1, 2, 1])
market = a.selectbox("Market", ["TH", "US"])
symbol = b.text_input("Symbol")
if c.button("Add symbol", type="primary", width="stretch") and symbol:
    s.add_watchlist(symbol, market)
    st.toast("Added to watchlist")
    st.rerun()

rows = s.get_watchlist()
st.dataframe(rows, width="stretch", hide_index=True)
if rows:
    c1, c2 = st.columns([3, 1])
    sel = c1.selectbox("Remove", [f"{r['market']}:{r['symbol']}" for r in rows])
    if c2.button("Remove selected", width="stretch"):
        m, x = sel.split(":", 1)
        s.remove_watchlist(x, m)
        st.rerun()
