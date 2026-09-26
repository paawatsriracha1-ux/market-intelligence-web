import unittest
from dataclasses import asdict

import pandas as pd

from market_intelligence.analysis.snapshot import AnalysisSnapshot
from market_intelligence.analysis.adapter import build_analysis_snapshot


class M22SnapshotAdapterTests(unittest.TestCase):

    def _frame(self):
        df = pd.DataFrame([{
            "Date": pd.Timestamp("2026-09-25 20:00:00"),
            "Close": 225.50,
            "EMA20": 220.0,
            "EMA50": 215.0,
            "EMA200": 200.0,
            "RSI14": 62.5,
            "MACD": 1.20,
            "MACD_SIGNAL": 0.90,
            "ATR14": 4.50,
            "VOL_RATIO": 1.30,
            "SUPPORT20": 218.0,
            "RESISTANCE20": 228.0,
        }])

        df.attrs["market_data_symbol"] = "AAPL"
        df.attrs["market_data_timeframe"] = "1D"
        df.attrs["market_data_reliability"] = "verified"
        df.attrs["market_data_quality"] = {
            "valid": True,
            "signal_allowed": True,
            "issues": [],
        }

        return df

    def _plan(self):
        return {
            "score": 78,
            "trend": "UPTREND",
            "signal": "BUY CANDIDATE",
            "entry": 225.50,
            "stop": 216.50,
            "target": 243.50,
            "risk_reward": 2.0,
        }

    def _guidance(self):
        return {
            "buy_trigger": 228.50,
            "buy_zone_low": 220.0,
            "buy_zone_high": 225.0,
            "sell_tp1": 237.0,
            "sell_tp2": 246.0,
            "stop_loss": 216.0,
            "confidence": 80,
        }

    def test_m223_returns_analysis_snapshot(self):
        result = build_analysis_snapshot(
            self._frame(),
            self._plan(),
            self._guidance(),
            market="US",
        )

        self.assertIsInstance(result, AnalysisSnapshot)

    def test_m223_identity_comes_from_verified_metadata(self):
        result = build_analysis_snapshot(
            self._frame(),
            self._plan(),
            self._guidance(),
            market="US",
        )

        self.assertEqual(result.symbol, "AAPL")
        self.assertEqual(result.market, "US")
        self.assertEqual(result.timeframe, "1D")

    def test_m223_indicators_come_from_last_row(self):
        result = build_analysis_snapshot(
            self._frame(),
            self._plan(),
            self._guidance(),
            market="US",
        )

        self.assertEqual(result.price, 225.50)
        self.assertEqual(result.indicators.ema20, 220.0)
        self.assertEqual(result.indicators.ema50, 215.0)
        self.assertEqual(result.indicators.ema200, 200.0)
        self.assertEqual(result.indicators.rsi14, 62.5)
        self.assertEqual(result.indicators.macd, 1.20)
        self.assertEqual(result.indicators.macd_signal, 0.90)
        self.assertEqual(result.indicators.atr14, 4.50)
        self.assertEqual(result.indicators.volume_ratio, 1.30)

    def test_m223_levels_are_preserved(self):
        result = build_analysis_snapshot(
            self._frame(),
            self._plan(),
            self._guidance(),
            market="US",
        )

        self.assertEqual(result.levels.support, 218.0)
        self.assertEqual(result.levels.resistance, 228.0)

    def test_m223_trade_plan_is_preserved(self):
        result = build_analysis_snapshot(
            self._frame(),
            self._plan(),
            self._guidance(),
            market="US",
        )

        self.assertEqual(result.trade_plan["entry"], 225.50)
        self.assertEqual(result.trade_plan["stop"], 216.50)
        self.assertEqual(result.trade_plan["target"], 243.50)
        self.assertEqual(result.trade_plan["risk_reward"], 2.0)

    def test_m223_guidance_is_preserved(self):
        result = build_analysis_snapshot(
            self._frame(),
            self._plan(),
            self._guidance(),
            market="US",
        )

        self.assertEqual(result.guidance["buy_trigger"], 228.50)
        self.assertEqual(result.guidance["confidence"], 80)

    def test_m223_quality_metadata_is_preserved(self):
        result = build_analysis_snapshot(
            self._frame(),
            self._plan(),
            self._guidance(),
            market="US",
        )

        quality = result.market_data_quality

        self.assertTrue(quality["valid"])
        self.assertTrue(quality["signal_allowed"])
        self.assertEqual(quality["reliability"], "verified")

    def test_m223_output_contains_no_dataframe(self):
        result = build_analysis_snapshot(
            self._frame(),
            self._plan(),
            self._guidance(),
            market="US",
        )

        payload = asdict(result)

        def contains_dataframe(value):
            if isinstance(value, pd.DataFrame):
                return True
            if isinstance(value, dict):
                return any(contains_dataframe(v) for v in value.values())
            if isinstance(value, (list, tuple)):
                return any(contains_dataframe(v) for v in value)
            return False

        self.assertFalse(contains_dataframe(payload))

    def test_m223_rejects_empty_dataframe(self):
        with self.assertRaises(ValueError):
            build_analysis_snapshot(
                pd.DataFrame(),
                self._plan(),
                self._guidance(),
                market="US",
            )


if __name__ == "__main__":
    unittest.main()
