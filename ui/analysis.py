import streamlit as st

from market_intelligence.services import analyze_symbol_v4
from ui.common import price_chart
from ui.web_shell import is_mobile_mode

st.title("🔎 Stock Analysis")
st.caption("V4 responsive workspace • Multi-timeframe analytics • Short-term trade zones on chart")

mobile = is_mobile_mode()
if mobile:
    market = st.selectbox("Market", ["TH", "US"])
    symbol = st.text_input("Symbol", "SNC" if market == "TH" else "AAPL").strip().upper()
    period = st.segmented_control("Analysis window", ["1D", "7D", "1M", "6M", "1Y", "2Y"], default="7D", selection_mode="single") or "7D"
    profile_label = st.segmented_control("Trading style", ["Intraday", "Swing", "Position"], default="Intraday", selection_mode="single") or "Intraday"
else:
    row1 = st.columns([1.0, 1.1, 2.6, 2.1])
    market = row1[0].selectbox("Market", ["TH", "US"])
    symbol = row1[1].text_input("Symbol", "SNC" if market == "TH" else "AAPL").strip().upper()
    with row1[2]:
        period = st.segmented_control("Analysis window", ["1D", "7D", "1M", "6M", "1Y", "2Y"], default="7D", selection_mode="single") or "7D"
    with row1[3]:
        profile_label = st.segmented_control("Trading style", ["Intraday", "Swing", "Position"], default="Intraday", selection_mode="single") or "Intraday"

profile = profile_label.upper()
if mobile:
    equity = st.number_input("Portfolio equity", 10_000.0, 1e9, 1_000_000.0, step=10_000.0)
    risk = st.slider("Risk / trade (%)", .1, 5.0, 1.0, .1)
else:
    row2 = st.columns([1.3, 1.3, 2.4])
    equity = row2[0].number_input("Portfolio equity", 10_000.0, 1e9, 1_000_000.0, step=10_000.0)
    risk = row2[1].slider("Risk / trade (%)", .1, 5.0, 1.0, .1)
    row2[2].info("Short-term: 1D=5m, 7D=30m, 1M=1h. Intraday profile uses tighter ATR risk/target bands.")

st.markdown(
    "<div class='trade-note'><b>Short-term mode:</b> Green box = potential Buy Zone, cyan/blue boxes = TP1/TP2, red box = Stop/Exit. Wait for the Buy Trigger confirmation when the regime says WAIT FOR CONFIRMATION.</div>",
    unsafe_allow_html=True,
)

if st.button("Analyze market", type="primary", width="stretch"):
    try:
        with st.spinner(f"Analyzing {symbol} • {period} • {profile_label}..."):
            df, plan, guide = analyze_symbol_v4(symbol, market, period=period, equity=equity, risk_pct=risk, trading_profile=profile)

        st.plotly_chart(price_chart(df, f"{symbol} • {market} • {period} • {guide.profile_label}", guide, compact=mobile), width="stretch")

        metric_data = [
            ("Technical score", f"{plan.score}/100"), ("Trend", plan.trend), ("Signal", plan.signal),
            ("RSI", f"{df.iloc[-1]['RSI14']:.1f}"), ("Confidence", f"{guide.confidence}/100"),
        ]
        cols = st.columns(2 if mobile else 5)
        for idx, (label, value) in enumerate(metric_data):
            cols[idx % len(cols)].metric(label, value)

        st.markdown("### Trade Map")
        st.caption(f"{guide.profile_label} profile • {guide.holding_note}")
        guidance_metrics = [
            ("Buy trigger", f"{guide.buy_trigger:,.4f}"),
            ("Buy zone", f"{guide.buy_zone_low:,.4f} – {guide.buy_zone_high:,.4f}"),
            ("TP1", f"{guide.sell_tp1:,.4f}"),
            ("TP2", f"{guide.sell_tp2:,.4f}"),
            ("Stop", f"{guide.stop_loss:,.4f}"),
        ]
        cols = st.columns(2 if mobile else 5)
        for idx, (label, value) in enumerate(guidance_metrics):
            cols[idx % len(cols)].metric(label, value)

        secondary = [
            ("Support", f"{guide.support:,.4f}"), ("Resistance", f"{guide.resistance:,.4f}"),
            ("Risk / Reward", f"{plan.risk_reward:.2f}"), ("Position qty", f"{plan.position_qty:,}"),
        ]
        cols = st.columns(2 if mobile else 4)
        for idx, (label, value) in enumerate(secondary):
            cols[idx % len(cols)].metric(label, value)

        with st.expander("How V4 calculated these levels", expanded=False):
            st.write(f"**Regime:** {guide.regime}")
            for item in guide.rationale:
                st.write(f"• {item}")
            st.write("**Strategy conditions**", plan.conditions)
            st.write("**Score components**", plan.score_parts)
            st.warning("Technical Guidance is a rule-based research aid from historical market data. It is not a guarantee, personalized investment advice, or an instruction to place a live order.")
    except Exception as exc:
        st.error(str(exc))
