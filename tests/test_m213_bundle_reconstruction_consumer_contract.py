"""
M2.13 contract: FinalDecisionBundle reconstruction must have
an explicit production consumer boundary.

This contract intentionally starts RED.

M2.12 established:
    FinalDecisionBundle.to_dict()
    FinalDecisionBundle.from_dict()
    DecisionTrace.from_dict()

M2.13 requires a production consumer outside decision/bundle.py
to cross the reconstruction boundary through
FinalDecisionBundle.from_dict().

The contract is structural by design.  It does not prescribe the
final persistence implementation and does not permit decision or
guidance re-evaluation.
"""

from __future__ import annotations

import ast
import tokenize
from pathlib import Path


SOURCE_ROOTS = (
    Path("src/market_intelligence"),
    Path("ui"),
)

BUNDLE_MODULE = Path(
    "src/market_intelligence/decision/bundle.py"
)


def _production_python_files():
    for root in SOURCE_ROOTS:
        if not root.exists():
            continue

        yield from root.rglob("*.py")


def _final_decision_bundle_from_dict_calls():
    calls = []

    for path in _production_python_files():

        # The definition itself is not a consumer.
        if path == BUNDLE_MODULE:
            continue

        with tokenize.open(path) as stream:
            source = stream.read()

        tree = ast.parse(source)

        aliases = set()
        module_aliases = set()

        for node in ast.walk(tree):

            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name == "FinalDecisionBundle":
                        aliases.add(
                            alias.asname or alias.name
                        )

            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if (
                        alias.name
                        == "market_intelligence.decision.bundle"
                    ):
                        module_aliases.add(
                            alias.asname or alias.name
                        )

        for node in ast.walk(tree):

            if not isinstance(node, ast.Call):
                continue

            func = node.func

            if not (
                isinstance(func, ast.Attribute)
                and func.attr == "from_dict"
            ):
                continue

            owner = func.value

            direct_call = (
                isinstance(owner, ast.Name)
                and owner.id in aliases
            )

            module_call = False

            if isinstance(owner, ast.Attribute):
                if (
                    owner.attr == "FinalDecisionBundle"
                    and isinstance(owner.value, ast.Name)
                    and owner.value.id in module_aliases
                ):
                    module_call = True

            if direct_call or module_call:
                calls.append(
                    (
                        str(path),
                        node.lineno,
                        ast.get_source_segment(
                            source,
                            node,
                        ),
                    )
                )

    return calls


def test_final_decision_bundle_has_production_reconstruction_consumer():
    calls = _final_decision_bundle_from_dict_calls()

    assert calls, (
        "M2.13 reconstruction consumer gap: "
        "FinalDecisionBundle.from_dict() has no production "
        "consumer outside decision/bundle.py"
    )
