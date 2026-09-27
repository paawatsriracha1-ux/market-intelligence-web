"""M2.5 final decision presentation contract.

The Stock Analysis UI must present the canonical final decision produced
by FinalDecisionBundle.

The UI is a consumer only. It must not create, upgrade, reinterpret, or
replace the final decision using legacy/raw analysis signals.

M2.5 requirements:

1. Final decision presentation consumes final_bundle.decision.
2. Action is displayed from the canonical DecisionResult.
3. Confidence is displayed from the canonical DecisionResult.
4. Eligibility is displayed from the canonical DecisionResult.
5. Actionable state comes from FinalDecisionBundle.
6. Decision reasons are exposed to the user.
7. Raw plan.signal must not be presented as the Final Decision.
"""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
UI_ANALYSIS = ROOT / "ui" / "analysis.py"


class TestM25DecisionPresentationContract(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.source = UI_ANALYSIS.read_text(
            encoding="utf-8-sig"
        )

    def test_ui_consumes_final_decision(self):
        self.assertIn(
            "final_bundle.decision",
            self.source,
            "M2.5 requires UI to consume "
            "FinalDecisionBundle.decision",
        )

    def test_ui_exposes_final_action(self):
        self.assertIn(
            ".action",
            self.source,
            "Final decision action must be presented",
        )

    def test_ui_exposes_final_confidence(self):
        self.assertIn(
            "final_decision.confidence",
            self.source,
            "Confidence must come from the final DecisionResult",
        )

    def test_ui_exposes_final_eligibility(self):
        self.assertIn(
            "final_decision.eligible",
            self.source,
            "Eligibility must come from the final DecisionResult",
        )

    def test_ui_exposes_final_actionable_state(self):
        self.assertIn(
            "final_bundle.actionable",
            self.source,
            "Actionable state must come from FinalDecisionBundle",
        )

    def test_ui_exposes_decision_reasons(self):
        self.assertTrue(
            (
                "final_decision.reasons" in self.source
                or
                "final_decision.reason_codes" in self.source
            ),
            "UI must expose canonical final decision reasons",
        )

    def test_ui_has_final_decision_section(self):
        self.assertIn(
            "Final Decision",
            self.source,
            "UI must contain a Final Decision presentation section",
        )

    def test_plan_signal_not_used_as_final_decision(self):
        forbidden_patterns = [
            '("Final Decision", plan.signal)',
            'st.write(plan.signal)',
            'st.metric("Final Decision", plan.signal)',
        ]

        violations = [
            pattern
            for pattern in forbidden_patterns
            if pattern in self.source
        ]

        self.assertEqual(
            violations,
            [],
            "Raw plan.signal must not be presented "
            f"as Final Decision: {violations}",
        )


if __name__ == "__main__":
    unittest.main()
