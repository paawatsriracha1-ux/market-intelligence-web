from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from market_intelligence.decision.contract import DecisionAction


@dataclass(frozen=True)
class DecisionPolicyResult:
    """
    Immutable result emitted by the M2.3.3 Decision Policy.

    This layer maps an already eligibility-gated analysis result
    into a canonical DecisionAction. It does not execute trades.
    """

    action: DecisionAction
    confidence: int
    reason_codes: tuple[str, ...]
    reasons: tuple[str, ...]
    schema_version: str = "m2.3.3"

    def __post_init__(self) -> None:
        if not isinstance(self.action, DecisionAction):
            raise TypeError("action must be a DecisionAction")

        if isinstance(self.confidence, bool) or not isinstance(
            self.confidence, int
        ):
            raise TypeError("confidence must be an integer")

        if not 0 <= self.confidence <= 100:
            raise ValueError("confidence must be between 0 and 100")

        if not isinstance(self.reason_codes, tuple):
            raise TypeError("reason_codes must be tuple[str, ...]")

        if not isinstance(self.reasons, tuple):
            raise TypeError("reasons must be tuple[str, ...]")

    @property
    def actionable(self) -> bool:
        return self.action is DecisionAction.BUY

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["action"] = self.action.value
        payload["reason_codes"] = list(self.reason_codes)
        payload["reasons"] = list(self.reasons)
        return payload


def evaluate_decision_policy(
    *,
    eligible: bool,
    score: int,
    signal: str,
) -> DecisionPolicyResult:
    """
    Deterministic M2.3.3 action mapping.

    Eligibility is authoritative. An ineligible input always
    fails closed to NO_SIGNAL regardless of score or signal.
    """

    if not isinstance(eligible, bool):
        raise TypeError("eligible must be bool")

    if isinstance(score, bool) or not isinstance(score, int):
        raise TypeError("score must be an integer")

    if not 0 <= score <= 100:
        raise ValueError("score must be between 0 and 100")

    if not isinstance(signal, str):
        raise TypeError("signal must be a string")

    normalized_signal = signal.strip().upper()

    # Fail closed before considering any trading signal.
    if not eligible:
        return DecisionPolicyResult(
            action=DecisionAction.NO_SIGNAL,
            confidence=0,
            reason_codes=("INELIGIBLE",),
            reasons=("Decision eligibility gate did not pass.",),
        )

    if normalized_signal == "BUY / STRONG":
        return DecisionPolicyResult(
            action=DecisionAction.BUY,
            confidence=score,
            reason_codes=("STRONG_BUY",),
            reasons=("Eligible strong buy signal.",),
        )

    if normalized_signal == "WATCH":
        return DecisionPolicyResult(
            action=DecisionAction.WATCH,
            confidence=score,
            reason_codes=("WATCH_SETUP",),
            reasons=("Eligible setup requires confirmation.",),
        )

    if normalized_signal == "HOLD":
        return DecisionPolicyResult(
            action=DecisionAction.HOLD,
            confidence=score,
            reason_codes=("HOLD_SETUP",),
            reasons=("Eligible hold signal.",),
        )

    if normalized_signal == "AVOID / WEAK":
        return DecisionPolicyResult(
            action=DecisionAction.AVOID,
            confidence=score,
            reason_codes=("WEAK_SETUP",),
            reasons=("Eligible weak setup should be avoided.",),
        )

    # Unknown/unmapped signals must never become actionable.
    return DecisionPolicyResult(
        action=DecisionAction.NO_SIGNAL,
        confidence=0,
        reason_codes=("UNMAPPED_SIGNAL",),
        reasons=("Signal is not mapped by the M2.3.3 decision policy.",),
    )
