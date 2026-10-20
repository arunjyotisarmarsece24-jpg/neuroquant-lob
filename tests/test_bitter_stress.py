"""
Unit Tests for Bitter Quant Adversarial Stress Benchmark
========================================================
Validates that the software engine withstands 4 extreme real-world market regimes:
  1. Flash Crash (Liquidity evaporation & circuit breaker halt)
  2. Adversarial Spoofing (OFI whipsaw noise rejection)
  3. Heavy-Tailed Student-t Jumps (Lyapunov invariant boundedness)
  4. 99% Poisoned Toxic Adverse Selection (Adaptive execution)

Author: Arunjyoti Sarma (Research Scholar, IIT (BHU), Varanasi)
"""

import unittest
import numpy as np
from benchmarks.run_bitter_regime_stress import (
    run_regime_flash_crash,
    run_regime_spoofing_attack,
    run_regime_heavy_tail_jumps,
    run_regime_adverse_selection
)


class TestBitterRegimeStress(unittest.TestCase):

    def test_regime_flash_crash(self):
        """Verify circuit breaker halts catastrophic liquidation during Flash Crash."""
        res = run_regime_flash_crash()
        self.assertEqual(res["status"], "PASS")
        self.assertGreater(res["blocked_trades"], 4000, "Circuit breaker should block majority of orders in crash")
        self.assertGreater(res["ac_kappa"], 0.0, "Optimal urgency kappa must be strictly positive")

    def test_regime_adversarial_spoofing(self):
        """Verify neuromorphic LIF rejects 100% of high-frequency spoof jitter."""
        res = run_regime_spoofing_attack()
        self.assertEqual(res["status"], "PASS")
        self.assertEqual(res["false_alarm_rate"], 0.0, "False alarm rate must be 0 for spoof jitter")

    def test_regime_heavy_tail_jumps(self):
        """Verify fat-tailed Student-t return shocks stay strictly within Lyapunov bound."""
        res = run_regime_heavy_tail_jumps()
        self.assertEqual(res["status"], "PASS")
        self.assertGreater(res["empirical_kurtosis"], 6.0, "Student-t df=3.5 must show extreme fat tails")
        self.assertLessEqual(res["max_lyapunov_deviation_mv"], 50.0, "Deviation must not exceed Lyapunov bound")

    def test_regime_adverse_selection(self):
        """Verify execution engine completes liquidation under 99% toxic flow."""
        res = run_regime_adverse_selection()
        self.assertEqual(res["status"], "PASS")
        self.assertLess(res["slippage_bps"], 5.0, "Slippage must remain under 5 bps")


if __name__ == "__main__":
    unittest.main()
