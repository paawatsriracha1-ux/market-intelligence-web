import ast
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]

BUNDLE_PATH = (
    ROOT
    / "src"
    / "market_intelligence"
    / "decision"
    / "bundle.py"
)


def load_bundle():
    source = BUNDLE_PATH.read_text(encoding="utf-8")
    return source, ast.parse(source)


def find_class(tree, name):
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node

    return None


def find_methods(class_node, names):
    if class_node is None:
        return []

    return [
        node
        for node in class_node.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in names
    ]


def referenced_attributes(node):
    attrs = set()

    for child in ast.walk(node):
        if isinstance(child, ast.Attribute):
            attrs.add(child.attr)

    return attrs


def referenced_string_constants(node):
    values = set()

    for child in ast.walk(node):
        if (
            isinstance(child, ast.Constant)
            and isinstance(child.value, str)
        ):
            values.add(child.value)

    return values


class M210TracePropagationContract(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.source, cls.tree = load_bundle()

        cls.trace_class = find_class(
            cls.tree,
            "DecisionTrace",
        )

        cls.bundle_class = find_class(
            cls.tree,
            "FinalDecisionBundle",
        )

    def test_decision_trace_contract_exists(self):
        self.assertIsNotNone(
            self.trace_class,
            "DecisionTrace must remain defined.",
        )

    def test_final_bundle_contract_exists(self):
        self.assertIsNotNone(
            self.bundle_class,
            "FinalDecisionBundle must remain defined.",
        )

    def test_trace_fields_preserved(self):
        fields = set()

        for node in self.trace_class.body:
            if (
                isinstance(node, ast.AnnAssign)
                and isinstance(node.target, ast.Name)
            ):
                fields.add(node.target.id)

        self.assertIn("schema_version", fields)
        self.assertIn("decision_id", fields)

    def test_final_bundle_still_carries_trace(self):
        fields = set()

        for node in self.bundle_class.body:
            if (
                isinstance(node, ast.AnnAssign)
                and isinstance(node.target, ast.Name)
            ):
                fields.add(node.target.id)

        self.assertIn(
            "trace",
            fields,
            "FinalDecisionBundle must retain trace.",
        )

    def test_trace_has_explicit_serialization_boundary(self):
        methods = find_methods(
            self.trace_class,
            {
                "to_dict",
                "to_json",
                "serialize",
            },
        )

        self.assertTrue(
            methods,
            "DecisionTrace requires an explicit "
            "serialization boundary.",
        )

    def test_trace_serialization_propagates_schema_version(self):
        methods = find_methods(
            self.trace_class,
            {
                "to_dict",
                "to_json",
                "serialize",
            },
        )

        propagated = False

        for method in methods:
            attrs = referenced_attributes(method)
            strings = referenced_string_constants(method)

            if (
                "schema_version" in attrs
                and "schema_version" in strings
            ):
                propagated = True

        self.assertTrue(
            propagated,
            "DecisionTrace serialization must explicitly "
            "propagate schema_version.",
        )

    def test_trace_serialization_propagates_decision_id(self):
        methods = find_methods(
            self.trace_class,
            {
                "to_dict",
                "to_json",
                "serialize",
            },
        )

        propagated = False

        for method in methods:
            attrs = referenced_attributes(method)
            strings = referenced_string_constants(method)

            if (
                "decision_id" in attrs
                and "decision_id" in strings
            ):
                propagated = True

        self.assertTrue(
            propagated,
            "DecisionTrace serialization must explicitly "
            "propagate decision_id.",
        )

    def test_trace_remains_non_authoritative(self):
        forbidden = {
            "action",
            "actionable",
            "guidance",
        }

        violations = []

        if self.trace_class is not None:
            for node in ast.walk(self.trace_class):
                if (
                    isinstance(node, ast.Attribute)
                    and node.attr in forbidden
                ):
                    violations.append(node.attr)

        self.assertFalse(
            violations,
            "DecisionTrace must remain non-authoritative: "
            + ", ".join(sorted(set(violations))),
        )


if __name__ == "__main__":
    unittest.main()
