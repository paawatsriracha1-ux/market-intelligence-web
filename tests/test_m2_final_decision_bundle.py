import unittest
from unittest.mock import patch

from market_intelligence.analysis.snapshot import (
    AnalysisSnapshot,
    IndicatorSnapshot,
    LevelSnapshot,
)
from market_intelligence.decision.bundle import (
    FinalDecisionBundle,
    evaluate_final_decision,
    reconstruct_technical_guidance,
)
from market_intelligence.decision.contract import (
    DecisionAction,
    DecisionResult,
)
from market_intelligence.strategy.guidance import TechnicalGuidance


def make_guidance():
    return TechnicalGuidance(
        buy_trigger=100.0,
        buy_zone_low=95.0,
        buy_zone_high=99.0,
        sell_tp1=110.0,
        sell_tp2=120.0,
        stop_loss=90.0,
        support=94.0,
        resistance=110.0,
        confidence=80,
        regime="TREND",
        rationale=["M2.3.8 test"],
    )


def make_snapshot(guidance=None):
    if guidance is None:
        guidance = make_guidance().to_dict()

    return AnalysisSnapshot(
        symbol="TEST",
        market="US",
        timeframe="1D",
        timestamp="2026-01-01T00:00:00",
        price=100.0,
        score=80,
        trend="UP",
        signal="BUY",
        indicators=IndicatorSnapshot(
            ema20=98.0,
            ema50=95.0,
            ema200=90.0,
            rsi14=60.0,
            macd=1.0,
            macd_signal=0.5,
            atr14=2.0,
            volume_ratio=1.2,
        ),
        levels=LevelSnapshot(
            support=94.0,
            resistance=110.0,
        ),
        trade_plan={},
        guidance=guidance,
        market_data_quality={
            "valid": True,
            "signal_allowed": True,
        },
    )


def make_decision(
    action=DecisionAction.BUY,
    confidence=90,
    eligible=True,
):
    return DecisionResult(
        action=action,
        confidence=confidence,
        eligible=eligible,
        reason_codes=("M238_TEST",),
        reasons=("M2.3.8 test decision",),
    )


class M238FinalDecisionBundleTests(unittest.TestCase):

    def test_reconstructs_serialized_technical_guidance(self):
        original = make_guidance()

        reconstructed = reconstruct_technical_guidance(
            original.to_dict()
        )

        self.assertIsInstance(
            reconstructed,
            TechnicalGuidance,
        )

        self.assertEqual(
            reconstructed.to_dict(),
            original.to_dict(),
        )


    def test_reconstruction_rejects_unknown_fields(self):
        payload = make_guidance().to_dict()
        payload["unexpected_field"] = "unsafe"

        with self.assertRaises(ValueError):
            reconstruct_technical_guidance(payload)


    def test_reconstruction_rejects_missing_required_fields(self):
        payload = make_guidance().to_dict()
        del payload["buy_trigger"]

        with self.assertRaises(ValueError):
            reconstruct_technical_guidance(payload)


    def test_reconstruction_rejects_non_mapping(self):
        with self.assertRaises(TypeError):
            reconstruct_technical_guidance([])


    @patch(
        "market_intelligence.decision.bundle.evaluate_safe_decision"
    )
    def test_safe_buy_produces_actionable_final_bundle(
        self,
        mock_safe_decision,
    ):
        mock_safe_decision.return_value = make_decision()

        result = evaluate_final_decision(
            make_snapshot()
        )

        self.assertIsInstance(
            result,
            FinalDecisionBundle,
        )

        self.assertEqual(
            result.decision.action,
            DecisionAction.BUY,
        )

        self.assertTrue(result.actionable)
        self.assertEqual(
            result.action,
            DecisionAction.BUY,
        )

        self.assertEqual(
            result.guidance.buy_trigger,
            100.0,
        )

        self.assertEqual(
            result.guidance.sell_tp1,
            110.0,
        )

        self.assertEqual(
            result.guidance.stop_loss,
            90.0,
        )

        self.assertEqual(
            result.schema_version,
            "m2.3.8",
        )


    @patch(
        "market_intelligence.decision.bundle.evaluate_safe_decision"
    )
    def test_no_signal_never_exposes_levels(
        self,
        mock_safe_decision,
    ):
        mock_safe_decision.return_value = make_decision(
            action=DecisionAction.NO_SIGNAL,
            confidence=0,
            eligible=False,
        )

        result = evaluate_final_decision(
            make_snapshot()
        )

        self.assertFalse(result.actionable)

        self.assertEqual(
            result.action,
            DecisionAction.NO_SIGNAL,
        )

        self.assertIsNone(
            result.guidance.buy_trigger,
        )

        self.assertIsNone(
            result.guidance.sell_tp1,
        )

        self.assertIsNone(
            result.guidance.stop_loss,
        )


    @patch(
        "market_intelligence.decision.bundle.evaluate_safe_decision"
    )
    def test_malformed_snapshot_guidance_fails_closed(
        self,
        mock_safe_decision,
    ):
        mock_safe_decision.return_value = make_decision()

        snapshot = make_snapshot(
            guidance={
                "buy_trigger": 100.0,
            }
        )

        result = evaluate_final_decision(snapshot)

        self.assertEqual(
            result.decision.action,
            DecisionAction.BUY,
        )

        self.assertFalse(result.actionable)

        self.assertEqual(
            result.guidance.action,
            DecisionAction.NO_SIGNAL,
        )

        self.assertEqual(
            result.guidance.reason,
            "INVALID_SNAPSHOT_GUIDANCE",
        )

        self.assertIsNone(
            result.guidance.buy_trigger,
        )


    def test_wrong_snapshot_type_is_rejected(self):
        with self.assertRaises(TypeError):
            evaluate_final_decision({})


if __name__ == "__main__":
    unittest.main()
