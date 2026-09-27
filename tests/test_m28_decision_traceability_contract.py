import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]

SOURCE_ROOT = ROOT / "src" / "market_intelligence"
UI_PATH = ROOT / "ui" / "analysis.py"


def read(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def all_source_text() -> str:
    parts = []

    for path in SOURCE_ROOT.rglob("*.py"):
        parts.append(read(path))

    return "\n".join(parts)


class M28DecisionTraceabilityContract(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.source = all_source_text()
        cls.ui = read(UI_PATH)

    def test_final_decision_bundle_still_exists(self):
        self.assertIn(
            "FinalDecisionBundle",
            self.source,
            "FinalDecisionBundle must remain the canonical "
            "decision consumer boundary.",
        )

    def test_traceability_contract_exists(self):
        candidates = (
            "DecisionTrace",
            "DecisionTraceability",
            "DecisionProvenance",
        )

        self.assertTrue(
            any(name in self.source for name in candidates),
            "M2.8 requires an explicit decision traceability "
            "metadata contract.",
        )

    def test_traceability_has_schema_version(self):
        self.assertRegex(
            self.source,
            r"\bschema_version\b",
            "Decision traceability must expose schema_version.",
        )

    def test_traceability_has_decision_identifier(self):
        identifier_patterns = (
            r"\bdecision_id\b",
            r"\btrace_id\b",
            r"\banalysis_id\b",
        )

        self.assertTrue(
            any(
                re.search(pattern, self.source)
                for pattern in identifier_patterns
            ),
            "Decision traceability must expose a stable identifier.",
        )

    def test_final_bundle_carries_traceability(self):
        bundle_pattern = re.compile(
            r"class\s+FinalDecisionBundle\b.*?"
            r"(trace|traceability|provenance)",
            re.DOTALL,
        )

        self.assertRegex(
            self.source,
            bundle_pattern,
            "FinalDecisionBundle must carry traceability metadata.",
        )

    def test_existing_authority_fields_remain_present(self):
        required = (
            "decision",
            "actionable",
            "guidance",
        )

        for field in required:
            self.assertIn(
                field,
                self.source,
                f"Existing authority field '{field}' must remain.",
            )

    def test_traceability_does_not_become_decision_authority(self):
        forbidden_patterns = (
            r"trace(?:ability)?\s*\.\s*action",
            r"trace(?:ability)?\s*\.\s*actionable",
            r"trace(?:ability)?\s*\.\s*guidance",
            r"provenance\s*\.\s*action",
            r"provenance\s*\.\s*actionable",
            r"provenance\s*\.\s*guidance",
        )

        violations = [
            pattern
            for pattern in forbidden_patterns
            if re.search(pattern, self.ui, re.IGNORECASE)
        ]

        self.assertFalse(
            violations,
            "UI must never use trace metadata as decision authority: "
            + ", ".join(violations),
        )

    def test_ui_keeps_canonical_decision_authority(self):
        self.assertIn(
            "final_bundle.decision",
            self.ui,
            "UI final decision authority must remain "
            "final_bundle.decision.",
        )

    def test_ui_keeps_canonical_actionable_authority(self):
        self.assertIn(
            "final_bundle.actionable",
            self.ui,
            "UI actionable authority must remain "
            "final_bundle.actionable.",
        )

    def test_ui_keeps_canonical_guidance_authority(self):
        self.assertIn(
            "final_bundle.guidance",
            self.ui,
            "UI trade guidance authority must remain "
            "final_bundle.guidance.",
        )


if __name__ == "__main__":
    unittest.main()