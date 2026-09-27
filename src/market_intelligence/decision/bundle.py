"""Final decision consumer boundary.

M2.3.8

This module combines the canonical AnalysisSnapshot, the M2.3.6 safe
decision pipeline, and the M2.3.7 actionable-guidance gate into one
presentation-safe result.

It does not recalculate market analysis, technical levels, eligibility,
decision policy, or decision safety.
"""

from __future__ import annotations
import hashlib

from dataclasses import dataclass, fields
from typing import Any, Mapping

from market_intelligence.analysis.snapshot import AnalysisSnapshot
from market_intelligence.strategy.guidance import TechnicalGuidance

from .contract import DecisionAction, DecisionResult
from .guidance import ActionableGuidance, evaluate_actionable_guidance
from .pipeline import evaluate_safe_decision


@dataclass(frozen=True)
class DecisionTrace:
    """Non-authoritative metadata for decision traceability."""

    schema_version: str = "1.0"
    decision_id: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "schema_version": self.schema_version,
            "decision_id": self.decision_id,
        }


@dataclass(frozen=True)
class FinalDecisionBundle:
    """Final consumer-safe decision result."""

    decision: DecisionResult
    guidance: ActionableGuidance
    schema_version: str = "m2.3.8"
    trace: DecisionTrace = DecisionTrace()

    @property
    def actionable(self) -> bool:
        return self.guidance.actionable

    @property
    def action(self) -> DecisionAction:
        return self.decision.action


def reconstruct_technical_guidance(
    payload: Mapping[str, Any],
) -> TechnicalGuidance:
    """Reconstruct TechnicalGuidance from the canonical snapshot payload.

    AnalysisSnapshot intentionally stores guidance as plain serializable
    values. This function is the explicit typed bridge back into the
    TechnicalGuidance contract.

    Unknown fields are rejected and missing required fields are rejected
    by the TechnicalGuidance constructor.
    """

    if not isinstance(payload, Mapping):
        raise TypeError("guidance payload must be a mapping")

    allowed_fields = {
        field.name
        for field in fields(TechnicalGuidance)
    }

    unknown_fields = set(payload) - allowed_fields

    if unknown_fields:
        names = ", ".join(sorted(unknown_fields))
        raise ValueError(
            f"guidance payload contains unknown fields: {names}"
        )

    try:
        return TechnicalGuidance(**dict(payload))
    except TypeError as exc:
        raise ValueError(
            "guidance payload does not match TechnicalGuidance"
        ) from exc



def _decision_id_for_snapshot(snapshot: AnalysisSnapshot) -> str:
    identity = "|".join(
        (
            snapshot.schema_version,
            snapshot.market,
            snapshot.symbol,
            snapshot.timeframe,
            snapshot.timestamp,
        )
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def evaluate_final_decision(
    snapshot: AnalysisSnapshot,
) -> FinalDecisionBundle:
    """Evaluate the final safe consumer-facing decision bundle."""

    if not isinstance(snapshot, AnalysisSnapshot):
        raise TypeError("snapshot must be an AnalysisSnapshot")

    decision_trace = DecisionTrace(
        decision_id=_decision_id_for_snapshot(snapshot),
    )

    decision = evaluate_safe_decision(snapshot)

    if not isinstance(decision, DecisionResult):
        raise TypeError(
            "safe decision pipeline must return DecisionResult"
        )

    try:
        technical_guidance = reconstruct_technical_guidance(
            snapshot.guidance
        )
    except (TypeError, ValueError):
        # Fail closed: malformed serialized guidance must never expose
        # executable trading levels.
        blocked_guidance = ActionableGuidance(
            actionable=False,
            action=DecisionAction.NO_SIGNAL,
            confidence=0,
            reason="INVALID_SNAPSHOT_GUIDANCE",
        )

        return FinalDecisionBundle(
            decision=decision,
            guidance=blocked_guidance,
            trace=decision_trace,
        )

    actionable_guidance = evaluate_actionable_guidance(
        decision,
        technical_guidance,
    )

    return FinalDecisionBundle(
        decision=decision,
        guidance=actionable_guidance,
        trace=decision_trace,
    )
