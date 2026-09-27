from __future__ import annotations

import unittest
from dataclasses import replace
from unittest.mock import patch

from market_intelligence.analysis.snapshot import AnalysisSnapshot
from market_intelligence.decision.contract import (
    DecisionAction,
    DecisionResult,
)
from market_intelligence.decision.pipeline import evaluate_safe_decision


def make_result(
    *,
    action: DecisionAction = DecisionAction.BUY,
    confidence: int = 80,
    eligible: bool = True,
    reason_codes: tuple[str, ...] = ("ENGINE_OK",),
    reasons: tuple[str, ...] = ("engine decision",),
) -> DecisionResult:
    return DecisionResult(
        action=action,
        confidence=confidence,
        eligible=eligible,
        reason_codes=reason_codes,
        reasons=reasons,
    )


class M236SafeDecisionPipelineTests(unittest.TestCase):

    def test_m236_rejects_wrong_input_type(self):
        with self.assertRaises(TypeError):
            evaluate_safe_decision({})  # type: ignore[arg-type]

    @patch(
        "market_intelligence.decision.pipeline.enforce_decision_safety"
    )
    @patch(
        "market_intelligence.decision.pipeline.evaluate_decision"
    )
    def test_m236_calls_engine_then_safety(
        self,
        mock_engine,
        mock_safety,
    ):
        snapshot = object.__new__(AnalysisSnapshot)

        engine_result = make_result()
        safe_result = make_result()

        mock_engine.return_value = engine_result
        mock_safety.return_value = safe_result

        result = evaluate_safe_decision(snapshot)

        mock_engine.assert_called_once_with(snapshot)
        mock_safety.assert_called_once_with(engine_result)

        self.assertIs(result, safe_result)

    @patch(
        "market_intelligence.decision.pipeline.evaluate_decision"
    )
    def test_m236_rejects_invalid_engine_output(
        self,
        mock_engine,
    ):
        snapshot = object.__new__(AnalysisSnapshot)
        mock_engine.return_value = {}

        with self.assertRaises(TypeError):
            evaluate_safe_decision(snapshot)

    @patch(
        "market_intelligence.decision.pipeline.enforce_decision_safety"
    )
    @patch(
        "market_intelligence.decision.pipeline.evaluate_decision"
    )
    def test_m236_rejects_invalid_safety_output(
        self,
        mock_engine,
        mock_safety,
    ):
        snapshot = object.__new__(AnalysisSnapshot)

        mock_engine.return_value = make_result()
        mock_safety.return_value = {}

        with self.assertRaises(TypeError):
            evaluate_safe_decision(snapshot)

    @patch(
        "market_intelligence.decision.pipeline.evaluate_decision"
    )
    def test_m236_valid_buy_survives_pipeline(
        self,
        mock_engine,
    ):
        snapshot = object.__new__(AnalysisSnapshot)

        mock_engine.return_value = make_result(
            action=DecisionAction.BUY,
            confidence=85,
            eligible=True,
        )

        result = evaluate_safe_decision(snapshot)

        self.assertEqual(result.action, DecisionAction.BUY)
        self.assertEqual(result.confidence, 85)
        self.assertTrue(result.eligible)

    def test_m236_contract_rejects_ineligible_buy(self):
        with self.assertRaises(ValueError):
            make_result(
                action=DecisionAction.BUY,
                confidence=90,
                eligible=False,
            )

    @patch(
        "market_intelligence.decision.pipeline.evaluate_decision"
    )
    def test_m236_zero_confidence_buy_is_blocked(
        self,
        mock_engine,
    ):
        snapshot = object.__new__(AnalysisSnapshot)

        mock_engine.return_value = make_result(
            action=DecisionAction.BUY,
            confidence=0,
            eligible=True,
        )

        result = evaluate_safe_decision(snapshot)

        self.assertEqual(result.action, DecisionAction.NO_SIGNAL)
        self.assertEqual(result.confidence, 0)
        self.assertFalse(result.eligible)

        self.assertIn(
            "BUY_REQUIRES_POSITIVE_CONFIDENCE",
            result.reason_codes,
        )

    @patch(
        "market_intelligence.decision.pipeline.evaluate_decision"
    )
    def test_m236_preserves_engine_provenance_when_blocked(
        self,
        mock_engine,
    ):
        snapshot = object.__new__(AnalysisSnapshot)

        mock_engine.return_value = make_result(
            action=DecisionAction.BUY,
            confidence=0,
            eligible=True,
            reason_codes=("ENGINE_ALPHA",),
            reasons=("engine provenance",),
        )

        result = evaluate_safe_decision(snapshot)

        self.assertIn("ENGINE_ALPHA", result.reason_codes)
        self.assertIn("engine provenance", result.reasons)

    @patch(
        "market_intelligence.decision.pipeline.evaluate_decision"
    )
    def test_m236_result_remains_immutable(
        self,
        mock_engine,
    ):
        snapshot = object.__new__(AnalysisSnapshot)
        mock_engine.return_value = make_result()

        result = evaluate_safe_decision(snapshot)

        with self.assertRaises(Exception):
            result.confidence = 1  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()

