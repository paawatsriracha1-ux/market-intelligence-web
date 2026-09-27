"""M2.3.6 safe decision pipeline.

Provides the canonical public entry point for producing a final
DecisionResult from an AnalysisSnapshot.

Pipeline:
    AnalysisSnapshot
        -> decision engine
        -> safety boundary
        -> final DecisionResult

Consumers should prefer this boundary instead of calling the decision
engine directly when an actionable result may leave the decision layer.
"""

from __future__ import annotations

from ..analysis.snapshot import AnalysisSnapshot
from .contract import DecisionResult
from .engine import evaluate_decision
from .safety import enforce_decision_safety


def evaluate_safe_decision(
    snapshot: AnalysisSnapshot,
) -> DecisionResult:
    """Evaluate a snapshot and enforce the final safety boundary."""

    if not isinstance(snapshot, AnalysisSnapshot):
        raise TypeError("snapshot must be an AnalysisSnapshot")

    decision = evaluate_decision(snapshot)

    if not isinstance(decision, DecisionResult):
        raise TypeError("decision engine must return a DecisionResult")

    safe_decision = enforce_decision_safety(decision)

    if not isinstance(safe_decision, DecisionResult):
        raise TypeError("decision safety must return a DecisionResult")

    return safe_decision
