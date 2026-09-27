"""M2.7 decision / trade authority consistency contract.

The Stock Analysis UI may expose technical analytics for research
context, but those values must remain subordinate to the canonical
FinalDecisionBundle.

M2.7 requirements:

1. Canonical decision authority is final_bundle.decision.
2. Canonical actionable authority is final_bundle.actionable.
3. Executable trade guidance is final_bundle.guidance.
4. Technical signal is explicitly presented as non-authoritative.
5. Technical confidence must not be presented as final confidence.
6. Technical score remains technical/research context only.
7. Trade-level presentation must be guarded by canonical actionable state.
8. UI must expose a clear authority boundary to the user.
"""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
UI_ANALYSIS = ROOT / "ui" / "analysis.py"


class TestM27AuthorityConsistencyContract(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.source = UI_ANALYSIS.read_text(
            encoding="utf-8-sig"
        )

    def test_canonical_decision_authority(self):
        self.assertIn(
            "final_decision = final_bundle.decision",
            self.source,
            "Final decision authority must come from "
            "FinalDecisionBundle.decision",
        )

    def test_canonical_actionable_authority(self):
        self.assertIn(
            "final_bundle.actionable",
            self.source,
            "Actionable authority must come from FinalDecisionBundle",
        )

    def test_canonical_trade_guidance_authority(self):
        self.assertIn(
            "actionable_guidance = final_bundle.guidance",
            self.source,
            "Executable trade guidance must come from "
            "FinalDecisionBundle.guidance",
        )

    def test_technical_signal_is_labeled_non_authoritative(self):
        self.assertIn(
            '("Technical Signal", plan.signal)',
            self.source,
            "Raw plan.signal may only be exposed as Technical Signal",
        )

    def test_final_confidence_comes_from_final_decision(self):
        self.assertIn(
            "final_decision.confidence",
            self.source,
            "Final confidence must come from canonical DecisionResult",
        )

    def test_technical_confidence_not_labeled_as_final_confidence(self):
        forbidden_patterns = [
            '("Confidence", f"{guide.confidence}/100")',
            'st.metric("Confidence", guide.confidence)',
            'st.metric("Final Confidence", guide.confidence)',
        ]

        violations = [
            pattern
            for pattern in forbidden_patterns
            if pattern in self.source
        ]

        self.assertEqual(
            violations,
            [],
            "Technical guidance confidence must not masquerade "
            f"as canonical final confidence: {violations}",
        )

    def test_technical_score_is_explicitly_technical(self):
        self.assertIn(
            '"Technical score"',
            self.source,
            "plan.score must remain labeled as Technical score",
        )

    def test_trade_levels_are_guarded_by_final_actionable(self):
        actionable_pos = self.source.find(
            "if final_bundle.actionable:"
        )
        trade_guidance_pos = self.source.find(
            "actionable_guidance.buy_trigger"
        )

        self.assertNotEqual(
            actionable_pos,
            -1,
            "Canonical actionable guard is required",
        )

        self.assertNotEqual(
            trade_guidance_pos,
            -1,
            "Trade-level presentation must exist",
        )

        self.assertLess(
            actionable_pos,
            trade_guidance_pos,
            "Canonical actionable guard must precede "
            "executable trade-level presentation",
        )

    def test_ui_exposes_authority_boundary(self):
        self.assertIn(
            "Decision Authority",
            self.source,
            "UI must explain the canonical decision authority boundary",
        )

    def test_no_plan_signal_as_final_decision(self):
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
            "Technical plan.signal must never replace "
            f"the final decision: {violations}",
        )


if __name__ == "__main__":
    unittest.main()