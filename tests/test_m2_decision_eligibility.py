import unittest
from dataclasses import replace

from market_intelligence.analysis.snapshot import (
    AnalysisSnapshot,
    IndicatorSnapshot,
    LevelSnapshot,
)
from market_intelligence.decision.eligibility import (
    EligibilityResult,
    evaluate_decision_eligibility,
)


class M232EligibilityGateTests(unittest.TestCase):

    def _snapshot(self, quality=None):
        return AnalysisSnapshot(
            symbol="AAPL",
            market="US",
            timeframe="1D",
            timestamp="2026-09-25T20:00:00",
            price=200.0,
            score=80,
            trend="UPTREND",
            signal="BUY CANDIDATE",
            indicators=IndicatorSnapshot(
                ema20=195.0,
                ema50=190.0,
                ema200=175.0,
                rsi14=60.0,
                macd=2.0,
                macd_signal=1.5,
                atr14=4.0,
                volume_ratio=1.2,
            ),
            levels=LevelSnapshot(
                support=190.0,
                resistance=205.0,
            ),
            trade_plan={},
            guidance={},
            market_data_quality=quality if quality is not None else {
                "valid": True,
                "signal_allowed": True,
                "reliability": "verified",
                "gap_count": 0,
                "issues": [],
            },
        )

    def test_m232_result_is_immutable(self):
        result = evaluate_decision_eligibility(self._snapshot())

        with self.assertRaises(Exception):
            result.eligible = False

    def test_m232_verified_snapshot_is_eligible(self):
        result = evaluate_decision_eligibility(self._snapshot())

        self.assertTrue(result.eligible)
        self.assertEqual(result.reason_codes, ("ELIGIBLE",))

    def test_m232_invalid_market_data_fails_closed(self):
        snapshot = self._snapshot({
            "valid": False,
            "signal_allowed": True,
            "reliability": "verified",
            "issues": ["invalid"],
        })

        result = evaluate_decision_eligibility(snapshot)

        self.assertFalse(result.eligible)
        self.assertIn("MARKET_DATA_INVALID", result.reason_codes)

    def test_m232_signal_blocked_fails_closed(self):
        snapshot = self._snapshot({
            "valid": True,
            "signal_allowed": False,
            "reliability": "verified",
            "issues": ["signal blocked"],
        })

        result = evaluate_decision_eligibility(snapshot)

        self.assertFalse(result.eligible)
        self.assertIn("SIGNAL_NOT_ALLOWED", result.reason_codes)

    def test_m232_unverified_reliability_fails_closed(self):
        snapshot = self._snapshot({
            "valid": True,
            "signal_allowed": True,
            "reliability": "unverified",
            "issues": [],
        })

        result = evaluate_decision_eligibility(snapshot)

        self.assertFalse(result.eligible)
        self.assertIn(
            "MARKET_DATA_NOT_VERIFIED",
            result.reason_codes,
        )

    def test_m232_missing_valid_fails_closed(self):
        snapshot = self._snapshot({
            "signal_allowed": True,
            "reliability": "verified",
        })

        result = evaluate_decision_eligibility(snapshot)

        self.assertFalse(result.eligible)
        self.assertIn("MARKET_DATA_INVALID", result.reason_codes)

    def test_m232_missing_signal_allowed_fails_closed(self):
        snapshot = self._snapshot({
            "valid": True,
            "reliability": "verified",
        })

        result = evaluate_decision_eligibility(snapshot)

        self.assertFalse(result.eligible)
        self.assertIn("SIGNAL_NOT_ALLOWED", result.reason_codes)

    def test_m232_missing_reliability_fails_closed(self):
        snapshot = self._snapshot({
            "valid": True,
            "signal_allowed": True,
        })

        result = evaluate_decision_eligibility(snapshot)

        self.assertFalse(result.eligible)
        self.assertIn(
            "MARKET_DATA_NOT_VERIFIED",
            result.reason_codes,
        )

    def test_m232_multiple_failures_are_preserved(self):
        snapshot = self._snapshot({
            "valid": False,
            "signal_allowed": False,
            "reliability": "unverified",
        })

        result = evaluate_decision_eligibility(snapshot)

        self.assertFalse(result.eligible)
        self.assertEqual(
            result.reason_codes,
            (
                "MARKET_DATA_INVALID",
                "SIGNAL_NOT_ALLOWED",
                "MARKET_DATA_NOT_VERIFIED",
            ),
        )

    def test_m232_schema_version_is_explicit(self):
        result = evaluate_decision_eligibility(self._snapshot())

        self.assertEqual(result.schema_version, "m2.3.2")

    def test_m232_rejects_non_snapshot(self):
        with self.assertRaises(TypeError):
            evaluate_decision_eligibility({})

    def test_m232_does_not_depend_on_trade_signal(self):
        snapshot = replace(
            self._snapshot(),
            signal="AVOID / WEAK",
            score=10,
        )

        result = evaluate_decision_eligibility(snapshot)

        self.assertTrue(result.eligible)


if __name__ == "__main__":
    unittest.main()

