from __future__ import annotations
from dataclasses import dataclass, asdict
import math
import pandas as pd
from ..indicators.core import detect_trend, technical_score

@dataclass
class TradePlan:
    score: int
    trend: str
    signal: str
    entry: float
    stop: float
    target: float
    risk_reward: float
    support: float | None
    resistance: float | None
    position_qty: int
    risk_amount: float
    score_parts: dict
    conditions: dict
    def to_dict(self): return asdict(self)

def build_trade_plan(df: pd.DataFrame, equity=1_000_000, risk_pct=1.0, market="US") -> TradePlan:
    if df.empty: raise ValueError("Empty dataframe")
    row = df.iloc[-1]
    score, parts = technical_score(row)
    trend = detect_trend(row)
    conditions = {
        "price_above_ema50": bool(row["Close"] > row["EMA50"]),
        "ema20_above_ema50": bool(row["EMA20"] > row["EMA50"]),
        "rsi_above_50": bool(row["RSI14"] > 50),
        "macd_bullish": bool(row["MACD"] > row["MACD_SIGNAL"]),
        "volume_confirmation": bool(pd.notna(row["VOL_RATIO"]) and row["VOL_RATIO"] >= 1.1),
    }
    passed = sum(conditions.values())
    if score >= 75 and passed >= 4 and "UPTREND" in trend: signal = "BUY CANDIDATE"
    elif score >= 60 and passed >= 3: signal = "WATCH / POSITIVE"
    elif score <= 35 or "DOWNTREND" in trend: signal = "AVOID / WEAK"
    else: signal = "NEUTRAL"
    entry = float(row["Close"])
    atr = max(float(row["ATR14"]), entry*.005)
    support = float(row["SUPPORT20"]) if pd.notna(row["SUPPORT20"]) else None
    resistance = float(row["RESISTANCE20"]) if pd.notna(row["RESISTANCE20"]) else None
    atr_stop = entry - 2*atr
    stop = max(atr_stop, support*.995) if support is not None and support < entry else atr_stop
    stop = min(stop, entry*.995)
    per_share_risk = max(entry-stop, entry*.001)
    target = entry + 2*per_share_risk
    risk_amount = equity*(risk_pct/100)
    qty = max(0, min(math.floor(risk_amount/per_share_risk), math.floor((equity*.20)/entry)))
    if market.upper() == "TH": qty = (qty//100)*100
    return TradePlan(score, trend, signal, entry, stop, target, (target-entry)/per_share_risk,
                     support, resistance, qty, risk_amount, parts, conditions)
