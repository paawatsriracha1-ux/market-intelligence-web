import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]

SNAPSHOT_PATH = (
    ROOT
    / "src"
    / "market_intelligence"
    / "analysis"
    / "snapshot.py"
)

BUNDLE_PATH = (
    ROOT
    / "src"
    / "market_intelligence"
    / "decision"
    / "bundle.py"
)

UI_PATH = ROOT / "ui" / "analysis.py"


def read(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


class M29DecisionIdentityContract(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.snapshot = read(SNAPSHOT_PATH)
        cls.bundle = read(BUNDLE_PATH)
        cls.ui = read(UI_PATH)

    def test_analysis_snapshot_exposes_identity_inputs(self):
        required = (
            "symbol",
            "market",
            "timeframe",
            "timestamp",
            "schema_version",
        )

        for field in required:
            self.assertRegex(
                self.snapshot,
                rf"\b{field}\s*:",
                f"AnalysisSnapshot must retain identity input "
                f"'{field}'.",
            )

    def test_decision_trace_retains_decision_id(self):
        self.assertRegex(
            self.bundle,
            r"class\s+DecisionTrace\b[\s\S]*?\bdecision_id\s*:",
            "DecisionTrace must retain decision_id.",
        )

    def test_final_bundle_retains_trace(self):
        self.assertRegex(
            self.bundle,
            r"class\s+FinalDecisionBundle\b[\s\S]*?\btrace\s*:",
            "FinalDecisionBundle must retain trace metadata.",
        )

    def test_decision_id_is_derived_from_snapshot_identity(self):
        identity_fields = (
            "symbol",
            "market",
            "timeframe",
            "timestamp",
        )

        has_builder = re.search(
            r"(decision_id|trace_id).*?"
            r"(snapshot|symbol|market|timeframe|timestamp)",
            self.bundle,
            re.DOTALL | re.IGNORECASE,
        )

        field_hits = sum(
            1
            for field in identity_fields
            if re.search(
                rf"snapshot\.{field}\b",
                self.bundle,
            )
        )

        self.assertTrue(
            has_builder and field_hits >= 4,
            "decision_id must be derived from the canonical "
            "AnalysisSnapshot identity fields.",
        )

    def test_decision_id_generation_is_deterministic(self):
        deterministic_markers = (
            "sha256",
            "hashlib",
            "uuid5",
            "NAMESPACE_",
        )

        self.assertTrue(
            any(
                marker in self.bundle
                for marker in deterministic_markers
            ),
            "decision_id generation must use a deterministic "
            "identity mechanism.",
        )

    def test_decision_id_does_not_use_random_uuid4(self):
        forbidden = (
            r"\buuid4\s*\(",
            r"\brandom\.",
            r"\bsecrets\.",
        )

        violations = [
            pattern
            for pattern in forbidden
            if re.search(
                pattern,
                self.bundle,
                re.IGNORECASE,
            )
        ]

        self.assertFalse(
            violations,
            "decision_id must not depend on random identity: "
            + ", ".join(violations),
        )

    def test_both_final_bundle_paths_carry_trace(self):
        constructors = re.findall(
            r"FinalDecisionBundle\s*\((.*?)\)",
            self.bundle,
            re.DOTALL,
        )

        self.assertGreaterEqual(
            len(constructors),
            2,
            "Expected both FinalDecisionBundle construction paths.",
        )

        missing = [
            index
            for index, body in enumerate(constructors, 1)
            if not re.search(r"\btrace\s*=", body)
        ]

        self.assertFalse(
            missing,
            "Every FinalDecisionBundle path must carry trace. "
            f"Missing paths: {missing}",
        )

    def test_trace_remains_non_authoritative_in_ui(self):
        forbidden = (
            r"final_bundle\.trace\.action\b",
            r"final_bundle\.trace\.actionable\b",
            r"final_bundle\.trace\.guidance\b",
            r"final_bundle\.trace\.signal\b",
        )

        violations = [
            pattern
            for pattern in forbidden
            if re.search(
                pattern,
                self.ui,
                re.IGNORECASE,
            )
        ]

        self.assertFalse(
            violations,
            "Trace metadata must remain non-authoritative: "
            + ", ".join(violations),
        )

    def test_canonical_authorities_remain_unchanged(self):
        required = (
            "final_bundle.decision",
            "final_bundle.actionable",
            "final_bundle.guidance",
        )

        for authority in required:
            self.assertIn(
                authority,
                self.ui,
                f"Canonical authority must remain {authority}.",
            )


if __name__ == "__main__":
    unittest.main()
