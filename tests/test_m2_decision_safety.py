import unittest
from dataclasses import FrozenInstanceError

from market_intelligence.decision.contract import (
    DecisionAction,
    DecisionResult,
)
from market_intelligence.decision.safety import (
    enforce_decision_safety,
    is_safe_actionable,
)


def make_result(
    *,
    action=DecisionAction.BUY,
    confidence=90,
    eligible=True,
    reason_codes=("ELIGIBLE", "BUY"),
    reasons=("Eligible.", "Strong BUY signal."),
):
    return DecisionResult(
        action=action,
        confidence=confidence,
        eligible=eligible,
        reason_codes=reason_codes,
        reasons=reasons,
    )


class M235DecisionSafetyTests(unittest.TestCase):

    def test_m235_accepts_valid_buy(self):
        result = make_result()

        safe = enforce_decision_safety(result)

        self.assertIs(safe, result)
        self.assertEqual(safe.action, DecisionAction.BUY)
        self.assertTrue(safe.eligible)
        self.assertEqual(safe.confidence, 90)

    def test_m235_valid_buy_is_actionable(self):
        self.assertTrue(is_safe_actionable(make_result()))

    def test_m235_rejects_wrong_input_type(self):
        with self.assertRaises(TypeError):
            enforce_decision_safety({})

    def test_m235_ineligible_buy_fails_closed(self):
        # Construct an otherwise impossible state by bypassing
        # DecisionResult.__post_init__. This verifies the boundary
        # independently from the contract's own protection.
        result = object.__new__(DecisionResult)

        object.__setattr__(result, "action", DecisionAction.BUY)
        object.__setattr__(result, "confidence", 90)
        object.__setattr__(result, "eligible", False)
        object.__setattr__(result, "reason_codes", ("TEST",))
        object.__setattr__(result, "reasons", ("Synthetic unsafe state.",))
        object.__setattr__(result, "schema_version", "m2.3.1")

        safe = enforce_decision_safety(result)

        self.assertEqual(safe.action, DecisionAction.NO_SIGNAL)
        self.assertEqual(safe.confidence, 0)
        self.assertFalse(safe.eligible)
        self.assertIn("SAFETY_BOUNDARY_BLOCKED", safe.reason_codes)
        self.assertIn("BUY_REQUIRES_ELIGIBLE", safe.reason_codes)

    def test_m235_zero_confidence_buy_fails_closed(self):
        result = object.__new__(DecisionResult)

        object.__setattr__(result, "action", DecisionAction.BUY)
        object.__setattr__(result, "confidence", 0)
        object.__setattr__(result, "eligible", True)
        object.__setattr__(result, "reason_codes", ("TEST",))
        object.__setattr__(result, "reasons", ("Synthetic unsafe state.",))
        object.__setattr__(result, "schema_version", "m2.3.1")

        safe = enforce_decision_safety(result)

        self.assertEqual(safe.action, DecisionAction.NO_SIGNAL)
        self.assertEqual(safe.confidence, 0)
        self.assertFalse(safe.eligible)
        self.assertIn(
            "BUY_REQUIRES_POSITIVE_CONFIDENCE",
            safe.reason_codes,
        )

    def test_m235_no_signal_zero_confidence_passes(self):
        result = make_result(
            action=DecisionAction.NO_SIGNAL,
            confidence=0,
            eligible=False,
            reason_codes=("NO_SIGNAL",),
            reasons=("No signal.",),
        )

        safe = enforce_decision_safety(result)

        self.assertIs(safe, result)
        self.assertFalse(is_safe_actionable(result))

    def test_m235_watch_is_not_actionable(self):
        result = make_result(
            action=DecisionAction.WATCH,
            confidence=65,
            eligible=True,
            reason_codes=("WATCH",),
            reasons=("Watch.",),
        )

        self.assertFalse(is_safe_actionable(result))

    def test_m235_hold_is_not_actionable(self):
        result = make_result(
            action=DecisionAction.HOLD,
            confidence=50,
            eligible=True,
            reason_codes=("HOLD",),
            reasons=("Hold.",),
        )

        self.assertFalse(is_safe_actionable(result))

    def test_m235_avoid_is_not_actionable(self):
        result = make_result(
            action=DecisionAction.AVOID,
            confidence=25,
            eligible=True,
            reason_codes=("AVOID",),
            reasons=("Avoid.",),
        )

        self.assertFalse(is_safe_actionable(result))

    def test_m235_preserves_provenance_when_blocking(self):
        result = object.__new__(DecisionResult)

        object.__setattr__(result, "action", DecisionAction.BUY)
        object.__setattr__(result, "confidence", 80)
        object.__setattr__(result, "eligible", False)
        object.__setattr__(
            result,
            "reason_codes",
            ("MARKET_DATA_INVALID", "BUY"),
        )
        object.__setattr__(
            result,
            "reasons",
            ("Market data invalid.", "BUY policy."),
        )
        object.__setattr__(result, "schema_version", "m2.3.1")

        safe = enforce_decision_safety(result)

        self.assertIn("MARKET_DATA_INVALID", safe.reason_codes)
        self.assertIn("BUY", safe.reason_codes)
        self.assertIn("SAFETY_BOUNDARY_BLOCKED", safe.reason_codes)

        self.assertIn("Market data invalid.", safe.reasons)
        self.assertIn("BUY policy.", safe.reasons)

    def test_m235_block_codes_have_no_duplicates(self):
        result = object.__new__(DecisionResult)

        object.__setattr__(result, "action", DecisionAction.BUY)
        object.__setattr__(result, "confidence", 0)
        object.__setattr__(result, "eligible", False)
        object.__setattr__(
            result,
            "reason_codes",
            ("SAFETY_BOUNDARY_BLOCKED",),
        )
        object.__setattr__(result, "reasons", ("Existing reason.",))
        object.__setattr__(result, "schema_version", "m2.3.1")

        safe = enforce_decision_safety(result)

        self.assertEqual(
            len(safe.reason_codes),
            len(set(safe.reason_codes)),
        )

    def test_m235_result_remains_immutable(self):
        safe = enforce_decision_safety(make_result())

        with self.assertRaises(FrozenInstanceError):
            safe.confidence = 1


if __name__ == "__main__":
    unittest.main()
