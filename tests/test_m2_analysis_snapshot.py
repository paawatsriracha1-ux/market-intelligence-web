import unittest
from dataclasses import asdict, is_dataclass

import pandas as pd

from market_intelligence.analysis.snapshot import (
    AnalysisSnapshot,
    IndicatorSnapshot,
    LevelSnapshot,
)


class M22AnalysisSnapshotContractTests(unittest.TestCase):

    def _snapshot(self):
        return AnalysisSnapshot(
            symbol="AAPL",
            market="US",
            timeframe="1D",
            timestamp="2026-09-25T20:00:00",
            price=225.50,
            score=78,
            trend="UPTREND",
            signal="BUY CANDIDATE",
            indicators=IndicatorSnapshot(
                ema20=220.0,
                ema50=215.0,
                ema200=200.0,
                rsi14=62.5,
                macd=1.20,
                macd_signal=0.90,
                atr14=4.50,
                volume_ratio=1.30,
            ),
            levels=LevelSnapshot(
                support=218.0,
                resistance=228.0,
            ),
            trade_plan={
                "entry": 225.50,
                "stop": 216.50,
                "target": 243.50,
                "risk_reward": 2.0,
            },
            guidance={
                "buy_trigger": 228.50,
                "buy_zone_low": 220.0,
                "buy_zone_high": 225.0,
                "sell_tp1": 237.0,
                "sell_tp2": 246.0,
                "stop_loss": 216.0,
                "confidence": 80,
            },
            market_data_quality={
                "valid": True,
                "signal_allowed": True,
                "reliability": "verified",
            },
        )

    def test_m221_snapshot_is_dataclass(self):
        snapshot = self._snapshot()
        self.assertTrue(is_dataclass(snapshot))

    def test_m221_schema_version_is_explicit(self):
        snapshot = self._snapshot()
        self.assertEqual(snapshot.schema_version, "m2.2")

    def test_m221_identity_fields_are_preserved(self):
        snapshot = self._snapshot()
        self.assertEqual(snapshot.symbol, "AAPL")
        self.assertEqual(snapshot.market, "US")
        self.assertEqual(snapshot.timeframe, "1D")

    def test_m221_score_is_bounded(self):
        snapshot = self._snapshot()
        self.assertGreaterEqual(snapshot.score, 0)
        self.assertLessEqual(snapshot.score, 100)

    def test_m221_indicator_contract(self):
        indicators = self._snapshot().indicators

        self.assertEqual(indicators.ema20, 220.0)
        self.assertEqual(indicators.ema50, 215.0)
        self.assertEqual(indicators.ema200, 200.0)
        self.assertEqual(indicators.rsi14, 62.5)
        self.assertEqual(indicators.atr14, 4.50)

    def test_m221_level_contract(self):
        levels = self._snapshot().levels
        self.assertLessEqual(levels.support, self._snapshot().price)
        self.assertGreaterEqual(levels.resistance, self._snapshot().price)

    def test_m221_trade_plan_is_embedded(self):
        plan = self._snapshot().trade_plan
        self.assertIn("entry", plan)
        self.assertIn("stop", plan)
        self.assertIn("target", plan)
        self.assertIn("risk_reward", plan)

    def test_m221_guidance_is_embedded(self):
        guidance = self._snapshot().guidance
        self.assertIn("buy_trigger", guidance)
        self.assertIn("buy_zone_low", guidance)
        self.assertIn("buy_zone_high", guidance)
        self.assertIn("sell_tp1", guidance)
        self.assertIn("sell_tp2", guidance)
        self.assertIn("stop_loss", guidance)

    def test_m221_reliability_metadata_is_embedded(self):
        quality = self._snapshot().market_data_quality
        self.assertTrue(quality["valid"])
        self.assertTrue(quality["signal_allowed"])
        self.assertEqual(quality["reliability"], "verified")

    def test_m221_snapshot_serializes_to_dict(self):
        payload = asdict(self._snapshot())

        self.assertIsInstance(payload, dict)
        self.assertEqual(payload["schema_version"], "m2.2")
        self.assertEqual(payload["symbol"], "AAPL")
        self.assertIsInstance(payload["indicators"], dict)
        self.assertIsInstance(payload["levels"], dict)

    def test_m221_snapshot_has_no_dataframe_dependency(self):
        payload = asdict(self._snapshot())

        def contains_dataframe(value):
            if isinstance(value, pd.DataFrame):
                return True
            if isinstance(value, dict):
                return any(contains_dataframe(v) for v in value.values())
            if isinstance(value, (list, tuple)):
                return any(contains_dataframe(v) for v in value)
            return False

        self.assertFalse(contains_dataframe(payload))


if __name__ == "__main__":
    unittest.main()
