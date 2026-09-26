import unittest

import pandas as pd

from market_intelligence.indicators.core import add_indicators
from market_intelligence.strategy.engine import build_trade_plan, TradePlan
from market_intelligence.strategy.guidance import (
    build_technical_guidance,
    TechnicalGuidance,
)
from market_intelligence.analysis.adapter import build_analysis_snapshot
from market_intelligence.analysis.snapshot import AnalysisSnapshot


class M224RealObjectIntegrationTests(unittest.TestCase):

    def _frame(self):
        n = 260

        dates = pd.date_range(
            "2025-01-01",
            periods=n,
            freq="D",
        )

        close = pd.Series(
            [100.0 + i * 0.20 for i in range(n)]
        )

        # IMPORTANT:
        # add_indicators() production contract requires Date as a column.
        df = pd.DataFrame(
            {
                "Date": dates,
                "Open": close - 0.30,
                "High": close + 0.80,
                "Low": close - 0.80,
                "Close": close,
                "Volume": [1_000_000 + i * 1000 for i in range(n)],
            }
        )

        df = add_indicators(df)

        # Simulate metadata already verified by M1 reliability gate.
        df.attrs["market_data_symbol"] = "AAPL"
        df.attrs["market_data_timeframe"] = "1D"
        df.attrs["market_data_reliability"] = "verified"
        df.attrs["market_data_quality"] = {
            "valid": True,
            "signal_allowed": True,
            "gap_count": 0,
            "issues": [],
        }

        return df

    def test_m224_real_trade_plan_is_accepted(self):
        df = self._frame()

        plan = build_trade_plan(
            df,
            equity=1_000_000,
            risk_pct=1.0,
            market="US",
        )

        guidance = build_technical_guidance(
            df,
            profile="SWING",
        )

        self.assertIsInstance(plan, TradePlan)
        self.assertIsInstance(guidance, TechnicalGuidance)

        snapshot = build_analysis_snapshot(
            df,
            plan,
            guidance,
            market="US",
        )

        self.assertIsInstance(snapshot, AnalysisSnapshot)

    def test_m224_real_objects_are_serialized(self):
        df = self._frame()

        plan = build_trade_plan(df, market="US")
        guidance = build_technical_guidance(
            df,
            profile="SWING",
        )

        snapshot = build_analysis_snapshot(
            df,
            plan,
            guidance,
            market="US",
        )

        payload = snapshot.to_dict()

        self.assertIsInstance(payload["trade_plan"], dict)
        self.assertIsInstance(payload["guidance"], dict)

        self.assertEqual(
            payload["trade_plan"]["score"],
            plan.score,
        )

        self.assertEqual(
            payload["guidance"]["profile"],
            guidance.profile,
        )

    def test_m224_snapshot_preserves_verified_identity(self):
        df = self._frame()

        plan = build_trade_plan(df, market="US")
        guidance = build_technical_guidance(df)

        snapshot = build_analysis_snapshot(
            df,
            plan,
            guidance,
            market="US",
        )

        payload = snapshot.to_dict()

        self.assertEqual(payload["symbol"], "AAPL")
        self.assertEqual(payload["market"], "US")
        self.assertEqual(payload["timeframe"], "1D")

        self.assertEqual(
            payload["market_data_quality"]["reliability"],
            "verified",
        )

    def test_m224_snapshot_contains_no_dataframe(self):
        df = self._frame()

        plan = build_trade_plan(df, market="US")
        guidance = build_technical_guidance(df)

        payload = build_analysis_snapshot(
            df,
            plan,
            guidance,
            market="US",
        ).to_dict()

        def contains_dataframe(value):
            if isinstance(value, pd.DataFrame):
                return True

            if isinstance(value, dict):
                return any(
                    contains_dataframe(v)
                    for v in value.values()
                )

            if isinstance(value, (list, tuple)):
                return any(
                    contains_dataframe(v)
                    for v in value
                )

            return False

        self.assertFalse(contains_dataframe(payload))


if __name__ == "__main__":
    unittest.main()
