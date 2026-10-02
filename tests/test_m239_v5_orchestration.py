"""M2.3.9 V5 orchestration contract tests.

These tests define the required public V5 service boundary.

Expected pipeline:

    reliable market data
        -> indicators
        -> TradePlan
        -> TechnicalGuidance
        -> AnalysisSnapshot
        -> FinalDecisionBundle

M2.3.9 Step 5 is test-first.
Production implementation is intentionally absent at this stage.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import unittest
from unittest.mock import patch

import pandas as pd

from market_intelligence.analysis.snapshot import AnalysisSnapshot
from market_intelligence.decision import FinalDecisionBundle
from market_intelligence.strategy.engine import TradePlan
from market_intelligence.strategy.guidance import TechnicalGuidance


def _market_frame() -> pd.DataFrame:
    """Minimal verified provider frame for orchestration testing."""

    dates = pd.date_range(
        "2026-01-01",
        periods=240,
        freq="D",
    )

    close = [
        100.0 + (i * 0.10)
        for i in range(len(dates))
    ]

    df = pd.DataFrame(
        {
            "Date": dates,
            "Open": close,
            "High": [x + 1.0 for x in close],
            "Low": [x - 1.0 for x in close],
            "Close": close,
            "Volume": [1_000_000] * len(dates),
        }
    )

    df.attrs["market_data_symbol"] = "TEST"
    df.attrs["market_data_timeframe"] = "1Y"
    df.attrs["market_data_reliability"] = "verified"
    df.attrs["market_data_quality"] = {
        "valid": True,
        "signal_allowed": True,
    }

    return df


class TestM239V5Orchestration(unittest.TestCase):

    def test_v5_public_service_exists(self):
        from market_intelligence import services

        self.assertTrue(
            hasattr(services, "analyze_symbol_v5"),
            "M2.3.9 requires analyze_symbol_v5 public service",
        )

    @patch("market_intelligence.services.provider.fetch")
    def test_v5_returns_canonical_pipeline_objects(
        self,
        fetch_mock,
    ):
        from market_intelligence.services import analyze_symbol_v5

        fetch_mock.return_value = _market_frame()

        result = analyze_symbol_v5(
            "TEST",
            market="US",
            period="1Y",
            trading_profile="SWING",
        )

        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 5)

        df, plan, guide, snapshot, final = result

        self.assertIsInstance(df, pd.DataFrame)
        self.assertIsInstance(plan, TradePlan)
        self.assertIsInstance(guide, TechnicalGuidance)
        self.assertIsInstance(snapshot, AnalysisSnapshot)
        self.assertIsInstance(final, FinalDecisionBundle)

    @patch("market_intelligence.services.provider.fetch")
    def test_v5_snapshot_preserves_analysis_identity(
        self,
        fetch_mock,
    ):
        from market_intelligence.services import analyze_symbol_v5

        fetch_mock.return_value = _market_frame()

        _, plan, guide, snapshot, _ = analyze_symbol_v5(
            "TEST",
            market="US",
            period="1Y",
            trading_profile="SWING",
        )

        self.assertEqual(snapshot.symbol, "TEST")
        self.assertEqual(snapshot.market, "US")
        self.assertEqual(snapshot.timeframe, "1Y")

        self.assertEqual(snapshot.score, plan.score)
        self.assertEqual(snapshot.trend, plan.trend)
        self.assertEqual(snapshot.signal, plan.signal)

        self.assertEqual(
            snapshot.trade_plan,
            plan.to_dict(),
        )

        self.assertEqual(
            snapshot.guidance,
            guide.to_dict(),
        )

    @patch("market_intelligence.services.provider.fetch")
    def test_v5_final_bundle_is_derived_from_snapshot(
        self,
        fetch_mock,
    ):
        from market_intelligence.services import analyze_symbol_v5
        from market_intelligence.decision import evaluate_final_decision

        fetch_mock.return_value = _market_frame()

        _, _, _, snapshot, final = analyze_symbol_v5(
            "TEST",
            market="US",
            period="1Y",
            trading_profile="SWING",
        )

        expected = evaluate_final_decision(snapshot)

        self.assertEqual(final, expected)

    @patch("market_intelligence.services.provider.fetch")
    def test_v5_preserves_verified_quality_metadata(
        self,
        fetch_mock,
    ):
        from market_intelligence.services import analyze_symbol_v5

        fetch_mock.return_value = _market_frame()

        _, _, _, snapshot, _ = analyze_symbol_v5(
            "TEST",
            market="US",
            period="1Y",
            trading_profile="SWING",
        )

        self.assertTrue(
            snapshot.market_data_quality["valid"]
        )

        self.assertTrue(
            snapshot.market_data_quality["signal_allowed"]
        )

        self.assertEqual(
            snapshot.market_data_quality["reliability"],
            "verified",
        )


if __name__ == "__main__":
    unittest.main()
