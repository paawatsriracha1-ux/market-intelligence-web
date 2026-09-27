from __future__ import annotations

import unittest

from market_intelligence.decision.contract import DecisionAction
from market_intelligence.decision.policy import (
    DecisionPolicyResult,
    evaluate_decision_policy,
)


class M233DecisionPolicyTests(unittest.TestCase):

    def test_m233_result_is_immutable(self):
        result = DecisionPolicyResult(
            action=DecisionAction.BUY,
            confidence=90,
            reason_codes=("STRONG_BUY",),
            reasons=("Strong bullish setup.",),
        )

        with self.assertRaises(Exception):
            result.confidence = 10

    def test_m233_schema_version_is_explicit(self):
        result = DecisionPolicyResult(
            action=DecisionAction.WATCH,
            confidence=60,
            reason_codes=("WATCH_SETUP",),
            reasons=("Setup requires confirmation.",),
        )

        self.assertEqual(result.schema_version, "m2.3.3")

    def test_m233_buy_mapping(self):
        result = evaluate_decision_policy(
            eligible=True,
            score=85,
            signal="BUY / STRONG",
        )

        self.assertEqual(result.action, DecisionAction.BUY)
        self.assertTrue(result.actionable)
        self.assertGreater(result.confidence, 0)

    def test_m233_watch_mapping(self):
        result = evaluate_decision_policy(
            eligible=True,
            score=65,
            signal="WATCH",
        )

        self.assertEqual(result.action, DecisionAction.WATCH)
        self.assertFalse(result.actionable)

    def test_m233_hold_mapping(self):
        result = evaluate_decision_policy(
            eligible=True,
            score=50,
            signal="HOLD",
        )

        self.assertEqual(result.action, DecisionAction.HOLD)
        self.assertFalse(result.actionable)

    def test_m233_avoid_mapping(self):
        result = evaluate_decision_policy(
            eligible=True,
            score=25,
            signal="AVOID / WEAK",
        )

        self.assertEqual(result.action, DecisionAction.AVOID)
        self.assertFalse(result.actionable)

    def test_m233_ineligible_fails_closed(self):
        result = evaluate_decision_policy(
            eligible=False,
            score=95,
            signal="BUY / STRONG",
        )

        self.assertEqual(result.action, DecisionAction.NO_SIGNAL)
        self.assertEqual(result.confidence, 0)
        self.assertFalse(result.actionable)
        self.assertIn("INELIGIBLE", result.reason_codes)

    def test_m233_unknown_signal_fails_closed(self):
        result = evaluate_decision_policy(
            eligible=True,
            score=90,
            signal="UNKNOWN",
        )

        self.assertEqual(result.action, DecisionAction.NO_SIGNAL)
        self.assertEqual(result.confidence, 0)
        self.assertFalse(result.actionable)

    def test_m233_score_is_bounded(self):
        with self.assertRaises(ValueError):
            evaluate_decision_policy(
                eligible=True,
                score=101,
                signal="BUY / STRONG",
            )

    def test_m233_bool_score_is_rejected(self):
        with self.assertRaises(TypeError):
            evaluate_decision_policy(
                eligible=True,
                score=True,
                signal="BUY / STRONG",
            )

    def test_m233_eligibility_requires_bool(self):
        with self.assertRaises(TypeError):
            evaluate_decision_policy(
                eligible=1,
                score=80,
                signal="BUY / STRONG",
            )

    def test_m233_serializes_to_plain_dict(self):
        result = evaluate_decision_policy(
            eligible=True,
            score=85,
            signal="BUY / STRONG",
        )

        payload = result.to_dict()

        self.assertIsInstance(payload, dict)
        self.assertIsInstance(payload["action"], str)
        self.assertIsInstance(payload["reason_codes"], list)
        self.assertIsInstance(payload["reasons"], list)
        self.assertEqual(payload["schema_version"], "m2.3.3")


if __name__ == "__main__":
    unittest.main()
