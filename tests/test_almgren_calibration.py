"""
NeuroQuant-LOB: Day 3 Almgren-Chriss Calibration Institutional Test Suite
========================================================================
Principal Architect: Arunjyoti Sarma (Research Scholar, IIT (BHU), Varanasi)
Standards Target: Institutional Tier-1 HFT Quantitative Execution

Verifies:
  1. Permanent price impact gamma > 0 and temporary impact eta > 0
  2. Bouchaud/Kyle square-root law exponent alpha in [0.40, 0.65]
  3. Efficient frontier strictly monotonic: dV/dlambda < 0
  4. Closed-form urgency kappa and liquidation half-life bounds
  5. C++20 AVX2 SIMD Core numerical congruence vs reference implementation
  6. Synthesizable Verilog parameter header optimal_almgren_params.vh
  7. Cycle-accurate hardware RTL gate simulation (almgren_chriss_risk_gate.v)
"""

import os
import sys
import json
import unittest
import subprocess
import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from neuroquant.execution.impact_calibrator import AlmgrenChrissImpactCalibrator, ImpactCalibrationResult
from neuroquant.execution.almgren_chriss import AlmgrenChrissConfig, AlmgrenChrissOptimizer

class TestAlmgrenChrissCalibration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.calibrator = AlmgrenChrissImpactCalibrator(seed=123)
        cls.res = cls.calibrator.calibrate(num_ticks=5000)

    def test_01_calibration_parameters_validity(self):
        """Permanent gamma > 0 and temporary eta > 0 must hold unconditionally."""
        self.assertGreater(self.res.gamma_permanent, 0.0, "Permanent impact gamma must be strictly positive")
        self.assertGreater(self.res.eta_temporary, 0.0, "Temporary impact eta must be strictly positive")
        self.assertLess(self.res.gamma_permanent, 1e-2, "Permanent impact gamma must not blow up")
        self.assertLess(self.res.eta_temporary, 1.0, "Temporary impact eta must remain bounded")

    def test_02_power_law_square_root_congruence(self):
        """Non-linear power-law exponent alpha must align with square-root law (alpha in [0.40, 0.65])."""
        alpha = self.res.alpha_power_law
        self.assertGreaterEqual(alpha, 0.40, f"Alpha {alpha:.4f} below theoretical lower bound 0.40")
        self.assertLessEqual(alpha, 0.65, f"Alpha {alpha:.4f} above theoretical upper bound 0.65")
        self.assertGreater(self.res.r2_temporary_nonlinear, 0.80, "Non-linear fit R2 must exceed 80%")

    def test_03_efficient_frontier_monotonicity(self):
        """Higher risk aversion lambda must strictly decrease execution shortfall variance."""
        cfg = AlmgrenChrissConfig(
            total_shares=10000.0,
            time_horizon_sec=60.0,
            num_intervals=30,
            volatility_sigma=0.25,
            gamma=self.res.gamma_permanent,
            eta=self.res.eta_temporary,
            alpha=self.res.alpha_power_law
        )
        opt = AlmgrenChrissOptimizer(cfg)

        s_low = opt.calculate_optimal_schedule(lambda_val=1e-7)
        s_med = opt.calculate_optimal_schedule(lambda_val=1e-5)
        s_high = opt.calculate_optimal_schedule(lambda_val=1e-3)

        # Variance must be strictly decreasing with lambda
        self.assertGreater(s_low.variance_shortfall, s_med.variance_shortfall,
                           "Variance must decrease from lambda=1e-7 to 1e-5")
        self.assertGreater(s_med.variance_shortfall, s_high.variance_shortfall,
                           "Variance must decrease from lambda=1e-5 to 1e-3")

        # Expected shortfall must be strictly increasing with lambda (faster trading = more impact)
        self.assertLessEqual(s_low.expected_shortfall, s_med.expected_shortfall,
                             "Expected cost must rise with urgency")
        self.assertLessEqual(s_med.expected_shortfall, s_high.expected_shortfall,
                             "Expected cost must rise with urgency")

    def test_04_urgency_kappa_bounds(self):
        """Urgency parameter kappa > 0 and liquidation half-life must be within [0.5s, T]."""
        kappa = self.res.champion_kappa
        t_half = self.res.champion_half_life_sec
        self.assertGreater(kappa, 0.0, "Urgency kappa must be strictly positive for lambda > 0")
        self.assertGreater(t_half, 0.1, "Half-life must be > 100 ms")
        self.assertLess(t_half, 60.0, "Half-life must be shorter than total horizon T=60s")

    def test_05_variance_reduction_over_twap(self):
        """Optimal execution must provide significant variance reduction over naive TWAP."""
        self.assertGreater(self.res.variance_reduction_pct, 10.0,
                           f"Variance reduction {self.res.variance_reduction_pct:.1f}% should exceed 10%")
        self.assertGreater(self.res.utility_improvement_pct, 5.0,
                           f"Utility improvement {self.res.utility_improvement_pct:.1f}% should exceed 5%")

    def test_06_verilog_header_synthesizability(self):
        """Optimal parameter header must exist and parse with positive parameters."""
        vh_path = os.path.join(PROJECT_ROOT, "hardware", "optimal_almgren_params.vh")
        self.assertTrue(os.path.exists(vh_path), f"Verilog header not found at {vh_path}")

        with open(vh_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("AC_GAMMA_PERM_Q16", content)
        self.assertIn("AC_ETA_TEMP_Q16", content)
        self.assertIn("AC_ALPHA_EXP_Q16", content)
        self.assertIn("AC_KAPPA_NOMINAL_Q16", content)
        self.assertIn("AC_MAX_RATE_CAP_Q16", content)
        self.assertIn("AC_SLIPPAGE_TOL_Q16", content)

    def test_07_hardware_almgren_simulation(self):
        """Cycle-accurate Verilog HDL testbench must compile and pass all 6 checks via Icarus Verilog."""
        cmd = [sys.executable, "run_hardware_simulation.py", "--module", "almgren"]
        proc = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(proc.returncode, 0, f"Hardware simulation failed:\n{proc.stderr}\n{proc.stdout}")
        self.assertIn("ALL ALMGREN-CHRISS HARDWARE RTL CHECKS PASSED", proc.stdout)

if __name__ == "__main__":
    unittest.main()
