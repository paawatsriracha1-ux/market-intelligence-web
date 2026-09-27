"""
M2.14 persistence prerequisite contract.

Architecture established before this contract:

    analyze_symbol_v5()
        -> FinalDecisionBundle

    FinalDecisionBundle
        -> to_dict()
        -> from_dict()

    Storage.reconstruct_final_decision_bundle()
        -> FinalDecisionBundle.from_dict()

What is still missing is a Storage-owned persistence boundary
capable of accepting the producer bundle and later returning it
through the established reconstruction boundary.

This contract is intentionally RED until that prerequisite exists.
"""

import ast
from pathlib import Path


STORAGE_PATH = Path(
    "src/market_intelligence/storage.py"
)


def _storage_tree():
    source = STORAGE_PATH.read_text(
        encoding="utf-8"
    )

    return source, ast.parse(source)


def _storage_class(tree):
    for node in tree.body:
        if (
            isinstance(node, ast.ClassDef)
            and node.name == "Storage"
        ):
            return node

    raise AssertionError(
        "Storage class not found"
    )


def _method_names(storage_class):
    return {
        node.name
        for node in storage_class.body
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        )
    }


def _decision_persistence_tables(source):
    """
    Detect Storage-owned SQL persistence related to the
    final decision / bundle boundary.

    The contract deliberately does not prescribe the final
    table name.
    """

    lower = source.lower()

    statements = []

    for statement in lower.split(";"):
        if "create table" not in statement:
            continue

        if any(
            token in statement
            for token in (
                "decision",
                "bundle",
            )
        ):
            statements.append(statement)

    return statements


def _persistence_methods(storage_class):
    """
    Detect candidate Storage methods without freezing an exact
    production API name prematurely.
    """

    candidates = []

    for node in storage_class.body:

        if not isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        ):
            continue

        lower = node.name.lower()

        persistence_signal = any(
            token in lower
            for token in (
                "save",
                "store",
                "persist",
                "write",
            )
        )

        bundle_signal = any(
            token in lower
            for token in (
                "decision",
                "bundle",
            )
        )

        if persistence_signal and bundle_signal:
            candidates.append(node.name)

    return candidates


def _read_methods(storage_class):
    """
    Detect candidate persisted-bundle read boundaries.

    Reconstruction alone does not satisfy this contract because
    reconstruction currently accepts an already supplied mapping;
    it does not retrieve persisted state.
    """

    candidates = []

    for node in storage_class.body:

        if not isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        ):
            continue

        lower = node.name.lower()

        read_signal = any(
            token in lower
            for token in (
                "load",
                "get",
                "read",
                "fetch",
            )
        )

        bundle_signal = any(
            token in lower
            for token in (
                "decision",
                "bundle",
            )
        )

        if read_signal and bundle_signal:
            candidates.append(node.name)

    return candidates


def test_m214_storage_owns_final_bundle_persistence_prerequisite():
    """
    M2.14 prerequisite RED contract.

    Storage must own enough persistence infrastructure to:

      producer FinalDecisionBundle
            |
            v
      serialized persisted state
            |
            v
      Storage read boundary
            |
            v
      reconstruct_final_decision_bundle()
            |
            v
      FinalDecisionBundle.from_dict()

    This contract intentionally avoids prescribing exact production
    method or table names.
    """

    source, tree = _storage_tree()
    storage_class = _storage_class(tree)

    methods = _method_names(storage_class)

    assert (
        "reconstruct_final_decision_bundle"
        in methods
    ), (
        "M2.14 prerequisite violated: "
        "M2.13 reconstruction boundary is missing"
    )

    tables = _decision_persistence_tables(
        source
    )

    persistence_methods = _persistence_methods(
        storage_class
    )

    read_methods = _read_methods(
        storage_class
    )

    assert tables, (
        "M2.14 RED: Storage has no persisted "
        "final-decision/bundle relation"
    )

    assert persistence_methods, (
        "M2.14 RED: Storage has no final bundle "
        "persistence/write boundary"
    )

    assert read_methods, (
        "M2.14 RED: Storage has no persisted final "
        "bundle read boundary"
    )
