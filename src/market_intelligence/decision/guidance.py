"""Safe actionable guidance boundary.

M2.3.7

This module controls whether technical trading guidance may become
actionable.  It does not generate prices, trading decisions, eligibility,
or safety decisions.

Only an eligible BUY decision that has already passed the M2.3.6 safe
decision pipeline may expose actionable BUY guidance.
"""

from __future__ import annotations

from dataclasses import dataclass

from market_intelligence.strategy.guidance import TechnicalGuidance

from .contract import DecisionAction, DecisionResult


_BLOCKED_REASON = "SAFE_DECISION_NOT_ACTIONABLE"


@dataclass(frozen=True)
class ActionableGuidance:
    """Final presentation-safe trading guidance."""

    actionable: bool
    action: DecisionAction

    buy_trigger: float | None = None
    buy_zone_low: float | None = None
    buy_zone_high: float | None = None

    sell_tp1: float | None = None
    sell_tp2: float | None = None
    stop_loss: float | None = None

    confidence: int = 0
    reason: str = _BLOCKED_REASON


def evaluate_actionable_guidance(
    decision: DecisionResult,
    guidance: TechnicalGuidance,
) -> ActionableGuidance:
    """Convert safe decision + technical guidance into presentation guidance.

    This function never creates or upgrades a trading decision.

    Actionable BUY guidance is exposed only when the supplied final
    DecisionResult is explicitly eligible and its action is BUY.
    All other decisions fail closed and do not expose executable levels.
    """

    if not isinstance(decision, DecisionResult):
        raise TypeError("decision must be a DecisionResult")

    if not isinstance(guidance, TechnicalGuidance):
        raise TypeError("guidance must be a TechnicalGuidance")

    if (
        decision.action is not DecisionAction.BUY
        or decision.eligible is not True
    ):
        return ActionableGuidance(
            actionable=False,
            action=decision.action,
            confidence=0,
            reason=_BLOCKED_REASON,
        )

    levels = (
        guidance.buy_trigger,
        guidance.buy_zone_low,
        guidance.buy_zone_high,
        guidance.sell_tp1,
        guidance.sell_tp2,
        guidance.stop_loss,
    )

    if not all(isinstance(value, (int, float)) for value in levels):
        return ActionableGuidance(
            actionable=False,
            action=DecisionAction.NO_SIGNAL,
            confidence=0,
            reason="INVALID_GUIDANCE_LEVELS",
        )

    if not (
        guidance.stop_loss
        < guidance.buy_zone_low
        <= guidance.buy_zone_high
        <= guidance.buy_trigger
        < guidance.sell_tp1
        < guidance.sell_tp2
    ):
        return ActionableGuidance(
            actionable=False,
            action=DecisionAction.NO_SIGNAL,
            confidence=0,
            reason="INVALID_GUIDANCE_STRUCTURE",
        )

    return ActionableGuidance(
        actionable=True,
        action=DecisionAction.BUY,
        buy_trigger=float(guidance.buy_trigger),
        buy_zone_low=float(guidance.buy_zone_low),
        buy_zone_high=float(guidance.buy_zone_high),
        sell_tp1=float(guidance.sell_tp1),
        sell_tp2=float(guidance.sell_tp2),
        stop_loss=float(guidance.stop_loss),
        confidence=decision.confidence,
        reason="SAFE_BUY_GUIDANCE",
    )
