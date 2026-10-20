"""
Unit Tests for Deep Neuromorphic Parameter Sweeps & Pareto Optimization
========================================================================
Verifies:
  1. Grid configuration and parameter space validation.
  2. Single-point evaluation completeness and numerical sanity.
  3. Q16.16 fixed-point Verilog RTL parameter translation and quantization bounds.
  4. Non-dominated Pareto frontier extraction & utopian distance calculation.
  5. Lemma 3 compact synaptic projection invariance (||W||_F <= 32.0) across swept learning rates.

Author: Arunjyoti Sarma (Research Scholar, IIT (BHU), Varanasi)
"""

import os
import sys
import unittest
import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from neuroquant.analysis.parameter_sweep import (
    SweepGridConfig,
    SweepEvaluationPoint,
    NeuromorphicParameterSweepEngine,
)


class TestNeuromorphicParameterSweeps(unittest.TestCase):
    """Institutional unit test suite for Day 1 parameter sweeps."""

    def setUp(self):
        self.grid = SweepGridConfig(
            tau_m_values=[10.0, 20.0],
            v_thresh_values=[-55.0, -50.0],
            learning_rate_values=[0.001, 0.005],
            ticks_per_eval=500
        )
        self.engine = NeuromorphicParameterSweepEngine(grid_config=self.grid)

    def test_sweep_grid_initialization(self):
        """Validates parameter grid configuration and default boundaries."""
        self.assertEqual(len(self.grid.tau_m_values), 2)
        self.assertEqual(len(self.grid.v_thresh_values), 2)
        self.assertEqual(len(self.grid.learning_rate_values), 2)
        self.assertAlmostEqual(self.grid.v_rest, -70.0)
        self.assertAlmostEqual(self.grid.v_reset, -75.0)
        self.assertEqual(self.grid.num_sensory, 32)
        self.assertEqual(self.grid.num_hidden, 64)
        self.assertEqual(self.grid.num_motor, 4)

    def test_single_configuration_evaluation(self):
        """Verifies evaluation of a single parameter configuration."""
        pt = self.engine.evaluate_configuration(tau_m=20.0, v_thresh=-50.0, lr=0.005)
        
        self.assertIsInstance(pt, SweepEvaluationPoint)
        self.assertAlmostEqual(pt.tau_m, 20.0)
        self.assertAlmostEqual(pt.v_thresh, -50.0)
        self.assertAlmostEqual(pt.learning_rate, 0.005)
        
        # Performance metrics bounds
        self.assertGreaterEqual(pt.macro_f1, 0.0)
        self.assertLessEqual(pt.macro_f1, 1.0)
        self.assertGreaterEqual(pt.spike_sparsity, 0.5)
        self.assertLessEqual(pt.spike_sparsity, 1.0)
        self.assertGreater(pt.mean_latency_us, 0.0)
        self.assertGreaterEqual(pt.total_spikes, 0)

    def test_rtl_fixed_point_mapping(self):
        """Verifies exact signed Q16.16 fixed-point RTL parameter mapping and sub-microvolt error."""
        rtl = NeuromorphicParameterSweepEngine.compute_rtl_constants(
            tau_m=20.0,
            v_thresh=-50.0,
            dt_ms=0.5,
            v_rest=-70.0,
            v_reset=-75.0
        )
        
        # Expected beta = exp(-0.5 / 20.0) = 0.9753099
        expected_beta = np.exp(-0.5 / 20.0)
        self.assertAlmostEqual(rtl["beta"], expected_beta, places=6)
        
        # Q16.16 Beta: round(beta * 65536) = 63918
        self.assertEqual(rtl["rtl_beta_q16"], int(round(expected_beta * 65536.0)))
        self.assertEqual(rtl["rtl_one_minus_beta_q16"], 65536 - rtl["rtl_beta_q16"])
        
        # Q16.16 V_THRESH: -50.0 * 65536 = -3276800
        self.assertEqual(rtl["rtl_v_thresh_q16"], -3276800)
        self.assertEqual(rtl["rtl_v_rest_q16"], -4587520)
        self.assertEqual(rtl["rtl_v_reset_q16"], -4915200)
        
        # Sub-nanovolt quantization residual
        self.assertLess(rtl["quant_error_mv"], 1e-4, "Quantization error must be < 0.0001 mV")

    def test_pareto_frontier_dominance(self):
        """Verifies that extracted Pareto-optimal points are strictly non-dominated."""
        # Run small 8-point sweep
        results = self.engine.run_sweep(verbose=False)
        self.assertEqual(len(results), 8)
        self.assertGreater(len(self.engine.pareto_frontier), 0)
        
        # Check non-dominance
        for p in self.engine.pareto_frontier:
            self.assertTrue(p.is_pareto_optimal)
            # Verify no other point dominates p
            for other in results:
                if other != p:
                    # other dominates p if other is >= in all 4 and strictly > in one
                    dominates = (
                        other.macro_f1 >= p.macro_f1 and
                        other.spike_sparsity >= p.spike_sparsity and
                        other.mean_latency_us <= p.mean_latency_us and
                        other.sharpe_ratio >= p.sharpe_ratio and
                        (other.macro_f1 > p.macro_f1 or
                         other.spike_sparsity > p.spike_sparsity or
                         other.mean_latency_us < p.mean_latency_us or
                         other.sharpe_ratio > p.sharpe_ratio)
                    )
                    self.assertFalse(dominates, f"Point {other} dominates Pareto point {p}")
                    
        # Check champion knee point exists and has minimum utopian distance
        self.assertIsNotNone(self.engine.champion)
        min_dist = min(pt.utopian_distance for pt in self.engine.pareto_frontier)
        self.assertAlmostEqual(self.engine.champion.utopian_distance, min_dist)

    def test_lemma_3_synaptic_boundedness_across_rates(self):
        """Verifies Lemma 3 compact projection invariant (||W||_F <= 32.0) holds unconditionally."""
        rates = [0.0005, 0.001, 0.005, 0.010, 0.020]
        for lr in rates:
            pt = self.engine.evaluate_configuration(tau_m=20.0, v_thresh=-50.0, lr=lr)
            self.assertTrue(pt.is_lemma_3_satisfied)
            self.assertLessEqual(pt.final_frobenius_norm, pt.lemma_3_bound + 1e-4)


if __name__ == "__main__":
    unittest.main()
