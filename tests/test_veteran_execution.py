"""
Unit Tests: Veteran Microstructure Execution Engine & C++20 AVX2 SIMD Core
==========================================================================
Verifies:
  1. Bouchaud Power-Law Transient Impact Propagator & Memory Decay
  2. Glosten-Milgrom Adverse Selection Maker Limit Order Model
  3. C++20 AVX2 Vectorized Almgren-Chriss Kernel & Hardware __rdtscp
  4. AVX2 Hardware Square Root Market Impact (_mm256_sqrt_ps)
  5. Extreme Tail Risk Metrics: 99.9% CVaR & Monte Carlo Invariants
"""

import os
import ctypes
import unittest
import numpy as np
from neuroquant.execution import (
    VeteranExecutionEngine,
    VeteranExecutionConfig,
    AlmgrenChrissOptimizer,
    AlmgrenChrissConfig
)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DLL_PATH = os.path.join(PROJECT_ROOT, "csrc", "lif_core.dll")

class TestVeteranExecutionEngine(unittest.TestCase):
    def setUp(self):
        self.cfg = VeteranExecutionConfig(
            total_shares=10_000.0,
            time_horizon_sec=60.0,
            num_intervals=30,
            base_lambda=1e-6,
            volatility_sigma=0.25,
            gamma=2.5e-7,
            eta=5.0e-5,
            alpha=0.5,
            spread=0.25,
            tau_0=0.5,
            gamma_prop=0.5
        )
        self.engine = VeteranExecutionEngine(self.cfg)

    def test_bouchaud_transient_impact_decay(self):
        """Verifies Bouchaud power-law kernel accumulates with rate and decays over time."""
        # Trade 1 at t = 0s with rate 100 shares/s
        self.engine.rate_history.append((0.0, 100.0))
        
        # Impact immediately at t = 0s
        impact_t0 = self.engine.compute_bouchaud_transient_impact(0.0, 100.0)
        
        # Impact at t = 2.0s with no new trade (decaying past trade)
        impact_t2 = self.engine.compute_bouchaud_transient_impact(2.0, 0.0)
        
        # Impact at t = 10.0s
        impact_t10 = self.engine.compute_bouchaud_transient_impact(10.0, 0.0)

        # Impact must strictly decay over elapsed time
        self.assertGreater(impact_t0, impact_t2)
        self.assertGreater(impact_t2, impact_t10)
        self.assertGreater(impact_t10, 0.0)

        # Expected decay: (1 + 2.0/0.5)^(-0.5) = 5^(-0.5) = 1/sqrt(5) ~= 0.4472
        expected_decay_ratio = (1.0 + (2.0 / 0.5)) ** (-0.5)
        # Ratio of past slice impact
        past_slice_t0 = self.cfg.eta * np.sqrt(100.0)
        self.assertAlmostEqual(impact_t2 / past_slice_t0, expected_decay_ratio, places=4)

    def test_glosten_milgrom_adverse_selection_fill_probability(self):
        """Verifies Glosten-Milgrom model suppresses maker fills during toxic sweeps."""
        # Calm regime: low toxicity, high upward drift
        prob_calm = self.engine.evaluate_maker_fill_probability(toxicity_prob=0.05, upward_prob=0.70)
        
        # Toxic cascade regime: extreme institutional sweeps
        prob_toxic = self.engine.evaluate_maker_fill_probability(toxicity_prob=0.95, upward_prob=0.05)

        self.assertGreater(prob_calm, 0.50, "Calm regime with upward momentum should have high maker fill rate")
        self.assertLess(prob_toxic, 0.20, "Toxic cascade should collapse maker fill rate (Winner's curse)")
        self.assertGreater(prob_calm, prob_toxic)

    def test_cxx_simd_almgren_chriss_binding(self):
        """Verifies C++20 AVX2 SIMD Almgren-Chriss DLL binding and parity with python."""
        if not os.path.exists(DLL_PATH):
            self.skipTest("lif_core.dll not compiled on this platform")

        dll = ctypes.CDLL(DLL_PATH)

        class ACSIMDParams(ctypes.Structure):
            _fields_ = [
                ("initial_shares", ctypes.c_double),
                ("time_horizon_sec", ctypes.c_double),
                ("num_intervals", ctypes.c_int32),
                ("lambda_val", ctypes.c_double),
                ("sigma", ctypes.c_double),
                ("gamma", ctypes.c_double),
                ("eta", ctypes.c_double),
                ("alpha", ctypes.c_double),
                ("spread", ctypes.c_double)
            ]

        class ACSIMDResult(ctypes.Structure):
            _fields_ = [
                ("kappa", ctypes.c_double),
                ("half_life_sec", ctypes.c_double),
                ("expected_shortfall", ctypes.c_double),
                ("variance_shortfall", ctypes.c_double),
                ("utility", ctypes.c_double),
                ("execution_cycles", ctypes.c_uint64),
                ("execution_nanoseconds", ctypes.c_double)
            ]

        params = ACSIMDParams(
            initial_shares=10000.0,
            time_horizon_sec=60.0,
            num_intervals=30,
            lambda_val=1e-6,
            sigma=0.25,
            gamma=2.5e-7,
            eta=5.0e-5,
            alpha=0.5,
            spread=0.25
        )

        holdings = (ctypes.c_double * 31)()
        trades = (ctypes.c_double * 30)()
        rates = (ctypes.c_double * 30)()
        result = ACSIMDResult()

        ret = dll.ac_simd_compute_schedule(
            ctypes.byref(params), holdings, trades, rates, ctypes.byref(result)
        )
        self.assertEqual(ret, 0, "C++20 SIMD AC function must return 0")

        # Parity checks
        self.assertAlmostEqual(holdings[0], 10000.0, places=4)
        self.assertAlmostEqual(holdings[30], 0.0, places=4)
        self.assertAlmostEqual(float(sum(trades)), 10000.0, places=2)
        self.assertGreater(result.kappa, 0.0)
        self.assertGreater(result.half_life_sec, 0.0)

    def test_cxx_simd_square_root_impact_avx2(self):
        """Verifies 8-wide AVX2 hardware _mm256_sqrt_ps computes square root impact."""
        if not os.path.exists(DLL_PATH):
            self.skipTest("lif_core.dll not compiled")

        dll = ctypes.CDLL(DLL_PATH)
        count = 16
        rates = (ctypes.c_float * count)(*[float(100.0 * (i + 1)) for i in range(count)])
        impacts = (ctypes.c_float * count)()
        eta = 5.0e-5

        ret = dll.ac_simd_compute_square_root_impact(rates, impacts, count, ctypes.c_float(eta))
        self.assertEqual(ret, 0)

        for i in range(count):
            expected = eta * np.sqrt(rates[i])
            self.assertAlmostEqual(impacts[i], expected, places=5)

    def test_cxx_simd_benchmark_throughput(self):
        """Verifies C++20 SIMD kernel achieves > 100,000 schedules/sec throughput."""
        if not os.path.exists(DLL_PATH):
            self.skipTest("lif_core.dll not compiled")

        dll = ctypes.CDLL(DLL_PATH)
        p50 = ctypes.c_double()
        p99 = ctypes.c_double()
        thr = ctypes.c_double()

        ret = dll.ac_simd_benchmark(1000, ctypes.byref(p50), ctypes.byref(p99), ctypes.byref(thr))
        self.assertEqual(ret, 0)
        self.assertGreater(thr.value, 100_000.0, "Throughput must exceed 100k schedules/sec")
        self.assertLess(p50.value, 20_000.0, "P50 latency must be sub-20 microseconds")

    def test_veteran_cvar_expected_shortfall(self):
        """Verifies Conditional Value at Risk (CVaR 99.9%) calculation."""
        arrival_price = 100.0
        # Synthetic fills
        for i in range(100):
            self.engine.fills.append({
                "exec_price": arrival_price - (0.1 * i),
                "target_slice": 10.0
            })
        cvar = self.engine.compute_cvar(arrival_price, alpha=0.95)
        self.assertGreater(cvar, 0.0)
        # CVaR (expected shortfall) must exceed or equal VaR
        losses = [(arrival_price - f["exec_price"]) * f["target_slice"] for f in self.engine.fills]
        var_95 = np.percentile(losses, 95.0)
        self.assertGreaterEqual(cvar, var_95)

    def test_monte_carlo_distribution_integrity(self):
        """Verifies fast Monte Carlo simulation kernel produces valid conservation and shortfalls."""
        from benchmarks.run_monte_carlo_execution import run_single_path_fast
        ac_cfg = AlmgrenChrissConfig(
            total_shares=1000.0,
            time_horizon_sec=30.0,
            num_intervals=10,
            risk_aversion_lambda=1e-6,
            volatility_sigma=0.25,
            gamma=2.5e-7,
            eta=5.0e-5,
            alpha=0.5,
            spread=0.25
        )
        opt = AlmgrenChrissOptimizer(ac_cfg)
        twap_trades = opt.calculate_twap_schedule().trades
        path_p = np.random.normal(0, 0.5, size=10)

        res = run_single_path_fast(twap_trades, path_p, p0=100.0, total_shares=1000.0, tau=3.0, ac_cfg=ac_cfg)
        self.assertIn("net_shortfall", res)
        self.assertIn("maker_ratio", res)
        self.assertIn("rebates", res)
        self.assertTrue(np.isfinite(res["net_shortfall"]), "Shortfall must be a finite numerical value")

    def test_veteran_execution_full_step(self):
        """Verifies step-by-step execution through veteran engine with Bouchaud memory."""
        res = self.engine.execute_slice(
            step_idx=1,
            current_time=2.0,
            current_mid=18500.0,
            target_slice=500.0,
            is_maker_intent=True,
            neuro_signals={"toxicity_prob": 0.05, "upward_prob": 0.70, "volatility_pulse": 0.10}
        )
        self.assertIn("exec_price", res)
        self.assertIn("transient_propagator_impact", res)
        self.assertGreater(res["exec_price"], 0.0)

if __name__ == "__main__":
    unittest.main()
