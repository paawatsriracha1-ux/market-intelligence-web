"""Adapters for producing the canonical M2 AnalysisSnapshot."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Mapping

import pandas as pd

from .snapshot import (
    AnalysisSnapshot,
    IndicatorSnapshot,
    LevelSnapshot,
)


def _to_dict(value: Any, name: str) -> dict[str, Any]:
    """Convert supported analysis objects to plain dictionaries."""
    if value is None:
        raise ValueError(f"{name} must not be None")

    if isinstance(value, Mapping):
        return dict(value)

    if is_dataclass(value):
        return asdict(value)

    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        result = to_dict()
        if isinstance(result, Mapping):
            return dict(result)

    raise TypeError(
        f"{name} must be a mapping, dataclass, or expose to_dict()"
    )


def _required_number(row: pd.Series, column: str) -> float:
    """Read a required finite numeric value from the analysis row."""
    if column not in row.index:
        raise ValueError(f"missing required analysis column: {column}")

    value = row[column]

    if pd.isna(value):
        raise ValueError(f"required analysis value is missing: {column}")

    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"required analysis value is not numeric: {column}"
        ) from exc

    if not pd.notna(result):
        raise ValueError(f"required analysis value is invalid: {column}")

    return result


def _required_text(value: Any, name: str) -> str:
    if value is None:
        raise ValueError(f"{name} is required")

    result = str(value).strip()

    if not result:
        raise ValueError(f"{name} is required")

    return result


def build_analysis_snapshot(
    df: pd.DataFrame,
    trade_plan: Any,
    guidance: Any,
    *,
    market: str,
) -> AnalysisSnapshot:
    """Build the canonical M2 analysis snapshot.

    The adapter is intentionally read-only. It does not recalculate
    indicators, strategy signals, risk levels, or guidance. Existing
    validated analysis results remain the source of truth.
    """
    if df is None or df.empty:
        raise ValueError("analysis dataframe must not be empty")

    row = df.iloc[-1]

    plan = _to_dict(trade_plan, "trade_plan")
    guide = _to_dict(guidance, "guidance")

    symbol = _required_text(
        df.attrs.get("market_data_symbol"),
        "market_data_symbol",
    )

    timeframe = _required_text(
        df.attrs.get("market_data_timeframe"),
        "market_data_timeframe",
    )

    market_value = _required_text(market, "market").upper()

    reliability = _required_text(
        df.attrs.get("market_data_reliability"),
        "market_data_reliability",
    )

    raw_quality = df.attrs.get("market_data_quality", {})

    if raw_quality is None:
        raw_quality = {}

    if not isinstance(raw_quality, Mapping):
        raise TypeError("market_data_quality must be a mapping")

    quality = dict(raw_quality)
    quality["reliability"] = reliability

    # M1 reliability gate must remain authoritative.
    if quality.get("valid") is not True:
        raise ValueError("market data is not valid")

    if quality.get("signal_allowed") is not True:
        raise ValueError("market data is not signal eligible")

    if "Date" not in row.index or pd.isna(row["Date"]):
        raise ValueError("analysis timestamp is required")

    timestamp = pd.Timestamp(row["Date"]).isoformat()

    score = plan.get("score")
    trend = plan.get("trend")
    signal = plan.get("signal")

    if score is None:
        raise ValueError("trade_plan score is required")

    try:
        score = int(score)
    except (TypeError, ValueError) as exc:
        raise ValueError("trade_plan score must be numeric") from exc

    trend = _required_text(trend, "trade_plan trend")
    signal = _required_text(signal, "trade_plan signal")

    indicators = IndicatorSnapshot(
        ema20=_required_number(row, "EMA20"),
        ema50=_required_number(row, "EMA50"),
        ema200=_required_number(row, "EMA200"),
        rsi14=_required_number(row, "RSI14"),
        macd=_required_number(row, "MACD"),
        macd_signal=_required_number(row, "MACD_SIGNAL"),
        atr14=_required_number(row, "ATR14"),
        volume_ratio=(
            None
            if "VOL_RATIO" not in row.index or pd.isna(row["VOL_RATIO"])
            else float(row["VOL_RATIO"])
        ),
    )

    levels = LevelSnapshot(
        support=_required_number(row, "SUPPORT20"),
        resistance=_required_number(row, "RESISTANCE20"),
    )

    return AnalysisSnapshot(
        symbol=symbol.upper(),
        market=market_value,
        timeframe=timeframe.upper(),
        timestamp=timestamp,
        price=_required_number(row, "Close"),
        score=score,
        trend=trend,
        signal=signal,
        indicators=indicators,
        levels=levels,
        trade_plan=plan,
        guidance=guide,
        market_data_quality=quality,
    )
