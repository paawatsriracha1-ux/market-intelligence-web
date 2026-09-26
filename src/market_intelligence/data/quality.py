from __future__ import annotations

from dataclasses import asdict, dataclass
import numpy as np
import pandas as pd

REQUIRED_COLUMNS = ("Date", "Open", "High", "Low", "Close", "Volume")

@dataclass(frozen=True)
class MarketDataQualityReport:
    valid: bool
    signal_allowed: bool
    rows: int
    source_timestamp: str | None
    issues: tuple[str, ...]

    def to_dict(self) -> dict:
        data = asdict(self)
        data["issues"] = list(self.issues)
        return data

def validate_market_frame(frame: pd.DataFrame) -> tuple[pd.DataFrame, MarketDataQualityReport]:
    """Validate OHLCV without inventing, interpolating, or repairing prices."""
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
    if issues:
        raise ValueError("Unreliable market data: " + ", ".join(dict.fromkeys(issues)))
    report = MarketDataQualityReport(True, True, len(out), out["Date"].iloc[-1].isoformat(), ())
    return out.reset_index(drop=True), report
