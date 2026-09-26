import streamlit as st
from market_intelligence.portfolio.service import mark_to_market
from ui.auth import user_storage

st.title("💼 Portfolio")
st.caption("Your private position tracker. Data is isolated per account.")
s = user_storage()
a, b, c, d = st.columns(4)
market = a.selectbox("Market", ["TH", "US"])
symbol = b.text_input("Symbol")
qty = c.number_input("Quantity", 0.0, 1e8, 0.0)
avg = d.number_input("Average cost", 0.0, 1e8, 0.0)

c1, c2 = st.columns(2)
if c1.button("Save position", type="primary", width="stretch") and symbol:
    s.upsert_portfolio(symbol, market, qty, avg)
    st.toast("Position saved")
    st.rerun()
refresh = c2.button("Refresh market values", width="stretch")

st.subheader("Positions")
if refresh:
    st.dataframe(mark_to_market(s), width="stretch", hide_index=True)
else:
    st.dataframe(s.get_portfolio(), width="stretch", hide_index=True)
