import streamlit as st

from market_intelligence.services import scan_symbols, provider
from ui.auth import current_user, user_storage

user = current_user()
s = user_storage()
w = s.get_watchlist()
p = s.get_portfolio()
paper = s.paper_snapshot()

st.markdown(
    f"""
    <div class="hero-card">
      <div class="hero-chip">MARKET INTELLIGENCE V4</div>
      <h1>Welcome back, {user.get('username','Investor')}</h1>
      <p>One workspace for market research, strategy validation and paper trading across Thai and US equities.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

metrics = [
    ("Watchlist", len(w), "symbols followed"),
    ("Portfolio", len(p), "tracked positions"),
    ("Paper cash", f"{paper['cash']:,.2f}", "simulation balance"),
    ("Paper positions", len(paper["positions"]), "open simulations"),
]
for col, (label, val, help_text) in zip(st.columns(4), metrics):
    col.metric(label, val, help=help_text)

st.write("")
left, right = st.columns([1.75, 1], gap="large")
with left:
    st.markdown('<div class="panel-title">Quick market scan</div>', unsafe_allow_html=True)
    market = st.segmented_control("Market", ["TH", "US"], default="TH", label_visibility="collapsed")
    default = "SNC,PTT,ADVANC,CPALL,DELTA" if market == "TH" else "AAPL,MSFT,NVDA,AMZN,META"
    symbols = st.text_input("Symbols", default, help="Comma-separated symbols. Thai tickers automatically use .BK.")
    a, b = st.columns([1, 1])
    run = a.button("Run scan", type="primary", width="stretch")
    if b.button("Refresh market data", width="stretch"):
        provider.clear_cache()
        st.toast("Market-data cache cleared")
    if run:
        with st.spinner("Loading market data..."):
            st.dataframe(
                scan_symbols([x.strip() for x in symbols.split(",") if x.strip()], market),
                width="stretch",
                hide_index=True,
            )
with right:
    st.markdown('<div class="panel-title">V4 workspace</div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="feature-card"><b>🔎 Analyze</b><br><span>Candlestick, trend, momentum, support/resistance and trade-plan calculations.</span></div><br>
        <div class="feature-card"><b>🧪 Validate</b><br><span>Backtest and Strategy Lab before relying on a trading setup.</span></div><br>
        <div class="feature-card"><b>📝 Simulate</b><br><span>Each user now has an isolated paper-trading portfolio and watchlist.</span></div>
        """,
        unsafe_allow_html=True,
    )

st.caption("V4 • Responsive multi-user workspace • PBKDF2 password hashing • Persistent user data • Railway health monitoring")
