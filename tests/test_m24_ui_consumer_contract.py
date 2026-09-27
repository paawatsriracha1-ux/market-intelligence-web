"""M2.4 UI consumer boundary specification.

The Stock Analysis UI must consume the canonical V5 orchestration
boundary rather than the legacy V4 analysis service.

Executable trade levels must come from FinalDecisionBundle.guidance,
which has already passed the final decision and actionable-guidance
safety boundaries.
"""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
UI_ANALYSIS = ROOT / "ui" / "analysis.py"


class TestM24UIConsumerContract(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.source = UI_ANALYSIS.read_text(encoding="utf-8-sig")

    def test_ui_uses_v5_public_service(self):
        self.assertIn(
            "analyze_symbol_v5",
            self.source,
            "M2.4 requires UI analysis to consume analyze_symbol_v5",
        )

        self.assertNotIn(
            "analyze_symbol_v4",
            self.source,
            "Legacy analyze_symbol_v4 must not remain in UI analysis",
        )

    def test_ui_receives_canonical_v5_objects(self):
        self.assertIn(
            "snapshot",
            self.source,
            "UI must receive the canonical AnalysisSnapshot",
        )

        self.assertIn(
            "final_bundle",
            self.source,
            "UI must receive the canonical FinalDecisionBundle",
        )

    def test_trade_map_uses_final_actionable_guidance(self):
        self.assertIn(
            "final_bundle.guidance",
            self.source,
            "Trade Map must consume final actionable guidance",
        )

    def test_ui_checks_actionable_boundary(self):
        self.assertIn(
            ".actionable",
            self.source,
            "UI must check actionable state before exposing trade levels",
        )

    def test_raw_guidance_not_used_for_executable_trade_levels(self):
        forbidden = [
            'f"{guide.buy_trigger:',
            'f"{guide.buy_zone_low:',
            'f"{guide.sell_tp1:',
            'f"{guide.sell_tp2:',
            'f"{guide.stop_loss:',
        ]

        violations = [
            pattern
            for pattern in forbidden
            if pattern in self.source
        ]

        self.assertEqual(
            violations,
            [],
            "Executable trade levels must not be rendered directly "
            f"from raw TechnicalGuidance: {violations}",
        )


if __name__ == "__main__":
    unittest.main()