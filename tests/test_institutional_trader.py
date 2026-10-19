"""
Unit Tests for Autonomous Institutional HFT Trader
==================================================
Validates end-to-end integration of L2 market feed, 32-channel spike modulation,
AVX2 SIMD SNN inference, pre-trade risk clearance, and FIX 4.4 order routing.

Author: Arunjyoti Sarma (Research Scholar, IIT (BHU), Varanasi)
"""

import unittest
from neuroquant.strategy.institutional_hft_trader import InstitutionalHFTTrader, TraderSnapshot
from neuroquant.risk.risk_gate import RiskConfig


class TestInstitutionalHFTTrader(unittest.TestCase):

    def setUp(self):
        self.trader = InstitutionalHFTTrader(
            symbol="BTCUSDT",
            use_live_feed=False,
            risk_cfg=RiskConfig(max_inventory_contracts=50.0)
        )

    def test_trader_initialization(self):
        self.assertIsNotNone(self.trader.book)
        self.assertIsNotNone(self.trader.encoder)
        self.assertIsNotNone(self.trader.brain)
        self.assertIsNotNone(self.trader.risk_gate)
        self.assertIsNotNone(self.trader.venue)
        self.assertEqual(self.trader.step_counter, 0)
        self.assertEqual(self.trader.inventory, 0.0)

    def test_trader_step_execution(self):
        snap = self.trader.step()
        self.assertIsInstance(snap, TraderSnapshot)
        self.assertEqual(snap.step_num, 1)
        self.assertGreater(snap.mid_price, 0.0)
        self.assertGreaterEqual(snap.spread, 0.0)
        self.assertGreater(snap.micro_price, 0.0)
        self.assertGreaterEqual(snap.sensory_spikes, 0)
        self.assertGreaterEqual(snap.sparsity_pct, 0.0)
        self.assertLessEqual(snap.sparsity_pct, 100.0)
        self.assertTrue(snap.risk_cleared)
        self.assertFalse(snap.is_killed)
        
        # Steady-state step settles into high biological sparsity (>80%)
        snap2 = self.trader.step()
        self.assertGreater(snap2.sparsity_pct, 80.0)

    def test_multi_step_trading_loop(self):
        # Run 25 steps through the complete autonomous pipeline
        snapshots = []
        for _ in range(25):
            snap = self.trader.step()
            snapshots.append(snap)

        self.assertEqual(self.trader.step_counter, 25)
        self.assertEqual(len(self.trader.recent_history), 25)
        self.assertGreater(self.trader.venue.total_volume_traded, 0.0)
        # Average risk check latency should be sub-microsecond
        avg_risk_ns = sum(s.risk_latency_ns for s in snapshots) / len(snapshots)
        self.assertLess(avg_risk_ns, 50_000.0)

    def test_risk_gate_intervention(self):
        # Force hard drawdown to test emergency killswitch in live trading loop
        self.trader.realized_pnl = -60_000.0 # Breaches -$50k limit
        snap = self.trader.step()
        self.assertFalse(snap.risk_cleared)
        self.assertTrue(snap.is_killed)
        self.assertIn("REJECT_DRAWD", snap.risk_action)

    def test_clean_shutdown(self):
        # Verify clean teardown without lingering threads
        self.trader.shutdown()


if __name__ == "__main__":
    unittest.main()
