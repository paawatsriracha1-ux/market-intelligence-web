from __future__ import annotations
import numpy as np
import pandas as pd

def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return (100 - (100 / (1 + rs))).fillna(50)

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy().sort_values("Date").reset_index(drop=True)
    c = d["Close"].astype(float)
    for n in (20, 50, 200): d[f"EMA{n}"] = c.ewm(span=n, adjust=False).mean()
    d["RSI14"] = _rsi(c, 14)
    ema12, ema26 = c.ewm(span=12, adjust=False).mean(), c.ewm(span=26, adjust=False).mean()
    d["MACD"] = ema12 - ema26
    d["MACD_SIGNAL"] = d["MACD"].ewm(span=9, adjust=False).mean()
    d["MACD_HIST"] = d["MACD"] - d["MACD_SIGNAL"]
    ma20, sd20 = c.rolling(20).mean(), c.rolling(20).std(ddof=0)
    d["BB_MID"], d["BB_UPPER"], d["BB_LOWER"] = ma20, ma20 + 2*sd20, ma20 - 2*sd20
    prev_close = c.shift(1)
    tr = pd.concat([(d["High"]-d["Low"]).abs(), (d["High"]-prev_close).abs(), (d["Low"]-prev_close).abs()], axis=1).max(axis=1)
    d["ATR14"] = tr.ewm(alpha=1/14, adjust=False, min_periods=14).mean().bfill()
    d["VOL_MA20"] = d["Volume"].rolling(20).mean()
    d["VOL_RATIO"] = d["Volume"] / d["VOL_MA20"].replace(0, np.nan)
    d["SUPPORT20"] = d["Low"].rolling(20).min()
    d["RESISTANCE20"] = d["High"].rolling(20).max()
    # Prior structure excludes the current bar and is used by V3 guidance lines.
    d["PREV_SUPPORT20"] = d["Low"].shift(1).rolling(20).min()
    d["PREV_RESISTANCE20"] = d["High"].shift(1).rolling(20).max()
    d["RETURN1D"] = c.pct_change()
    d["ATR_PCT"] = d["ATR14"] / c * 100
    return d

def detect_trend(row: pd.Series) -> str:
    c, e20, e50, e200 = row["Close"], row["EMA20"], row["EMA50"], row["EMA200"]
    if c > e20 > e50 > e200: return "STRONG UPTREND"
    if c > e50 and e20 > e50: return "UPTREND"
    if c < e20 < e50 < e200: return "STRONG DOWNTREND"
    if c < e50 and e20 < e50: return "DOWNTREND"
    return "SIDEWAY"

def technical_score(row: pd.Series) -> tuple[int, dict]:
    parts = {"trend": 0, "momentum": 0, "volume": 0, "structure": 0, "risk": 0}
    c = float(row["Close"])
    for cond, pts in [(c > row["EMA20"],8),(row["EMA20"] > row["EMA50"],8),(row["EMA50"] > row["EMA200"],7),(c > row["EMA200"],7)]:
        if bool(cond): parts["trend"] += pts
    rsi = float(row["RSI14"])
    if 50 <= rsi <= 70: parts["momentum"] += 13
    elif 45 <= rsi < 50 or 70 < rsi <= 75: parts["momentum"] += 7
    if row["MACD"] > row["MACD_SIGNAL"]: parts["momentum"] += 12
    vr = float(row["VOL_RATIO"]) if pd.notna(row["VOL_RATIO"]) else 0
    parts["volume"] += 10 if vr >= 1.5 else 7 if vr >= 1.1 else 3 if vr >= .8 else 0
    if pd.notna(row.get("RETURN1D")) and float(row["RETURN1D"]) > 0: parts["volume"] += 5
    sup, res = row["SUPPORT20"], row["RESISTANCE20"]
    if pd.notna(sup) and c > sup: parts["structure"] += 7
    if pd.notna(res) and res > c and (res-c)/c >= .02: parts["structure"] += 8
    elif pd.notna(res) and c >= res*.995: parts["structure"] += 6
    ap = float(row["ATR_PCT"]) if pd.notna(row["ATR_PCT"]) else 99
    parts["risk"] += 15 if 0 < ap <= 3 else 11 if ap <= 5 else 6 if ap <= 8 else 3 if ap <= 12 else 0
    score = int(max(0, min(100, sum(parts.values()))))
    return score, parts
