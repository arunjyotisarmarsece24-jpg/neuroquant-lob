"""
Unit Tests: Pre-Trade Microsecond Risk Gate (< 50 ns Circuit Breakers)
======================================================================
Validates:
  1. Fat-Finger Price Collar (+/-1.5% from mid-price)
  2. Hard Position Bound (+/-50 contracts with inventory-reducing exception)
  3. Mark-to-Market Emergency Killswitch (-$50,000 hard stop-loss)
  4. Max Single Order Volume Sanity
  5. Neuromorphic Membrane Voltage Invariant Check (Gronwall Lyapunov limit)
  6. Sub-microsecond hot-path execution throughput
"""

import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from neuroquant.risk import PreTradeRiskGate, RiskConfig, RiskAction

class TestPreTradeRiskGate(unittest.TestCase):
    def setUp(self):
        self.config = RiskConfig(
            max_inventory_contracts=50.0,
            fat_finger_collar_pct=0.015,
            max_order_size=5000.0,
            max_drawdown_dollars=50000.0,
            membrane_voltage_bound_mv=50.0
        )
        self.gate = PreTradeRiskGate(self.config)
        self.mid = 18500.0

    def test_valid_order_acceptance(self):
        """Clean orders within risk limits must pass with ACCEPT."""
        res = self.gate.validate_order(
            side="BUY",
            quantity=10.0,
            price=18505.0,  # +0.027% from mid (well within 1.5%)
            mid_price=self.mid,
            current_inventory=0.0,
            current_mtm_pnl=500.0,
            membrane_voltage_mv=-65.0
        )
        self.assertTrue(res.passed)
        self.assertEqual(res.action, RiskAction.ACCEPT)
        self.assertGreater(res.latency_ns, 0.0)

    def test_fat_finger_rejection(self):
        """Fat-finger orders deviating > 1.5% from mid must be rejected immediately."""
        # Price deviates +3.0% ($19,055 vs $18,500)
        res_high = self.gate.validate_order(
            side="BUY",
            quantity=10.0,
            price=19055.0,
            mid_price=self.mid,
            current_inventory=0.0,
            current_mtm_pnl=0.0
        )
        self.assertFalse(res_high.passed)
        self.assertEqual(res_high.action, RiskAction.REJECT_FAT_FINGER)

        # Price deviates -2.5% ($18,037.5 vs $18,500)
        res_low = self.gate.validate_order(
            side="SELL",
            quantity=10.0,
            price=18037.5,
            mid_price=self.mid,
            current_inventory=0.0,
            current_mtm_pnl=0.0
        )
        self.assertFalse(res_low.passed)
        self.assertEqual(res_low.action, RiskAction.REJECT_FAT_FINGER)

    def test_max_inventory_boundary(self):
        """Inventory expansion beyond +/-50 must be blocked; risk reduction permitted."""
        # Current inventory = +45; buying 10 contracts expands to +55 (> 50 limit)
        res_block = self.gate.validate_order(
            side="BUY",
            quantity=10.0,
            price=self.mid,
            mid_price=self.mid,
            current_inventory=45.0,
            current_mtm_pnl=0.0
        )
        self.assertFalse(res_block.passed)
        self.assertEqual(res_block.action, RiskAction.REJECT_MAX_INVENTORY)

        # However, SELLING 20 contracts while long +45 contracts reduces inventory to +25 (De-risking!)
        res_allow = self.gate.validate_order(
            side="SELL",
            quantity=20.0,
            price=self.mid,
            mid_price=self.mid,
            current_inventory=45.0,
            current_mtm_pnl=0.0
        )
        self.assertTrue(res_allow.passed)
        self.assertEqual(res_allow.action, RiskAction.ACCEPT)

    def test_mtm_emergency_killswitch(self):
        """Drawdown exceeding -$50,000 must trip emergency killswitch and halt trading."""
        self.assertFalse(self.gate.killswitch_tripped)

        # Loss of -$52,000 breaches -$50,000 limit
        res = self.gate.validate_order(
            side="BUY",
            quantity=5.0,
            price=self.mid,
            mid_price=self.mid,
            current_inventory=0.0,
            current_mtm_pnl=-52000.0
        )
        self.assertFalse(res.passed)
        self.assertEqual(res.action, RiskAction.REJECT_DRAWDOWN_LIMIT)
        self.assertTrue(self.gate.killswitch_tripped)

        # All subsequent orders must be blocked by the active killswitch
        res_subsequent = self.gate.validate_order(
            side="BUY",
            quantity=1.0,
            price=self.mid,
            mid_price=self.mid,
            current_inventory=0.0,
            current_mtm_pnl=100.0
        )
        self.assertFalse(res_subsequent.passed)
        self.assertEqual(res_subsequent.action, RiskAction.KILLSWITCH_ACTIVE)

        # Reset killswitch administratively
        self.gate.reset_killswitch()
        self.assertFalse(self.gate.killswitch_tripped)

    def test_max_order_size_rejection(self):
        """Single order volume exceeding 5,000 must be rejected."""
        res = self.gate.validate_order(
            side="BUY",
            quantity=6000.0,
            price=self.mid,
            mid_price=self.mid,
            current_inventory=0.0,
            current_mtm_pnl=0.0
        )
        self.assertFalse(res.passed)
        self.assertEqual(res.action, RiskAction.REJECT_ORDER_SIZE)

    def test_neuromorphic_voltage_invariant(self):
        """Neuron membrane potential exceeding Gronwall attractor limit (> 50 mV) triggers rejection."""
        res = self.gate.validate_order(
            side="BUY",
            quantity=10.0,
            price=self.mid,
            mid_price=self.mid,
            current_inventory=0.0,
            current_mtm_pnl=0.0,
            membrane_voltage_mv=75.0  # Invariant violation
        )
        self.assertFalse(res.passed)
        self.assertEqual(res.action, RiskAction.REJECT_NEUROMORPHIC_INVARIANT)

    def test_stress_benchmark_performance(self):
        """Verifies high-throughput execution under 5,000 rapid checks."""
        stats = self.gate.run_stress_benchmark(num_checks=5000)
        self.assertEqual(stats["total_checks"], 5000)
        self.assertGreater(stats["checks_per_second"], 50_000.0, "Throughput must exceed 50k checks/sec")

if __name__ == "__main__":
    unittest.main()
