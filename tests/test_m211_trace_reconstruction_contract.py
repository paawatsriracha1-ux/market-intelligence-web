from __future__ import annotations

import inspect

import pytest

from market_intelligence.decision.bundle import DecisionTrace


# ============================================================
# M2.11 TRACE RECONSTRUCTION CONTRACT
#
# M2.10 established the outbound serialization boundary:
#
#     DecisionTrace.to_dict()
#
# M2.11 establishes the inverse reconstruction boundary.
#
# Contract:
#
#   serialized trace
#       ↓
#   DecisionTrace.from_dict(...)
#       ↓
#   reconstructed DecisionTrace
#
# Identity fields must survive:
#
#   schema_version
#   decision_id
#
# Trace remains metadata only and must not become
# authoritative decision input.
# ============================================================


def test_decision_trace_exposes_from_dict_boundary():
    """
    M2.11 requires an explicit reconstruction boundary.

    This test MUST remain red until production source
    implements DecisionTrace.from_dict().
    """

    assert hasattr(
        DecisionTrace,
        "from_dict",
    ), (
        "M2.11 requires DecisionTrace.from_dict() "
        "to reconstruct serialized trace metadata"
    )

    assert callable(
        getattr(
            DecisionTrace,
            "from_dict",
            None,
        )
    )


def test_decision_trace_from_dict_accepts_payload():
    """
    Reconstruction must consume the serialized payload
    as a single mapping boundary.
    """

    method = getattr(
        DecisionTrace,
        "from_dict",
        None,
    )

    assert method is not None

    signature = inspect.signature(method)

    parameters = list(signature.parameters.values())

    assert len(parameters) == 1, (
        "DecisionTrace.from_dict() must expose one "
        "payload argument at the public boundary"
    )


def test_decision_trace_round_trip_preserves_identity():
    """
    Serialization followed by reconstruction must preserve
    both trace identity fields exactly.
    """

    original = DecisionTrace(
        schema_version="1.0",
        decision_id="m211-contract-id",
    )

    payload = original.to_dict()

    reconstructed = DecisionTrace.from_dict(payload)

    assert isinstance(
        reconstructed,
        DecisionTrace,
    )

    assert (
        reconstructed.schema_version
        == original.schema_version
    )

    assert (
        reconstructed.decision_id
        == original.decision_id
    )

    assert reconstructed == original


def test_decision_trace_reconstruction_is_deterministic():
    """
    The same serialized payload must reconstruct the same
    immutable trace value every time.
    """

    payload = {
        "schema_version": "1.0",
        "decision_id": "deterministic-trace-id",
    }

    first = DecisionTrace.from_dict(payload)
    second = DecisionTrace.from_dict(payload)

    assert first == second

    assert first.schema_version == "1.0"
    assert first.decision_id == "deterministic-trace-id"


def test_decision_trace_round_trip_payload_is_stable():
    """
    A round trip must not mutate or expand the serialized
    trace schema.
    """

    payload = {
        "schema_version": "1.0",
        "decision_id": "stable-payload-id",
    }

    reconstructed = DecisionTrace.from_dict(payload)

    assert reconstructed.to_dict() == payload


def test_decision_trace_reconstruction_does_not_mutate_payload():
    """
    Reconstruction must treat the caller payload as input,
    not as mutable internal state.
    """

    payload = {
        "schema_version": "1.0",
        "decision_id": "isolated-payload-id",
    }

    before = dict(payload)

    reconstructed = DecisionTrace.from_dict(payload)

    assert payload == before

    assert reconstructed.schema_version == "1.0"
    assert reconstructed.decision_id == "isolated-payload-id"


def test_decision_trace_remains_frozen_value_object():
    """
    M2.11 must not weaken the existing frozen trace model.
    """

    trace = DecisionTrace(
        schema_version="1.0",
        decision_id="immutable-id",
    )

    with pytest.raises(Exception):
        trace.decision_id = "changed"
