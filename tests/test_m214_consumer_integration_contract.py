from pathlib import Path
import ast
import tokenize


PRODUCTION_ROOTS = (
    Path("src/market_intelligence"),
    Path("ui"),
)

STORAGE_PATH = Path(
    "src/market_intelligence/storage.py"
)

TARGET_METHOD = "reconstruct_final_decision_bundle"


def _attribute_name(source, node):
    return (
        ast.get_source_segment(source, node)
        or getattr(node, "attr", "")
    )


def _production_callers():
    callers = []

    for root in PRODUCTION_ROOTS:
        if not root.exists():
            continue

        for path in root.rglob("*.py"):
            # The reconstruction boundary itself is the provider,
            # not its production consumer.
            if path == STORAGE_PATH:
                continue

            with tokenize.open(path) as handle:
                source = handle.read()

            tree = ast.parse(source)

            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue

                func = node.func

                if not isinstance(func, ast.Attribute):
                    continue

                if func.attr != TARGET_METHOD:
                    continue

                callers.append(
                    (
                        str(path),
                        node.lineno,
                        _attribute_name(source, func),
                    )
                )

    return callers


def test_m214_production_consumer_uses_storage_reconstruction_boundary():
    """
    M2.14 RED contract.

    A production consumer must cross the established Storage
    reconstruction boundary instead of reconstructing or
    re-evaluating FinalDecisionBundle independently.

    This test is intentionally RED until that production
    consumer integration exists.
    """

    callers = _production_callers()

    assert callers, (
        "M2.14 RED: no production consumer calls "
        "Storage.reconstruct_final_decision_bundle(); "
        "consumer integration boundary is not established"
    )
