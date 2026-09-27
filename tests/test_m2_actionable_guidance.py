import unittest

from market_intelligence.decision.contract import (
    DecisionAction,
    DecisionResult,
)
from market_intelligence.decision.guidance import (
    ActionableGuidance,
    evaluate_actionable_guidance,
)
from market_intelligence.strategy.guidance import TechnicalGuidance


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
        reason_codes=(),
        reasons=(),
    )


def make_guidance(**overrides):
    values = {
        "buy_trigger": 100.0,
        "buy_zone_low": 95.0,
        "buy_zone_high": 99.0,
        "sell_tp1": 110.0,
        "sell_tp2": 120.0,
        "stop_loss": 90.0,
        "support": 94.0,
        "resistance": 110.0,
        "confidence": 80,
        "regime": "TREND",
        "rationale": ["test guidance"],
    }

    values.update(overrides)

    return TechnicalGuidance(**values)


class M237ActionableGuidanceTests(unittest.TestCase):

    def test_m237_valid_safe_buy_is_actionable(self):
        decision = make_decision()
        guidance = make_guidance()

        result = evaluate_actionable_guidance(
            decision,
            guidance,
        )

        self.assertIsInstance(result, ActionableGuidance)
        self.assertTrue(result.actionable)
        self.assertEqual(result.action, DecisionAction.BUY)

        self.assertEqual(result.buy_trigger, 100.0)
        self.assertEqual(result.buy_zone_low, 95.0)
        self.assertEqual(result.buy_zone_high, 99.0)

        self.assertEqual(result.sell_tp1, 110.0)
        self.assertEqual(result.sell_tp2, 120.0)
        self.assertEqual(result.stop_loss, 90.0)

        self.assertEqual(result.confidence, 90)
        self.assertEqual(result.reason, "SAFE_BUY_GUIDANCE")


    def test_m237_no_signal_does_not_expose_levels(self):
        decision = make_decision(
            action=DecisionAction.NO_SIGNAL,
            confidence=0,
            eligible=False,
        )

        guidance = make_guidance()

        result = evaluate_actionable_guidance(
            decision,
            guidance,
        )

        self.assertFalse(result.actionable)
        self.assertEqual(
            result.action,
            DecisionAction.NO_SIGNAL,
        )

        self.assertIsNone(result.buy_trigger)
        self.assertIsNone(result.buy_zone_low)
        self.assertIsNone(result.buy_zone_high)

        self.assertIsNone(result.sell_tp1)
        self.assertIsNone(result.sell_tp2)
        self.assertIsNone(result.stop_loss)

        self.assertEqual(result.confidence, 0)


    def test_m237_invalid_guidance_structure_fails_closed(self):
        decision = make_decision()

        guidance = make_guidance(
            stop_loss=105.0,
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
        self.assertIsNone(result.sell_tp1)
        self.assertIsNone(result.stop_loss)


    def test_m237_wrong_decision_type_is_rejected(self):
        guidance = make_guidance()

        with self.assertRaises(TypeError):
            evaluate_actionable_guidance(
                {},
                guidance,
            )


    def test_m237_wrong_guidance_type_is_rejected(self):
        decision = make_decision()

        with self.assertRaises(TypeError):
            evaluate_actionable_guidance(
                decision,
                {},
            )


if __name__ == "__main__":
    unittest.main()
