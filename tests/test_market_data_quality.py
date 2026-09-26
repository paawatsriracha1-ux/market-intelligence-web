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

    def test_m12_fresh_intraday_frame_reports_reliability_metadata(self):
        frame, report = validate_market_frame(valid_frame(), interval="5m", now=pd.Timestamp("2026-09-25 03:10"), enforce_freshness=True, enforce_gaps=True)
        self.assertEqual(len(frame), 2); self.assertEqual(report.interval, "5m")
        self.assertEqual(report.age_seconds, 300.0); self.assertEqual(report.stale_after_seconds, 900.0)
        self.assertEqual(report.gap_count, 0); self.assertTrue(report.signal_allowed)

    def test_m12_stale_intraday_data_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "stale_market_data"):
            validate_market_frame(valid_frame(), interval="5m", now=pd.Timestamp("2026-09-25 03:30"), enforce_freshness=True)

    def test_m12_large_intraday_gap_fails_closed(self):
        frame = valid_frame(); frame.loc[1, "Date"] = pd.Timestamp("2026-09-25 03:30")
        with self.assertRaisesRegex(ValueError, "market_data_gap"):
            validate_market_frame(frame, interval="5m", now=pd.Timestamp("2026-09-25 03:35"), enforce_gaps=True)

    def test_m12_historical_call_does_not_enforce_wall_clock_freshness(self):
        _, report = validate_market_frame(valid_frame(), interval="5m", now=pd.Timestamp("2026-10-01"))
        self.assertGreater(report.age_seconds, report.stale_after_seconds); self.assertTrue(report.signal_allowed)

    def test_m14_session_boundary_is_not_false_gap(self):
        frame = pd.concat([valid_frame(), valid_frame().assign(Date=pd.to_datetime(["2026-09-26 03:00", "2026-09-26 03:05"]))], ignore_index=True)
        _, report = validate_market_frame(frame, interval="5m", now=pd.Timestamp("2026-09-26 03:10"), enforce_gaps=True, session_aware=True)
        self.assertEqual(report.gap_count, 0); self.assertTrue(report.signal_allowed)

    def test_m14_closed_session_does_not_false_stale(self):
        _, report = validate_market_frame(valid_frame(), interval="5m", now=pd.Timestamp("2026-09-26 12:00"), enforce_freshness=True, session_aware=True)
        self.assertGreater(report.age_seconds, report.stale_after_seconds); self.assertTrue(report.signal_allowed)

    def test_m14_same_session_stale_data_still_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "stale_market_data"):
            validate_market_frame(valid_frame(), interval="5m", now=pd.Timestamp("2026-09-25 03:30"), enforce_freshness=True, session_aware=True)

    def test_m14_same_session_gap_still_fails_closed(self):
        frame = valid_frame(); frame.loc[1, "Date"] = pd.Timestamp("2026-09-25 03:30")
        with self.assertRaisesRegex(ValueError, "market_data_gap"):
            validate_market_frame(frame, interval="5m", now=pd.Timestamp("2026-09-25 03:35"), enforce_gaps=True, session_aware=True)

if __name__ == "__main__": unittest.main()
