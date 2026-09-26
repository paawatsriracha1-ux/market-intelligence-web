import streamlit as st
from market_intelligence.services import analyze_symbol
from ui.auth import user_storage

st.title("📝 Paper Trading")
st.caption("Simulate trades without sending orders to a live broker.")
s = user_storage()
snap = s.paper_snapshot()

m1, m2 = st.columns(2)
m1.metric("Paper cash", f"{snap['cash']:,.2f}")
m2.metric("Open positions", len(snap["positions"]))

a, b, c, d = st.columns(4)
market = a.selectbox("Market", ["TH", "US"])
symbol = b.text_input("Symbol", "SNC" if market == "TH" else "AAPL")
side = c.selectbox("Side", ["BUY", "SELL"])
qty = d.number_input("Quantity", 1.0, 1e8, 100.0 if market == "TH" else 1.0)
use_live = st.checkbox("Use latest market close", True)
price = st.number_input("Manual execution price", 0.0001, 1e8, 1.0)

if st.button("Execute paper order", type="primary"):
    try:
        px = price
        if use_live:
            df, _ = analyze_symbol(symbol, market, period="1mo")
            px = float(df.iloc[-1]["Close"])
        s.execute_paper_order(symbol, market, side, qty, px)
        st.success(f"Paper order filled at {px:,.4f}")
        st.rerun()
    except Exception as e:
        st.error(str(e))

st.subheader("Positions")
st.dataframe(s.paper_snapshot()["positions"], width="stretch", hide_index=True)
st.subheader("Recent orders")
st.dataframe(s.paper_snapshot()["orders"], width="stretch", hide_index=True)

with st.expander("Reset paper account"):
    reset_cash = st.number_input("New paper cash", min_value=0.0, value=1_000_000.0, step=100_000.0)
    if st.button("Reset simulation", type="secondary"):
        s.reset_paper(reset_cash)
        st.success("Paper account reset")
        st.rerun()
