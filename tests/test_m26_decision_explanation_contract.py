"""M2.6 canonical decision explanation contract.

The Stock Analysis UI must explain the canonical Final Decision without
creating, upgrading, downgrading, or reinterpreting that decision.

Authority:

    Final action       -> final_bundle.decision.action
    Final confidence   -> final_bundle.decision.confidence
    Final eligibility  -> final_bundle.decision.eligible
    Final reasons      -> final_bundle.decision.reasons / reason_codes
    Actionable state   -> final_bundle.actionable

Technical plan/signal information may remain visible as supporting
analysis, but it must never become the authority for explaining the
Final Decision.
"""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
UI_ANALYSIS = ROOT / "ui" / "analysis.py"


class TestM26DecisionExplanationContract(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.source = UI_ANALYSIS.read_text(
            encoding="utf-8-sig"
        )

    def test_explanation_uses_canonical_final_decision(self):
        self.assertIn(
            "final_bundle.decision",
            self.source,
            "Decision explanation must consume "
            "FinalDecisionBundle.decision",
        )

    def test_explanation_exposes_reason_codes(self):
        self.assertIn(
            "final_decision.reason_codes",
            self.source,
            "Decision explanation must expose canonical reason codes",
        )

    def test_explanation_exposes_human_readable_reasons(self):
        self.assertIn(
            "final_decision.reasons",
            self.source,
            "Decision explanation must expose canonical reasons",
        )

    def test_explanation_uses_bundle_actionable_authority(self):
        self.assertIn(
            "final_bundle.actionable",
            self.source,
            "Actionable explanation must use FinalDecisionBundle",
        )

    def test_ui_has_decision_explanation_section(self):
        explanation_markers = (
            "Why this decision",
            "Decision Explanation",
            "Why this Final Decision",
        )

        self.assertTrue(
            any(
                marker in self.source
                for marker in explanation_markers
            ),
            "UI must provide an explicit Final Decision "
            "explanation section",
        )

    def test_raw_signal_not_used_as_decision_reason(self):
        forbidden_patterns = [
            '("Decision reason", plan.signal)',
            '("Final reason", plan.signal)',
            'st.write("Decision reason", plan.signal)',
            'st.write("Final reason", plan.signal)',
        ]

        violations = [
            pattern
            for pattern in forbidden_patterns
            if pattern in self.source
        ]

        self.assertEqual(
            violations,
            [],
            "Raw technical signal must not become a "
            f"Final Decision reason: {violations}",
        )


if __name__ == "__main__":
    unittest.main()
