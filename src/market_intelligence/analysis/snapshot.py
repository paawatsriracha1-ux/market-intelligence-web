"""Canonical analysis snapshot contracts.

M2.2 establishes a stable, serializable analysis representation without
changing the existing TradePlan, TechnicalGuidance, or service contracts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class IndicatorSnapshot:
    """Canonical technical-indicator values."""

    ema20: float
    ema50: float
    ema200: float
    rsi14: float
    macd: float
    macd_signal: float
    atr14: float
    volume_ratio: float | None = None


@dataclass(frozen=True)
class LevelSnapshot:
    """Canonical structural price levels."""

    support: float
    resistance: float


@dataclass(frozen=True)
class AnalysisSnapshot:
    """Stable analysis result passed to later M2 components.

    This contract intentionally contains plain Python values only.
    Pandas objects must never cross this boundary.
    """

    symbol: str
    market: str
    timeframe: str
    timestamp: str
    price: float
    score: int
    trend: str
    signal: str

    indicators: IndicatorSnapshot
    levels: LevelSnapshot

    trade_plan: dict[str, Any] = field(default_factory=dict)
    guidance: dict[str, Any] = field(default_factory=dict)
    market_data_quality: dict[str, Any] = field(default_factory=dict)

    schema_version: str = "m2.2"

    def __post_init__(self) -> None:
        if not self.symbol:
            raise ValueError("symbol must not be empty")

        if not self.market:
            raise ValueError("market must not be empty")

        if not self.timeframe:
            raise ValueError("timeframe must not be empty")

        if not 0 <= self.score <= 100:
            raise ValueError("score must be between 0 and 100")

        if self.price <= 0:
            raise ValueError("price must be positive")

        if self.levels.support > self.price:
            raise ValueError("support must not exceed current price")

        if self.levels.resistance < self.price:
            raise ValueError("resistance must not be below current price")

    def to_dict(self) -> dict[str, Any]:
        """Return a plain serializable dictionary."""
        from dataclasses import asdict

        return asdict(self)
