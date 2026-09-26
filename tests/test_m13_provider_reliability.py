from __future__ import annotations

import unittest
from unittest.mock import patch
import pandas as pd

from src.market_intelligence import services


def provider_frame(reliable=True):
    dates = pd.date_range("2026-01-01", periods=220, freq="D")
    close = pd.Series([100.0 + i * 0.1 for i in range(220)])
    frame = pd.DataFrame({
        "Date": dates,
        "Open": close.values,
        "High": (close + 1).values,
        "Low": (close - 1).values,
        "Close": close.values,
        "Volume": [1000 + i for i in range(220)],
    })
    frame.attrs["market_data_source"] = "test-provider"
    frame.attrs["market_data_reliability"] = "verified" if reliable else "unverified"
    frame.attrs["market_data_quality"] = {
        "valid": bool(reliable),
        "signal_allowed": bool(reliable),
        "rows": len(frame),
        "source_timestamp": dates[-1].isoformat(),
        "issues": [] if reliable else ["test_unreliable"],
    }
    return frame


class M13ProviderReliabilityTests(unittest.TestCase):
    def test_verified_provider_data_reaches_analysis(self):
        with patch.object(services.provider, "fetch", return_value=provider_frame(True)):
            df, plan = services.analyze_symbol("TEST", period="1Y")
        self.assertFalse(df.empty)
        self.assertEqual(df.attrs["market_data_reliability"], "verified")
        self.assertIsNotNone(plan)

    def test_missing_quality_metadata_fails_closed(self):
        frame = provider_frame(True)
        frame.attrs.pop("market_data_quality")
        with patch.object(services.provider, "fetch", return_value=frame):
            with self.assertRaisesRegex(ValueError, "metadata is missing"):
                services.analyze_symbol("TEST", period="1Y")

    def test_unverified_provider_data_fails_closed(self):
        frame = provider_frame(True)
        frame.attrs["market_data_reliability"] = "unverified"
        with patch.object(services.provider, "fetch", return_value=frame):
            with self.assertRaisesRegex(ValueError, "not verified"):
                services.analyze_symbol("TEST", period="1Y")

    def test_signal_ineligible_data_fails_closed(self):
        frame = provider_frame(True)
        frame.attrs["market_data_quality"]["signal_allowed"] = False
        with patch.object(services.provider, "fetch", return_value=frame):
            with self.assertRaisesRegex(ValueError, "not eligible for trading signals"):
                services.analyze_symbol("TEST", period="1Y")

    def test_trim_preserves_provider_reliability_metadata(self):
        frame = provider_frame(True)
        trimmed = services._trim_window(frame, 7)
        self.assertEqual(trimmed.attrs["market_data_source"], "test-provider")
        self.assertEqual(trimmed.attrs["market_data_reliability"], "verified")
        self.assertTrue(trimmed.attrs["market_data_quality"]["signal_allowed"])


if __name__ == "__main__":
    unittest.main()
