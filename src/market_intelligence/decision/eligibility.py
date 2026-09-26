from __future__ import annotations

from dataclasses import dataclass

from ..analysis.snapshot import AnalysisSnapshot


@dataclass(frozen=True)
class EligibilityResult:
    eligible: bool
    reason_codes: tuple[str, ...]
    reasons: tuple[str, ...]
    schema_version: str = "m2.3.2"


def evaluate_decision_eligibility(
    snapshot: AnalysisSnapshot,
) -> EligibilityResult:
    """
    M2.3.2 fail-closed eligibility gate.

    Decision eligibility is derived only from the immutable
    AnalysisSnapshot produced by M2.2.

    Raw market data must not be inspected here.
    """
    if not isinstance(snapshot, AnalysisSnapshot):
        raise TypeError("snapshot must be an AnalysisSnapshot")

    quality = snapshot.market_data_quality

    if not isinstance(quality, dict):
        return EligibilityResult(
            eligible=False,
            reason_codes=("MARKET_DATA_QUALITY_MISSING",),
            reasons=("Market data quality metadata is missing or invalid.",),
        )

    reason_codes: list[str] = []
    reasons: list[str] = []

    # Fail closed: explicit True is required.
    if quality.get("valid") is not True:
        reason_codes.append("MARKET_DATA_INVALID")
        reasons.append("Market data did not pass validation.")

    if quality.get("signal_allowed") is not True:
        reason_codes.append("SIGNAL_NOT_ALLOWED")
        reasons.append("Market data quality does not allow signal generation.")

    reliability = quality.get("reliability")

    if reliability != "verified":
        reason_codes.append("MARKET_DATA_NOT_VERIFIED")
        reasons.append("Market data reliability is not verified.")

    if reason_codes:
        return EligibilityResult(
            eligible=False,
            reason_codes=tuple(reason_codes),
            reasons=tuple(reasons),
        )

    return EligibilityResult(
        eligible=True,
        reason_codes=("ELIGIBLE",),
        reasons=("Analysis snapshot passed the decision eligibility gate.",),
    )
