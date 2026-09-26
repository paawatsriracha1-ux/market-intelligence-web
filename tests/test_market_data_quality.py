from __future__ import annotations
import unittest
import pandas as pd
from src.market_intelligence.data.quality import validate_market_frame

def valid_frame():
    return pd.DataFrame({"Date": pd.to_datetime(["2026-09-25 03:00", "2026-09-25 03:05"]), "Open": [10.0,10.2], "High": [10.5,10.6], "Low": [9.9,10.1], "Close": [10.2,10.4], "Volume": [1000,1200]})

class MarketDataQualityTests(unittest.TestCase):
    def test_valid_frame_is_signal_eligible(self):
        frame, report = validate_market_frame(valid_frame())
        self.assertEqual(len(frame), 2); self.assertTrue(report.valid); self.assertTrue(report.signal_allowed)
        self.assertEqual(report.source_timestamp, "2026-09-25T03:05:00")
    def test_duplicate_timestamp_fails_closed(self):
        frame=valid_frame(); frame.loc[1,"Date"]=frame.loc[0,"Date"]
        with self.assertRaisesRegex(ValueError,"duplicate_timestamp"): validate_market_frame(frame)
    def test_non_monotonic_timestamp_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"non_monotonic_timestamp"): validate_market_frame(valid_frame().iloc[::-1].reset_index(drop=True))
    def test_invalid_ohlc_relationship_fails_closed(self):
        frame=valid_frame(); frame.loc[1,"High"]=10.0
        with self.assertRaisesRegex(ValueError,"invalid_ohlc_relationship"): validate_market_frame(frame)
    def test_negative_volume_fails_closed(self):
        frame=valid_frame(); frame.loc[1,"Volume"]=-1
        with self.assertRaisesRegex(ValueError,"negative_volume"): validate_market_frame(frame)
    def test_non_positive_price_fails_closed(self):
        frame=valid_frame(); frame.loc[1,"Close"]=0
        with self.assertRaisesRegex(ValueError,"non_positive_price"): validate_market_frame(frame)

if __name__ == "__main__": unittest.main()
