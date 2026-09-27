from __future__ import annotations

import pytest

from market_intelligence.decision.bundle import (
    DecisionTrace,
    FinalDecisionBundle,
)


# ============================================================
# M2.12 TRACE PERSISTENCE BOUNDARY CONTRACT
#
# M2.10 established DecisionTrace serialization.
# M2.11 established DecisionTrace reconstruction.
#
# M2.12 requires those boundaries to be integrated into the
# consumer-safe FinalDecisionBundle persistence boundary.
#
# Contract:
#
#   FinalDecisionBundle
#           ↓
#       to_dict()
#           ↓
#   plain serialized trace payload
#           ↓
#       from_dict(...)
#           ↓
#   reconstructed FinalDecisionBundle
#
# Trace remains metadata only.
# Reconstructed trace MUST NOT become authoritative decision
# input or cause decision/guidance re-evaluation.
# ============================================================


def test_final_decision_bundle_exposes_serialization_boundary():
    assert hasattr(
        FinalDecisionBundle,
        "to_dict",
    ), (
        "M2.12 requires FinalDecisionBundle.to_dict() "
        "as the persistence serialization boundary"
    )

    assert callable(
        getattr(
            FinalDecisionBundle,
            "to_dict",
            None,
        )
    )


def test_final_decision_bundle_exposes_reconstruction_boundary():
    assert hasattr(
        FinalDecisionBundle,
        "from_dict",
    ), (
        "M2.12 requires FinalDecisionBundle.from_dict() "
        "as the persistence reconstruction boundary"
    )

    assert callable(
        getattr(
            FinalDecisionBundle,
            "from_dict",
            None,
        )
    )


def test_bundle_serialization_contains_plain_trace_payload():
    """
    The persisted bundle must serialize trace metadata
    through the established DecisionTrace boundary.
    """

    assert hasattr(FinalDecisionBundle, "to_dict")

    trace = DecisionTrace(
        schema_version="1.0",
        decision_id="m212-trace-id",
    )

    # Construction details for decision/guidance are intentionally
    # not guessed here. The production implementation must expose
    # a consumer-safe bundle persistence boundary whose trace value
    # is a plain mapping.
    #
    # This assertion intentionally remains RED until that boundary
    # exists.
    assert "trace" in {
        field
        for field in (
            getattr(
                FinalDecisionBundle,
                "__dataclass_fields__",
                {},
            )
        )
    }

    assert trace.to_dict() == {
        "schema_version": "1.0",
        "decision_id": "m212-trace-id",
    }


def test_trace_reconstruction_boundary_remains_explicit():
    payload = {
        "schema_version": "1.0",
        "decision_id": "m212-reconstructed-id",
    }

    reconstructed = DecisionTrace.from_dict(payload)

    assert reconstructed == DecisionTrace(
        schema_version="1.0",
        decision_id="m212-reconstructed-id",
    )


def test_trace_remains_frozen_non_authoritative_metadata():
    trace = DecisionTrace(
        schema_version="1.0",
        decision_id="metadata-only-id",
    )

    with pytest.raises(Exception):
        trace.decision_id = "changed"
