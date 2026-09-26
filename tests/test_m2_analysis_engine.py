import unittest
import numpy as np
import pandas as pd

from market_intelligence.indicators.core import (
    add_indicators,
    detect_trend,
    technical_score,
)


def make_market_frame(rows=260, start=100.0, step=0.25):
    close = start + np.arange(rows) * step

    return pd.DataFrame({
        "Date": pd.date_range("2025-01-01", periods=rows, freq="D"),
        "Open": close - 0.20,
        "High": close + 1.00,
        "Low": close - 1.00,
        "Close": close,
        "Volume": np.linspace(1_000_000, 2_000_000, rows),
    })


class M2AnalysisEngineTests(unittest.TestCase):

    def setUp(self):
        self.raw = make_market_frame()
        self.df = add_indicators(self.raw)
        self.row = self.df.iloc[-1]

    def test_m21_required_indicator_columns_exist(self):
        required = {
            "EMA20", "EMA50", "EMA200",
            "RSI14",
            "MACD", "MACD_SIGNAL", "MACD_HIST",
            "BB_MID", "BB_UPPER", "BB_LOWER",
            "ATR14",
            "VOL_MA20", "VOL_RATIO",
            "SUPPORT20", "RESISTANCE20",
            "PREV_SUPPORT20", "PREV_RESISTANCE20",
            "RETURN1D", "ATR_PCT",
        }

        self.assertTrue(required.issubset(self.df.columns))

    def test_m21_ema_order_for_uptrend(self):
        self.assertGreater(self.row["EMA20"], self.row["EMA50"])
        self.assertGreater(self.row["EMA50"], self.row["EMA200"])

    def test_m21_rsi_is_bounded(self):
        valid = self.df["RSI14"].dropna()

        self.assertTrue((valid >= 0).all())
        self.assertTrue((valid <= 100).all())

    def test_m21_macd_identity(self):
        expected = self.df["MACD"] - self.df["MACD_SIGNAL"]

        np.testing.assert_allclose(
            self.df["MACD_HIST"],
            expected,
            rtol=1e-10,
            atol=1e-10,
        )

    def test_m21_bollinger_band_order(self):
        valid = self.df.dropna(
            subset=["BB_LOWER", "BB_MID", "BB_UPPER"]
        )

        self.assertTrue(
            (valid["BB_LOWER"] <= valid["BB_MID"]).all()
        )
        self.assertTrue(
            (valid["BB_MID"] <= valid["BB_UPPER"]).all()
        )

    def test_m21_atr_is_positive(self):
        valid = self.df["ATR14"].dropna()

        self.assertTrue((valid > 0).all())

    def test_m21_volume_ratio_is_non_negative(self):
        valid = self.df["VOL_RATIO"].dropna()

        self.assertTrue((valid >= 0).all())

    def test_m21_support_resistance_enclose_close(self):
        valid = self.df.dropna(
            subset=["SUPPORT20", "RESISTANCE20"]
        )

        self.assertTrue(
            (valid["SUPPORT20"] <= valid["Close"]).all()
        )
        self.assertTrue(
            (valid["RESISTANCE20"] >= valid["Close"]).all()
        )

    def test_m21_prior_structure_excludes_current_bar(self):
        i = len(self.df) - 1

        expected_support = self.raw["Low"].iloc[i-20:i].min()
        expected_resistance = self.raw["High"].iloc[i-20:i].max()

        self.assertAlmostEqual(
            self.row["PREV_SUPPORT20"],
            expected_support,
        )
        self.assertAlmostEqual(
            self.row["PREV_RESISTANCE20"],
            expected_resistance,
        )

    def test_m21_detects_uptrend(self):
        trend = detect_trend(self.row)

        self.assertIn(
            trend,
            {"UPTREND", "STRONG UPTREND"},
        )

    def test_m21_score_is_bounded(self):
        score, parts = technical_score(self.row)

        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)

        self.assertEqual(
            set(parts),
            {"trend", "momentum", "volume", "structure", "risk"},
        )

    def test_m21_score_equals_component_sum(self):
        score, parts = technical_score(self.row)

        expected = max(0, min(100, sum(parts.values())))

        self.assertEqual(score, expected)


if __name__ == "__main__":
    unittest.main()