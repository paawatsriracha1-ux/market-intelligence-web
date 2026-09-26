from __future__ import annotations

from dataclasses import asdict, dataclass
import pandas as pd

from ..indicators.core import detect_trend, technical_score


TRADING_PROFILES = {
    "INTRADAY": {
        "label": "Intraday",
        "trigger_atr": 0.05,
        "zone_atr": 0.28,
        "support_buffer_atr": 0.15,
        "stop_atr": 1.00,
        "tp1_r": 1.00,
        "tp2_r": 1.80,
        "target_band_atr": 0.12,
        "note": "Short-term setup. Prefer 1D / 7D data and confirm liquidity before execution.",
    },
    "SWING": {
        "label": "Swing",
        "trigger_atr": 0.10,
        "zone_atr": 0.38,
        "support_buffer_atr": 0.30,
        "stop_atr": 1.50,
        "tp1_r": 1.50,
        "tp2_r": 2.50,
        "target_band_atr": 0.18,
        "note": "Multi-day setup. 7D / 1M / 6M windows are usually the most useful context.",
    },
    "POSITION": {
        "label": "Position",
        "trigger_atr": 0.15,
        "zone_atr": 0.55,
        "support_buffer_atr": 0.40,
        "stop_atr": 2.00,
        "tp1_r": 2.00,
        "tp2_r": 3.50,
        "target_band_atr": 0.25,
        "note": "Longer-horizon setup. Prefer 1M / 6M / 1Y / 2Y context rather than intraday noise.",
    },
}


@dataclass
class TechnicalGuidance:
    """Data-derived technical levels for research / paper trading."""

    buy_trigger: float
    buy_zone_low: float
    buy_zone_high: float
    sell_tp1: float
    sell_tp2: float
    stop_loss: float
    support: float
    resistance: float
    confidence: int
    regime: str
    rationale: list[str]
    profile: str = "SWING"
    profile_label: str = "Swing"
    tp1_zone_low: float = 0.0
    tp1_zone_high: float = 0.0
    tp2_zone_low: float = 0.0
    tp2_zone_high: float = 0.0
    stop_zone_low: float = 0.0
    stop_zone_high: float = 0.0
    holding_note: str = ""

    def to_dict(self):
        return asdict(self)


def normalize_profile(profile: str | None) -> str:
    key = str(profile or "SWING").strip().upper().replace("-", " ")
    aliases = {
        "DAY": "INTRADAY", "DAY TRADE": "INTRADAY", "SHORT": "INTRADAY",
        "INTRADAY": "INTRADAY", "SWING": "SWING", "POSITION": "POSITION",
        "LONG": "POSITION", "POSITION TRADE": "POSITION",
    }
    return aliases.get(key, "SWING")


def build_technical_guidance(df: pd.DataFrame, profile: str = "SWING") -> TechnicalGuidance:
    if df is None or df.empty:
        raise ValueError("Empty dataframe")
    row = df.iloc[-1]
    close = float(row["Close"])
    atr = max(float(row.get("ATR14", close * 0.01)), close * 0.003)
    ema20 = float(row.get("EMA20", close))
    score, _ = technical_score(row)
    trend = detect_trend(row)

    profile_key = normalize_profile(profile)
    cfg = TRADING_PROFILES[profile_key]

    prior_support = row.get("PREV_SUPPORT20")
    prior_resistance = row.get("PREV_RESISTANCE20")
    support = float(prior_support) if pd.notna(prior_support) else float(row.get("SUPPORT20", close - atr))
    resistance = float(prior_resistance) if pd.notna(prior_resistance) else float(row.get("RESISTANCE20", close + atr))
    support = min(support, close)
    resistance = max(resistance, close)

    bullish = "UPTREND" in trend and score >= 55
    macd_bullish = bool(row.get("MACD", 0) > row.get("MACD_SIGNAL", 0))
    volume_ok = bool(pd.notna(row.get("VOL_RATIO")) and float(row.get("VOL_RATIO", 0)) >= 1.0)

    trigger_buffer = cfg["trigger_atr"] * atr
    if bullish:
        buy_trigger = max(close, resistance + trigger_buffer)
        pullback_anchor = max(support + cfg["support_buffer_atr"] * atr, min(ema20, close))
        buy_zone_low = min(pullback_anchor, close)
        buy_zone_high = min(max(buy_zone_low + cfg["zone_atr"] * atr, close), buy_trigger)
        regime = "BULLISH / BREAKOUT-PULLBACK"
    else:
        buy_trigger = max(close + max(0.35, cfg["trigger_atr"] * 3.0) * atr, resistance + trigger_buffer)
        buy_zone_low = max(support + cfg["support_buffer_atr"] * atr, min(ema20, close))
        buy_zone_high = min(max(buy_zone_low + cfg["zone_atr"] * atr, close), buy_trigger)
        regime = "WAIT FOR CONFIRMATION"

    structural_stop = support - cfg["support_buffer_atr"] * atr
    volatility_stop = buy_zone_low - cfg["stop_atr"] * atr
    stop_loss = min(structural_stop, volatility_stop)
    stop_loss = min(stop_loss, buy_trigger - max(0.60, cfg["stop_atr"] * 0.50) * atr)

    risk = max(buy_trigger - stop_loss, atr * 0.75)
    sell_tp1 = buy_trigger + cfg["tp1_r"] * risk
    sell_tp2 = buy_trigger + cfg["tp2_r"] * risk

    band = cfg["target_band_atr"] * atr
    tp1_zone_low, tp1_zone_high = sell_tp1 - band, sell_tp1 + band
    tp2_zone_low, tp2_zone_high = sell_tp2 - band, sell_tp2 + band
    stop_band = max(0.10 * atr, 0.15 * abs(buy_zone_low - stop_loss))
    stop_zone_low, stop_zone_high = stop_loss - stop_band, stop_loss + stop_band

    confidence = int(round(min(100, max(0, score * 0.70 + (15 if macd_bullish else 0) + (15 if volume_ok else 0)))))
    rationale = [
        f"Profile: {cfg['label']}",
        f"Trend: {trend}",
        f"Technical score: {score}/100",
        f"ATR: {atr:.4f}",
        f"Buy trigger uses prior resistance + {cfg['trigger_atr']:.2f} ATR confirmation buffer",
        f"Stop combines support structure with a {cfg['stop_atr']:.2f} ATR volatility allowance",
        f"TP1/TP2 use {cfg['tp1_r']:.2f}R and {cfg['tp2_r']:.2f}R from the trigger",
    ]
    return TechnicalGuidance(
        buy_trigger=round(buy_trigger, 6),
        buy_zone_low=round(buy_zone_low, 6),
        buy_zone_high=round(buy_zone_high, 6),
        sell_tp1=round(sell_tp1, 6),
        sell_tp2=round(sell_tp2, 6),
        stop_loss=round(stop_loss, 6),
        support=round(support, 6),
        resistance=round(resistance, 6),
        confidence=confidence,
        regime=regime,
        rationale=rationale,
        profile=profile_key,
        profile_label=cfg["label"],
        tp1_zone_low=round(tp1_zone_low, 6),
        tp1_zone_high=round(tp1_zone_high, 6),
        tp2_zone_low=round(tp2_zone_low, 6),
        tp2_zone_high=round(tp2_zone_high, 6),
        stop_zone_low=round(stop_zone_low, 6),
        stop_zone_high=round(stop_zone_high, 6),
        holding_note=cfg["note"],
    )
