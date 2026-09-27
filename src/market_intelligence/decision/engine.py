"""M2.3.4 deterministic Decision Engine orchestration.

This module composes the existing M2 decision stages:

    AnalysisSnapshot
        -> M2.3.2 eligibility gate
        -> M2.3.3 decision policy
        -> DecisionResult

The engine does not recompute indicators, scores, signals, or market-data
quality.  It consumes the immutable AnalysisSnapshot produced by M2.2.

Fail-closed behavior remains authoritative.
"""

from __future__ import annotations

from ..analysis.snapshot import AnalysisSnapshot
from .contract import DecisionResult
from .eligibility import evaluate_decision_eligibility
from .policy import evaluate_decision_policy


def evaluate_decision(
    snapshot: AnalysisSnapshot,
) -> DecisionResult:
    """Evaluate an AnalysisSnapshot through the complete M2.3 pipeline."""

    if not isinstance(snapshot, AnalysisSnapshot):
        raise TypeError("snapshot must be an AnalysisSnapshot")

    eligibility = evaluate_decision_eligibility(snapshot)

    policy = evaluate_decision_policy(
        eligible=eligibility.eligible,
        score=snapshot.score,
        signal=snapshot.signal,
    )

    # Preserve provenance from both stages while preventing duplicate codes.
    reason_codes = tuple(
        dict.fromkeys(
            eligibility.reason_codes + policy.reason_codes
        )
    )

    reasons = eligibility.reasons + policy.reasons

    return DecisionResult(
        action=policy.action,
        confidence=policy.confidence,
        eligible=eligibility.eligible,
        reason_codes=reason_codes,
        reasons=reasons,
    )
