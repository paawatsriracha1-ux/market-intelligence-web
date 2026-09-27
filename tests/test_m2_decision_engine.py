import unittest

from market_intelligence.analysis.snapshot import (
    AnalysisSnapshot,
    IndicatorSnapshot,
    LevelSnapshot,
)
from market_intelligence.decision.contract import (
    DecisionAction,
    DecisionResult,
)
from market_intelligence.decision.engine import evaluate_decision


def make_snapshot(
    *,
    score=90,
    signal="BUY / STRONG",
    valid=True,
    signal_allowed=True,
    reliability="verified",
):
    return AnalysisSnapshot(
        symbol="TEST",
        market="TEST",
        timeframe="1d",
        timestamp="2026-09-27T00:00:00",
        price=100.0,
        score=score,
        trend="UP",
        signal=signal,
        indicators=IndicatorSnapshot(
            ema20=100.0,
            ema50=99.0,
            ema200=95.0,
            rsi14=60.0,
            macd=1.0,
            macd_signal=0.5,
            atr14=2.0,
            volume_ratio=1.2,
        ),
        levels=LevelSnapshot(
            support=95.0,
            resistance=110.0,
        ),
        market_data_quality={
            "valid": valid,
            "signal_allowed": signal_allowed,
            "reliability": reliability,
        },
    )


class M234DecisionEngineTests(unittest.TestCase):

    def test_m234_returns_decision_result(self):
        result = evaluate_decision(make_snapshot())

        self.assertIsInstance(result, DecisionResult)

    def test_m234_verified_strong_buy_reaches_buy(self):
        result = evaluate_decision(make_snapshot())

        self.assertTrue(result.eligible)
        self.assertEqual(result.action, DecisionAction.BUY)
        self.assertTrue(result.actionable)
        self.assertEqual(result.confidence, 90)

    def test_m234_invalid_market_data_blocks_buy(self):
        result = evaluate_decision(
            make_snapshot(valid=False)
        )

        self.assertFalse(result.eligible)
        self.assertEqual(result.action, DecisionAction.NO_SIGNAL)
        self.assertFalse(result.actionable)
        self.assertEqual(result.confidence, 0)
        self.assertIn("MARKET_DATA_INVALID", result.reason_codes)

    def test_m234_signal_not_allowed_blocks_buy(self):
        result = evaluate_decision(
            make_snapshot(signal_allowed=False)
        )

        self.assertFalse(result.eligible)
        self.assertEqual(result.action, DecisionAction.NO_SIGNAL)
        self.assertFalse(result.actionable)
        self.assertEqual(result.confidence, 0)
        self.assertIn("SIGNAL_NOT_ALLOWED", result.reason_codes)

    def test_m234_unverified_market_data_blocks_buy(self):
        result = evaluate_decision(
            make_snapshot(reliability="unverified")
        )

        self.assertFalse(result.eligible)
        self.assertEqual(result.action, DecisionAction.NO_SIGNAL)
        self.assertFalse(result.actionable)
        self.assertEqual(result.confidence, 0)
        self.assertIn(
            "MARKET_DATA_NOT_VERIFIED",
            result.reason_codes,
        )

    def test_m234_high_score_cannot_bypass_gate(self):
        result = evaluate_decision(
            make_snapshot(
                score=100,
                signal="BUY / STRONG",
                valid=False,
            )
        )

        self.assertFalse(result.eligible)
        self.assertEqual(result.action, DecisionAction.NO_SIGNAL)
        self.assertFalse(result.actionable)

    def test_m234_watch_mapping(self):
        result = evaluate_decision(
            make_snapshot(
                score=70,
                signal="WATCH",
            )
        )

        self.assertTrue(result.eligible)
        self.assertEqual(result.action, DecisionAction.WATCH)
        self.assertFalse(result.actionable)

    def test_m234_hold_mapping(self):
        result = evaluate_decision(
            make_snapshot(
                score=50,
                signal="HOLD",
            )
        )

        self.assertTrue(result.eligible)
        self.assertEqual(result.action, DecisionAction.HOLD)
        self.assertFalse(result.actionable)

    def test_m234_avoid_mapping(self):
        result = evaluate_decision(
            make_snapshot(
                score=25,
                signal="AVOID / WEAK",
            )
        )

        self.assertTrue(result.eligible)
        self.assertEqual(result.action, DecisionAction.AVOID)
        self.assertFalse(result.actionable)

    def test_m234_unknown_signal_fails_closed(self):
        result = evaluate_decision(
            make_snapshot(
                score=100,
                signal="UNKNOWN",
            )
        )

        self.assertEqual(result.action, DecisionAction.NO_SIGNAL)
        self.assertFalse(result.actionable)
        self.assertEqual(result.confidence, 0)
        self.assertIn("UNMAPPED_SIGNAL", result.reason_codes)

    def test_m234_preserves_eligibility_provenance(self):
        result = evaluate_decision(
            make_snapshot(valid=False)
        )

        self.assertIn("MARKET_DATA_INVALID", result.reason_codes)
        self.assertIn("INELIGIBLE", result.reason_codes)

    def test_m234_eligible_provenance_is_preserved(self):
        result = evaluate_decision(make_snapshot())

        self.assertIn("ELIGIBLE", result.reason_codes)
        self.assertIn("STRONG_BUY", result.reason_codes)

    def test_m234_contract_schema_remains_m231(self):
        result = evaluate_decision(make_snapshot())

        self.assertEqual(result.schema_version, "m2.3.1")

    def test_m234_result_is_immutable(self):
        result = evaluate_decision(make_snapshot())

        with self.assertRaises(Exception):
            result.confidence = 0

    def test_m234_rejects_wrong_input_type(self):
        with self.assertRaises(TypeError):
            evaluate_decision({})


if __name__ == "__main__":
    unittest.main()
