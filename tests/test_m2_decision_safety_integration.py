import unittest

from market_intelligence.analysis.snapshot import (
    AnalysisSnapshot,
    IndicatorSnapshot,
    LevelSnapshot,
)
from market_intelligence.decision.contract import DecisionAction
from market_intelligence.decision.engine import evaluate_decision
from market_intelligence.decision.safety import (
    enforce_decision_safety,
    is_safe_actionable,
)


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


class M235DecisionSafetyIntegrationTests(unittest.TestCase):

    def test_m235_engine_buy_survives_safety_boundary(self):
        decision = evaluate_decision(make_snapshot())

        safe = enforce_decision_safety(decision)

        self.assertEqual(decision.action, DecisionAction.BUY)
        self.assertIs(safe, decision)
        self.assertTrue(is_safe_actionable(safe))

    def test_m235_engine_watch_survives_without_becoming_actionable(self):
        decision = evaluate_decision(
            make_snapshot(
                score=65,
                signal="WATCH",
            )
        )

        safe = enforce_decision_safety(decision)

        self.assertEqual(decision.action, DecisionAction.WATCH)
        self.assertIs(safe, decision)
        self.assertFalse(is_safe_actionable(safe))

    def test_m235_engine_hold_survives_without_becoming_actionable(self):
        decision = evaluate_decision(
            make_snapshot(
                score=50,
                signal="HOLD",
            )
        )

        safe = enforce_decision_safety(decision)

        self.assertEqual(decision.action, DecisionAction.HOLD)
        self.assertIs(safe, decision)
        self.assertFalse(is_safe_actionable(safe))

    def test_m235_engine_avoid_survives_without_becoming_actionable(self):
        decision = evaluate_decision(
            make_snapshot(
                score=25,
                signal="AVOID / WEAK",
            )
        )

        safe = enforce_decision_safety(decision)

        self.assertEqual(decision.action, DecisionAction.AVOID)
        self.assertIs(safe, decision)
        self.assertFalse(is_safe_actionable(safe))

    def test_m235_invalid_market_data_cannot_become_actionable(self):
        decision = evaluate_decision(
            make_snapshot(
                score=100,
                signal="BUY / STRONG",
                valid=False,
            )
        )

        safe = enforce_decision_safety(decision)

        self.assertNotEqual(safe.action, DecisionAction.BUY)
        self.assertFalse(is_safe_actionable(safe))
        self.assertFalse(safe.eligible)

    def test_m235_unverified_market_data_cannot_become_actionable(self):
        decision = evaluate_decision(
            make_snapshot(
                score=100,
                signal="BUY / STRONG",
                reliability="unverified",
            )
        )

        safe = enforce_decision_safety(decision)

        self.assertNotEqual(safe.action, DecisionAction.BUY)
        self.assertFalse(is_safe_actionable(safe))
        self.assertFalse(safe.eligible)

    def test_m235_signal_not_allowed_cannot_become_actionable(self):
        decision = evaluate_decision(
            make_snapshot(
                score=100,
                signal="BUY / STRONG",
                signal_allowed=False,
            )
        )

        safe = enforce_decision_safety(decision)

        self.assertNotEqual(safe.action, DecisionAction.BUY)
        self.assertFalse(is_safe_actionable(safe))
        self.assertFalse(safe.eligible)

    def test_m235_preserves_engine_provenance(self):
        decision = evaluate_decision(make_snapshot())

        original_codes = decision.reason_codes
        original_reasons = decision.reasons

        safe = enforce_decision_safety(decision)

        self.assertEqual(safe.reason_codes, original_codes)
        self.assertEqual(safe.reasons, original_reasons)


if __name__ == "__main__":
    unittest.main()

