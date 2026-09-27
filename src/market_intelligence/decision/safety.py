from __future__ import annotations

from dataclasses import replace

from .contract import DecisionAction, DecisionResult


SAFETY_SCHEMA_VERSION = "m2.3.5"

_BLOCKING_CODE = "SAFETY_BOUNDARY_BLOCKED"
_BLOCKING_REASON = "Decision was blocked by the M2.3.5 safety boundary."


def enforce_decision_safety(result: DecisionResult) -> DecisionResult:
    """
    M2.3.5 final fail-closed safety boundary.

    The safety boundary does not generate trading decisions.
    It validates an already-created DecisionResult and prevents
    an unsafe or inconsistent result from becoming actionable.
    """

    if not isinstance(result, DecisionResult):
        raise TypeError("result must be a DecisionResult")

    violations: list[str] = []

    # BUY is actionable only when eligibility is explicitly True.
    if result.action is DecisionAction.BUY and result.eligible is not True:
        violations.append("BUY_REQUIRES_ELIGIBLE")

    # BUY must carry positive confidence.
    if result.action is DecisionAction.BUY and result.confidence <= 0:
        violations.append("BUY_REQUIRES_POSITIVE_CONFIDENCE")

    # NO_SIGNAL must remain non-actionable and confidence-free.
    if result.action is DecisionAction.NO_SIGNAL and result.confidence != 0:
        violations.append("NO_SIGNAL_REQUIRES_ZERO_CONFIDENCE")

    # Any ineligible result must never become actionable.
    if result.eligible is not True and result.action is DecisionAction.BUY:
        if "BUY_REQUIRES_ELIGIBLE" not in violations:
            violations.append("BUY_REQUIRES_ELIGIBLE")

    if not violations:
        # DecisionResult is frozen; return the original immutable object.
        return result

    reason_codes = tuple(
        dict.fromkeys(
            result.reason_codes
            + (_BLOCKING_CODE,)
            + tuple(violations)
        )
    )

    reasons = result.reasons + (_BLOCKING_REASON,)

    # Fail closed.
    return replace(
        result,
        action=DecisionAction.NO_SIGNAL,
        confidence=0,
        eligible=False,
        reason_codes=reason_codes,
        reasons=reasons,
    )


def is_safe_actionable(result: DecisionResult) -> bool:
    """
    True only when the decision survives the safety boundary
    and is explicitly actionable.
    """
    safe = enforce_decision_safety(result)

    return (
        safe.eligible is True
        and safe.action is DecisionAction.BUY
        and safe.confidence > 0
    )
