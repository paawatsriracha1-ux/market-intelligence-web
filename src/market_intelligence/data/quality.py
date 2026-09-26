from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import re

import numpy as np
import pandas as pd

REQUIRED_COLUMNS = ("Date", "Open", "High", "Low", "Close", "Volume")
_INTERVAL_RE = re.compile(r"^(\d+)(m|h|d|wk)$", re.IGNORECASE)


@dataclass(frozen=True)
class MarketDataQualityReport:
    valid: bool
    signal_allowed: bool
    rows: int
    source_timestamp: str | None
    issues: tuple[str, ...]
    interval: str | None = None
    checked_at: str | None = None
    age_seconds: float | None = None
    stale_after_seconds: float | None = None
    gap_count: int = 0
    max_gap_seconds: float | None = None

    def to_dict(self) -> dict:
        data = asdict(self)
        data["issues"] = list(self.issues)
        return data


def _interval_seconds(interval: str) -> int:
    value = str(interval).strip().lower()
    match = _INTERVAL_RE.fullmatch(value)
    if not match:
        raise ValueError(f"Unsupported market-data interval: {interval}")
    amount = int(match.group(1))
    unit = match.group(2).lower()
    multiplier = {"m": 60, "h": 3600, "d": 86400, "wk": 604800}[unit]
    return amount * multiplier


def _utc_naive(value: datetime | pd.Timestamp | None) -> pd.Timestamp:
    if value is None:
        value = datetime.now(timezone.utc)
    ts = pd.Timestamp(value)
    if ts.tzinfo is not None:
        ts = ts.tz_convert("UTC").tz_localize(None)
    return ts


def validate_market_frame(
    frame: pd.DataFrame,
    *,
    interval: str | None = None,
    now: datetime | pd.Timestamp | None = None,
    stale_multiplier: float = 3.0,
    gap_multiplier: float = 3.0,
    enforce_freshness: bool = False,
    enforce_gaps: bool = False,
    session_aware: bool = False,
) -> tuple[pd.DataFrame, MarketDataQualityReport]:
    """Validate OHLCV without inventing, interpolating, or repairing prices.

    M1.4 supports session-aware intraday checks. When ``session_aware`` is true,
    freshness is enforced only while the newest bar and validation time are on
    the same UTC trading date, and gap checks compare bars only within the same
    UTC date. This prevents weekends, overnight closures and ordinary session
    boundaries from being misclassified as missing market data.
    """
    if frame is None or frame.empty:
        raise ValueError("Market data is empty")
    missing = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise ValueError(f"Missing market-data columns: {missing}")

    out = frame.loc[:, REQUIRED_COLUMNS].copy()
    out["Date"] = pd.to_datetime(out["Date"], utc=True, errors="coerce").dt.tz_convert(None)
    for column in REQUIRED_COLUMNS[1:]:
        out[column] = pd.to_numeric(out[column], errors="coerce")

    issues: list[str] = []
    if out["Date"].isna().any(): issues.append("invalid_timestamp")
    if out["Date"].duplicated().any(): issues.append("duplicate_timestamp")
    if not out["Date"].is_monotonic_increasing: issues.append("non_monotonic_timestamp")

    prices = out[["Open", "High", "Low", "Close"]]
    if not np.isfinite(prices.to_numpy(dtype=float)).all() or prices.isna().any().any(): issues.append("non_finite_price")
    if (prices <= 0).any().any(): issues.append("non_positive_price")
    volume = out["Volume"]
    if not np.isfinite(volume.to_numpy(dtype=float)).all() or volume.isna().any(): issues.append("non_finite_volume")
    if (volume < 0).any(): issues.append("negative_volume")
    if ((out["High"] < out["Low"]) | (out["Open"] > out["High"]) | (out["Open"] < out["Low"]) | (out["Close"] > out["High"]) | (out["Close"] < out["Low"])).any():
        issues.append("invalid_ohlc_relationship")

    checked_at = _utc_naive(now)
    age_seconds: float | None = None
    stale_after_seconds: float | None = None
    gap_count = 0
    max_gap_seconds: float | None = None

    if interval is not None and not out["Date"].isna().any():
        interval_seconds = _interval_seconds(interval)
        source_ts = out["Date"].iloc[-1]
        age_seconds = max(0.0, float((checked_at - source_ts).total_seconds()))
        stale_after_seconds = float(interval_seconds * stale_multiplier)

        same_session_date = source_ts.normalize() == checked_at.normalize()
        should_check_freshness = enforce_freshness and (not session_aware or same_session_date)
        if should_check_freshness and age_seconds > stale_after_seconds:
            issues.append("stale_market_data")

        if len(out) > 1:
            gaps = out["Date"].diff().dropna().dt.total_seconds()
            if session_aware:
                current_dates = out["Date"].dt.normalize()
                same_date = current_dates.eq(current_dates.shift(1)).iloc[1:]
                gaps = gaps[same_date.to_numpy()]
            if not gaps.empty:
                max_gap_seconds = float(gaps.max())
                gap_limit = float(interval_seconds * gap_multiplier)
                gap_count = int((gaps > gap_limit).sum())
                if enforce_gaps and gap_count:
                    issues.append("market_data_gap")

    if issues:
        raise ValueError("Unreliable market data: " + ", ".join(dict.fromkeys(issues)))

    source_timestamp = out["Date"].iloc[-1].isoformat()
    report = MarketDataQualityReport(
        valid=True,
        signal_allowed=True,
        rows=len(out),
        source_timestamp=source_timestamp,
        issues=(),
        interval=str(interval) if interval is not None else None,
        checked_at=checked_at.isoformat(),
        age_seconds=age_seconds,
        stale_after_seconds=stale_after_seconds,
        gap_count=gap_count,
        max_gap_seconds=max_gap_seconds,
    )
    return out.reset_index(drop=True), report
