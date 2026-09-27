from __future__ import annotations

import unittest

from market_intelligence.analysis.snapshot import (
    AnalysisSnapshot,
    IndicatorSnapshot,
    LevelSnapshot,
)
from market_intelligence.decision.contract import DecisionAction
from market_intelligence.decision.eligibility import (
    evaluate_decision_eligibility,
)
from market_intelligence.decision.policy import (
    evaluate_decision_policy,
)


class M233DecisionPolicyIntegrationTests(unittest.TestCase):

    def _snapshot(
        self,
        *,
        score: int = 85,
        signal: str = "BUY / STRONG",
        quality: dict | None = None,
    ) -> AnalysisSnapshot:
        return AnalysisSnapshot(
            symbol="AAPL",
            market="US",
            timeframe="1D",
            timestamp="2026-09-25T03:05:00",
            price=200.0,
            score=score,
            trend="BULLISH",
            signal=signal,
            indicators=IndicatorSnapshot(
                ema20=198.0,
                ema50=195.0,
                ema200=180.0,
                rsi14=60.0,
                macd=2.0,
                macd_signal=1.5,
                atr14=4.0,
                volume_ratio=1.2,
            ),
            levels=LevelSnapshot(
                support=190.0,
                resistance=205.0,
            ),
            trade_plan={},
            guidance={},
            market_data_quality=quality if quality is not None else {
                "valid": True,
                "signal_allowed": True,
                "reliability": "verified",
                "gap_count": 0,
                "issues": [],
            },
        )

    def _decision(self, snapshot: AnalysisSnapshot):
        eligibility = evaluate_decision_eligibility(snapshot)

        return eligibility, evaluate_decision_policy(
            eligible=eligibility.eligible,
            score=snapshot.score,
            signal=snapshot.signal,
        )

    def test_m233_verified_strong_buy_reaches_buy(self):
        eligibility, decision = self._decision(self._snapshot())

        self.assertTrue(eligibility.eligible)
        self.assertEqual(decision.action, DecisionAction.BUY)
        self.assertTrue(decision.actionable)

    def test_m233_invalid_market_data_blocks_buy(self):
        snapshot = self._snapshot(
            quality={
                "valid": False,
                "signal_allowed": True,
                "reliability": "verified",
                "gap_count": 1,
                "issues": ["invalid"],
            }
        )

        eligibility, decision = self._decision(snapshot)

        self.assertFalse(eligibility.eligible)
        self.assertEqual(decision.action, DecisionAction.NO_SIGNAL)
        self.assertEqual(decision.confidence, 0)
        self.assertFalse(decision.actionable)

    def test_m233_signal_not_allowed_blocks_buy(self):
        snapshot = self._snapshot(
            quality={
                "valid": True,
                "signal_allowed": False,
                "reliability": "verified",
                "gap_count": 0,
                "issues": ["signal blocked"],
            }
        )

        eligibility, decision = self._decision(snapshot)

        self.assertFalse(eligibility.eligible)
        self.assertEqual(decision.action, DecisionAction.NO_SIGNAL)
        self.assertFalse(decision.actionable)

    def test_m233_unverified_market_data_blocks_buy(self):
        snapshot = self._snapshot(
            quality={
                "valid": True,
                "signal_allowed": True,
                "reliability": "unverified",
                "gap_count": 0,
                "issues": [],
            }
        )

        eligibility, decision = self._decision(snapshot)

        self.assertFalse(eligibility.eligible)
        self.assertEqual(decision.action, DecisionAction.NO_SIGNAL)
        self.assertEqual(decision.confidence, 0)

    def test_m233_high_score_cannot_bypass_gate(self):
        snapshot = self._snapshot(
            score=100,
            signal="BUY / STRONG",
            quality={
                "valid": False,
                "signal_allowed": False,
                "reliability": "unverified",
                "gap_count": 10,
                "issues": ["bad data"],
            },
        )

        eligibility, decision = self._decision(snapshot)

        self.assertFalse(eligibility.eligible)
        self.assertEqual(decision.action, DecisionAction.NO_SIGNAL)
        self.assertFalse(decision.actionable)

    def test_m233_unknown_signal_fails_closed_after_gate(self):
        snapshot = self._snapshot(
            score=90,
            signal="UNKNOWN",
        )

        eligibility, decision = self._decision(snapshot)

        self.assertTrue(eligibility.eligible)
        self.assertEqual(decision.action, DecisionAction.NO_SIGNAL)
        self.assertEqual(decision.confidence, 0)
        self.assertIn("UNMAPPED_SIGNAL", decision.reason_codes)

    def test_m233_non_buy_actions_are_not_actionable(self):
        cases = (
            ("WATCH", 65, DecisionAction.WATCH),
            ("HOLD", 50, DecisionAction.HOLD),
            ("AVOID / WEAK", 25, DecisionAction.AVOID),
        )

        for signal, score, expected in cases:
            with self.subTest(signal=signal):
                _, decision = self._decision(
                    self._snapshot(score=score, signal=signal)
                )

                self.assertEqual(decision.action, expected)
                self.assertFalse(decision.actionable)


if __name__ == "__main__":
    unittest.main()
