from __future__ import annotations

import os
import streamlit as st

UI_MODES = ["Auto", "Desktop", "Mobile"]


def get_ui_mode() -> str:
    return str(st.session_state.get("mi_ui_mode", "Auto"))


def is_mobile_mode() -> bool:
    return get_ui_mode() == "Mobile"


def _mode_css(mode: str) -> str:
    mobile_rules = """
      .block-container { max-width: 590px !important; padding-left:.72rem !important; padding-right:.72rem !important; padding-top:.72rem !important; }
      [data-testid="stHorizontalBlock"] { flex-wrap:wrap !important; gap:.65rem !important; }
      [data-testid="stColumn"] { min-width:100% !important; flex:1 1 100% !important; }
      [data-testid="stMetric"] { padding:.78rem .82rem !important; border-radius:14px !important; }
      [data-testid="stMetricValue"] { font-size:1.34rem !important; }
      .hero-card { border-radius:18px !important; padding:1rem 1.05rem !important; }
      .hero-card h1 { font-size:1.35rem !important; }
      .auth-title { font-size:1.65rem !important; }
      .auth-hero { margin:.5rem auto 1rem auto !important; }
      .feature-card { min-height:auto !important; }
      div[data-testid="stPlotlyChart"] { border-radius:14px !important; }
      button { min-height:44px !important; }
    """
    if mode == "Mobile":
        return mobile_rules
    if mode == "Desktop":
        return ".block-container { max-width:1480px !important; }"
    return f"@media (max-width: 768px) {{ {mobile_rules} }}"


def apply_web_shell() -> None:
    if "mi_ui_mode" not in st.session_state:
        st.session_state["mi_ui_mode"] = "Auto"
    mode = get_ui_mode()
    st.markdown(
        f"""
        <style>
        :root {{ --mi-green:#0f766e; --mi-dark:#0f172a; --mi-muted:#64748b; --mi-line:#e2e8f0; }}
        .stApp {{ background: linear-gradient(180deg,#f8fafc 0%,#f1f5f9 100%); }}
        .block-container {{ padding-top: 1.2rem; padding-bottom: 3rem; max-width: 1480px; }}
        [data-testid="stSidebar"] {{ background:#ffffff; border-right:1px solid #e5e7eb; }}
        [data-testid="stSidebar"] .block-container {{ padding-top:.8rem; }}
        h1,h2,h3 {{ letter-spacing:-.025em; color:#0f172a; }}
        p, label, [data-testid="stCaptionContainer"] {{ color:#475569; }}
        [data-testid="stMetric"] {{ background:rgba(255,255,255,.96); border:1px solid #e2e8f0; padding:1rem 1.05rem; border-radius:18px; box-shadow:0 8px 30px rgba(15,23,42,.045); }}
        [data-testid="stMetricValue"] {{ color:#0f172a; font-weight:760; }}
        div[data-testid="stDataFrame"], div[data-testid="stPlotlyChart"] {{ background:#fff; border:1px solid #e2e8f0; border-radius:18px; overflow:hidden; box-shadow:0 8px 30px rgba(15,23,42,.035); }}
        .stButton>button, .stFormSubmitButton>button {{ border-radius:12px; font-weight:650; min-height:42px; }}
        .stButton>button[kind="primary"], .stFormSubmitButton>button[kind="primary"] {{ background:linear-gradient(135deg,#0f766e,#0891b2); border:none; }}
        .brand-wrap {{ padding:.15rem .25rem .65rem .25rem; }}
        .brand-title {{ font-weight:800; font-size:1.16rem; letter-spacing:-.02em; color:#0f172a; }}
        .brand-sub {{ font-size:.77rem; color:#64748b; margin-top:.16rem; }}
        .v4-badge {{ display:inline-flex; padding:.18rem .48rem; border-radius:999px; background:#ccfbf1; color:#115e59; font-size:.68rem; font-weight:800; letter-spacing:.08em; margin-top:.48rem; }}
        .hero-card {{ background:linear-gradient(135deg,#0f172a 0%,#134e4a 58%,#0e7490 100%); color:white; border-radius:24px; padding:1.35rem 1.5rem; margin-bottom:1.05rem; box-shadow:0 16px 45px rgba(15,23,42,.14); }}
        .hero-card h1 {{ color:#fff; margin:0; font-size:1.9rem; }}
        .hero-card p {{ color:#dbeafe; margin:.5rem 0 0 0; }}
        .hero-chip {{ display:inline-flex; border:1px solid rgba(255,255,255,.22); background:rgba(255,255,255,.10); color:#ecfeff; padding:.28rem .6rem; border-radius:999px; font-size:.75rem; margin-bottom:.6rem; }}
        .panel-title {{ font-size:1.05rem; font-weight:750; color:#0f172a; margin:.2rem 0 .75rem 0; }}
        .user-chip {{ background:#f8fafc; border:1px solid #e2e8f0; padding:.72rem .8rem; border-radius:14px; margin:.55rem 0; color:#0f172a; }}
        .user-chip span {{ color:#0f766e; font-size:.68rem; font-weight:800; letter-spacing:.08em; }}
        .auth-hero {{ max-width:900px; margin:1.1rem auto 1.35rem auto; text-align:center; }}
        .auth-kicker {{ display:inline-flex; background:#ccfbf1; color:#115e59; font-size:.72rem; font-weight:800; letter-spacing:.12em; border-radius:999px; padding:.32rem .72rem; }}
        .auth-title {{ color:#0f172a; font-size:2.25rem; font-weight:850; letter-spacing:-.045em; margin:.72rem 0 .35rem 0; }}
        .auth-subtitle {{ color:#64748b; font-size:1rem; }}
        .feature-card {{ background:#fff; border:1px solid #e2e8f0; border-radius:18px; padding:1rem 1.05rem; min-height:128px; }}
        .feature-card b {{ color:#0f172a; }} .feature-card span {{ color:#64748b; font-size:.88rem; }}
        .trade-note {{ background:#ecfeff; border:1px solid #a5f3fc; border-radius:14px; padding:.78rem .9rem; color:#164e63; margin:.6rem 0; }}
        div[data-baseweb="tab-list"] {{ gap:.35rem; }} button[data-baseweb="tab"] {{ border-radius:10px; }}
        {_mode_css(mode)}
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.sidebar.markdown(
        """
        <div class="brand-wrap">
          <div class="brand-title">📈 Market Intelligence</div>
          <div class="brand-sub">Thai + US Equity Analytics</div>
          <div class="v4-badge">VERSION 4</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.sidebar.segmented_control(
        "Display mode", UI_MODES, key="mi_ui_mode", selection_mode="single",
        help="Auto responds to screen width. Desktop and Mobile force a layout optimized for that device."
    )
    st.sidebar.caption(f"View: {get_ui_mode()} • Data: {os.getenv('MARKET_DATA_PROVIDER', 'Yahoo Finance')}")
    st.sidebar.caption("Research + Paper Trading")
    st.sidebar.divider()
