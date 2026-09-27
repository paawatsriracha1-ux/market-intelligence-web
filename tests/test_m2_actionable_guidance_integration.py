import unittest
from unittest.mock import patch

from market_intelligence.analysis.snapshot import AnalysisSnapshot
from market_intelligence.decision.contract import (
    DecisionAction,
    DecisionResult,
)
from market_intelligence.decision.guidance import (
    evaluate_actionable_guidance,
)
from market_intelligence.decision.pipeline import (
    evaluate_safe_decision,
)
from market_intelligence.strategy.guidance import TechnicalGuidance


def make_guidance():
    return TechnicalGuidance(
        buy_trigger=100.0,
        buy_zone_low=95.0,
        buy_zone_high=99.0,
        sell_tp1=110.0,
        sell_tp2=120.0,
        stop_loss=90.0,
        support=94.0,
        resistance=110.0,
        confidence=80,
        regime="TREND",
        rationale=["integration test"],
    )


def make_decision(
    *,
    action=DecisionAction.BUY,
    confidence=90,
    eligible=True,
):
    return DecisionResult(
        action=action,
        confidence=confidence,
        eligible=eligible,
        reason_codes=("INTEGRATION_TEST",),
        reasons=("integration decision",),
    )


class M237ActionableGuidanceIntegrationTests(unittest.TestCase):

    @patch(
        "market_intelligence.decision.pipeline.evaluate_decision"
    )
    def test_safe_pipeline_buy_exposes_guidance(
        self,
        mock_engine,
    ):
        snapshot = object.__new__(AnalysisSnapshot)

        mock_engine.return_value = make_decision(
            action=DecisionAction.BUY,
            confidence=90,
            eligible=True,
        )

        decision = evaluate_safe_decision(snapshot)

        result = evaluate_actionable_guidance(
            decision,
            make_guidance(),
        )

        self.assertEqual(decision.action, DecisionAction.BUY)
        self.assertTrue(decision.eligible)

        self.assertTrue(result.actionable)
        self.assertEqual(result.action, DecisionAction.BUY)

        self.assertEqual(result.buy_trigger, 100.0)
        self.assertEqual(result.buy_zone_low, 95.0)
        self.assertEqual(result.buy_zone_high, 99.0)
        self.assertEqual(result.sell_tp1, 110.0)
        self.assertEqual(result.sell_tp2, 120.0)
        self.assertEqual(result.stop_loss, 90.0)

        self.assertEqual(result.confidence, 90)


    @patch(
        "market_intelligence.decision.pipeline.evaluate_decision"
    )
    def test_safe_pipeline_no_signal_hides_guidance(
        self,
        mock_engine,
    ):
        snapshot = object.__new__(AnalysisSnapshot)

        mock_engine.return_value = make_decision(
            action=DecisionAction.NO_SIGNAL,
            confidence=0,
            eligible=False,
        )

        decision = evaluate_safe_decision(snapshot)

        result = evaluate_actionable_guidance(
            decision,
            make_guidance(),
        )

        self.assertEqual(
            decision.action,
            DecisionAction.NO_SIGNAL,
        )

        self.assertFalse(result.actionable)

        self.assertIsNone(result.buy_trigger)
        self.assertIsNone(result.buy_zone_low)
        self.assertIsNone(result.buy_zone_high)
        self.assertIsNone(result.sell_tp1)
        self.assertIsNone(result.sell_tp2)
        self.assertIsNone(result.stop_loss)


    @patch(
        "market_intelligence.decision.pipeline.evaluate_decision"
    )
    def test_safe_pipeline_watch_cannot_become_actionable(
        self,
        mock_engine,
    ):
        snapshot = object.__new__(AnalysisSnapshot)

        mock_engine.return_value = make_decision(
            action=DecisionAction.WATCH,
            confidence=65,
            eligible=True,
        )

        decision = evaluate_safe_decision(snapshot)

        result = evaluate_actionable_guidance(
            decision,
            make_guidance(),
        )

        self.assertEqual(
            decision.action,
            DecisionAction.WATCH,
        )

        self.assertFalse(result.actionable)
        self.assertIsNone(result.buy_trigger)


    @patch(
        "market_intelligence.decision.pipeline.evaluate_decision"
    )
    def test_malformed_guidance_cannot_bypass_safe_buy(
        self,
        mock_engine,
    ):
        snapshot = object.__new__(AnalysisSnapshot)

        mock_engine.return_value = make_decision(
            action=DecisionAction.BUY,
            confidence=95,
            eligible=True,
        )

        decision = evaluate_safe_decision(snapshot)

        guidance = make_guidance()
        object.__setattr__(
            guidance,
            "stop_loss",
            105.0,
        )

        result = evaluate_actionable_guidance(
            decision,
            guidance,
        )

        self.assertFalse(result.actionable)

        self.assertEqual(
            result.action,
            DecisionAction.NO_SIGNAL,
        )

        self.assertEqual(
            result.reason,
            "INVALID_GUIDANCE_STRUCTURE",
        )

        self.assertIsNone(result.buy_trigger)
        self.assertIsNone(result.stop_loss)


if __name__ == "__main__":
    unittest.main()
