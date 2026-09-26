from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class DecisionAction(str, Enum):
    """Canonical actions emitted by the M2 decision layer."""

    BUY = "BUY"
    WATCH = "WATCH"
    HOLD = "HOLD"
    AVOID = "AVOID"
    NO_SIGNAL = "NO_SIGNAL"


VALID_DECISION_ACTIONS = frozenset(
    action.value for action in DecisionAction
)


@dataclass(frozen=True)
class DecisionResult:
    """
    Immutable output contract for the M2 Decision Engine.

    M2.3.1 defines the contract only.
    Decision/scoring logic is introduced in later M2.3 stages.
    """

    action: DecisionAction
    confidence: int
    eligible: bool
    reason_codes: tuple[str, ...]
    reasons: tuple[str, ...]
    schema_version: str = "m2.3.1"

    def __post_init__(self) -> None:
        if not isinstance(self.action, DecisionAction):
            raise TypeError(
                "action must be a DecisionAction"
            )

        if isinstance(self.confidence, bool) or not isinstance(
            self.confidence, int
        ):
            raise TypeError(
                "confidence must be an integer"
            )

        if not 0 <= self.confidence <= 100:
            raise ValueError(
                "confidence must be between 0 and 100"
            )

        if not isinstance(self.eligible, bool):
            raise TypeError(
                "eligible must be bool"
            )

        if not isinstance(self.reason_codes, tuple):
            raise TypeError(
                "reason_codes must be tuple[str, ...]"
            )

        if not isinstance(self.reasons, tuple):
            raise TypeError(
                "reasons must be tuple[str, ...]"
            )

        if not all(
            isinstance(code, str) and code.strip()
            for code in self.reason_codes
        ):
            raise ValueError(
                "reason_codes must contain non-empty strings"
            )

        if not all(
            isinstance(reason, str) and reason.strip()
            for reason in self.reasons
        ):
            raise ValueError(
                "reasons must contain non-empty strings"
            )

        if len(set(self.reason_codes)) != len(self.reason_codes):
            raise ValueError(
                "reason_codes must not contain duplicates"
            )

        # Fail-closed invariant:
        # an ineligible analysis must never produce an actionable BUY.
        if not self.eligible and self.action is DecisionAction.BUY:
            raise ValueError(
                "ineligible decision cannot emit BUY"
            )

        if (
            self.action is DecisionAction.NO_SIGNAL
            and self.confidence != 0
        ):
            raise ValueError(
                "NO_SIGNAL must have confidence=0"
            )

        if not isinstance(self.schema_version, str) or not self.schema_version:
            raise ValueError(
                "schema_version must be a non-empty string"
            )

    @property
    def actionable(self) -> bool:
        """True only when the result is eligible and explicitly BUY."""

        return (
            self.eligible
            and self.action is DecisionAction.BUY
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-friendly payload."""

        payload = asdict(self)
        payload["action"] = self.action.value
        payload["reason_codes"] = list(self.reason_codes)
        payload["reasons"] = list(self.reasons)
        return payload
