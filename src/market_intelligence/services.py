from __future__ import annotations

import pandas as pd

from .data.provider import YFinanceProvider
from .indicators.core import add_indicators
from .strategy.engine import build_trade_plan
from .strategy.guidance import build_technical_guidance

provider = YFinanceProvider()

# UI analysis windows. Short windows use intraday bars so indicators still have
# enough observations to be useful. 7D is sourced from 1 month then trimmed.
ANALYSIS_WINDOWS = {
    "1D": {"period": "1d", "interval": "5m", "trim_days": None},
    "7D": {"period": "1mo", "interval": "30m", "trim_days": 7},
    "1M": {"period": "1mo", "interval": "1h", "trim_days": None},
    "6M": {"period": "6mo", "interval": "1d", "trim_days": None},
    "1Y": {"period": "1y", "interval": "1d", "trim_days": None},
    "2Y": {"period": "2y", "interval": "1d", "trim_days": None},
    "5Y": {"period": "5y", "interval": "1d", "trim_days": None},
}


def resolve_analysis_window(value: str) -> dict:
    key = str(value or "2Y").strip().upper()
    aliases = {
        "1D": "1D", "7D": "7D", "1M": "1M", "1MO": "1M",
        "6M": "6M", "6MO": "6M", "1Y": "1Y", "2Y": "2Y", "5Y": "5Y",
    }
    key = aliases.get(key, key)
    if key not in ANALYSIS_WINDOWS:
        # Preserve compatibility for callers passing native yfinance periods.
        return {"period": str(value), "interval": "1d", "trim_days": None, "label": str(value).upper()}
    return {**ANALYSIS_WINDOWS[key], "label": key}


def _trim_window(df: pd.DataFrame, days: int | None) -> pd.DataFrame:
    if not days or df.empty:
        return df
    end = pd.to_datetime(df["Date"]).max()
    start = end - pd.Timedelta(days=int(days))
    out = df[pd.to_datetime(df["Date"]) >= start].copy().reset_index(drop=True)
    # A holiday-heavy week can be sparse; keep at least the most recent 20 bars.
    if len(out) < 20:
        out = df.tail(min(len(df), 80)).copy().reset_index(drop=True)
    return out


def analyze_symbol(symbol, market="US", period="2Y", interval=None, equity=1_000_000, risk_pct=1.0):
    spec = resolve_analysis_window(period)
    use_interval = interval or spec["interval"]
    raw = provider.fetch(symbol, market, spec["period"], use_interval)
    raw = _trim_window(raw, spec.get("trim_days"))
    enriched = add_indicators(raw)
    return enriched, build_trade_plan(enriched, equity=equity, risk_pct=risk_pct, market=market)


def analyze_symbol_v3(symbol, market="US", period="2Y", equity=1_000_000, risk_pct=1.0):
    df, plan = analyze_symbol(symbol, market, period=period, equity=equity, risk_pct=risk_pct)
    return df, plan, build_technical_guidance(df)


def analyze_symbol_v4(symbol, market="US", period="2Y", equity=1_000_000, risk_pct=1.0, trading_profile="SWING"):
    """V4 analysis with timeframe-aware, user-selectable trading profile guidance."""
    df, plan = analyze_symbol(symbol, market, period=period, equity=equity, risk_pct=risk_pct)
    return df, plan, build_technical_guidance(df, profile=trading_profile)


def scan_symbols(symbols, market="US", period="1Y"):
    rows = []
    for symbol in symbols:
        symbol = symbol.strip()
        if not symbol:
            continue
        try:
            df, plan = analyze_symbol(symbol, market, period=period)
            last = df.iloc[-1]
            rows.append({
                "symbol": symbol.upper(), "market": market.upper(),
                "price": round(float(last["Close"]), 4), "score": plan.score,
                "trend": plan.trend, "signal": plan.signal,
                "rsi": round(float(last["RSI14"]), 2),
                "volume_ratio": round(float(last["VOL_RATIO"]), 2) if pd.notna(last["VOL_RATIO"]) else None,
                "entry": round(plan.entry, 4), "stop": round(plan.stop, 4), "target": round(plan.target, 4),
            })
        except Exception as exc:
            rows.append({"symbol": symbol.upper(), "market": market.upper(), "error": str(exc)})
    out = pd.DataFrame(rows)
    return out.sort_values("score", ascending=False, na_position="last") if not out.empty and "score" in out.columns else out
