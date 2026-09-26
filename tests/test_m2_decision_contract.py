import unittest
from dataclasses import FrozenInstanceError

from market_intelligence.decision.contract import (
    DecisionAction,
    DecisionResult,
    VALID_DECISION_ACTIONS,
)


class M231DecisionContractTests(unittest.TestCase):

    def _result(self, **overrides):
        values = {
            "action": DecisionAction.WATCH,
            "confidence": 65,
            "eligible": True,
            "reason_codes": (
                "TREND_UP",
                "WAIT_CONFIRMATION",
            ),
            "reasons": (
                "Trend structure is positive.",
                "Entry confirmation is still required.",
            ),
        }

        values.update(overrides)
        return DecisionResult(**values)

    def test_m231_allowed_actions_are_locked(self):
        self.assertEqual(
            VALID_DECISION_ACTIONS,
            frozenset({
                "BUY",
                "WATCH",
                "HOLD",
                "AVOID",
                "NO_SIGNAL",
            }),
        )

    def test_m231_result_is_immutable(self):
        result = self._result()

        with self.assertRaises(FrozenInstanceError):
            result.confidence = 99

    def test_m231_confidence_is_bounded(self):
        with self.assertRaises(ValueError):
            self._result(confidence=-1)

        with self.assertRaises(ValueError):
            self._result(confidence=101)

    def test_m231_confidence_rejects_bool(self):
        with self.assertRaises(TypeError):
            self._result(confidence=True)

    def test_m231_action_requires_enum(self):
        with self.assertRaises(TypeError):
            self._result(action="BUY")

    def test_m231_ineligible_buy_fails_closed(self):
        with self.assertRaises(ValueError):
            self._result(
                action=DecisionAction.BUY,
                eligible=False,
            )

    def test_m231_no_signal_requires_zero_confidence(self):
        with self.assertRaises(ValueError):
            self._result(
                action=DecisionAction.NO_SIGNAL,
                confidence=10,
            )

    def test_m231_valid_no_signal(self):
        result = self._result(
            action=DecisionAction.NO_SIGNAL,
            confidence=0,
            eligible=False,
            reason_codes=("NO_ELIGIBLE_SIGNAL",),
            reasons=("No eligible signal is available.",),
        )

        self.assertFalse(result.actionable)

    def test_m231_buy_is_actionable_only_when_eligible(self):
        result = self._result(
            action=DecisionAction.BUY,
            confidence=82,
            eligible=True,
        )

        self.assertTrue(result.actionable)

    def test_m231_watch_is_not_actionable(self):
        result = self._result(
            action=DecisionAction.WATCH,
            eligible=True,
        )

        self.assertFalse(result.actionable)

    def test_m231_reason_codes_cannot_be_duplicated(self):
        with self.assertRaises(ValueError):
            self._result(
                reason_codes=(
                    "TREND_UP",
                    "TREND_UP",
                )
            )

    def test_m231_reason_codes_reject_empty_value(self):
        with self.assertRaises(ValueError):
            self._result(
                reason_codes=("TREND_UP", ""),
            )

    def test_m231_serializes_to_plain_dict(self):
        result = self._result()

        payload = result.to_dict()

        self.assertIsInstance(payload, dict)
        self.assertEqual(payload["action"], "WATCH")
        self.assertEqual(payload["confidence"], 65)
        self.assertTrue(payload["eligible"])
        self.assertIsInstance(
            payload["reason_codes"],
            list,
        )
        self.assertIsInstance(
            payload["reasons"],
            list,
        )

    def test_m231_schema_version_is_explicit(self):
        result = self._result()

        self.assertEqual(
            result.schema_version,
            "m2.3.1",
        )


if __name__ == "__main__":
    unittest.main()
