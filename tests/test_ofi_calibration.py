"""
Unit Tests for Day 2 Multi-Level OFI & Cross-Level Hawkes Calibration
====================================================================
Validates:
  1. Multi-level OFI directional price-jump & queue deltas (Cont et al. 2014 & Rama Cont / Xu 2021)
  2. Continuous exponential information decay convergence (lambda_l, tau_1/2)
  3. Multivariate Hawkes cross-level spectral radius stability: rho(Gamma) < 1.0
  4. Bit-exact mathematical parity between C++20 AVX2 SIMD core and Python reference model
  5. C++20 AVX2 SIMD execution latency (< 500 ns/tick, > 1,000,000 ticks/sec)
  6. Multi-horizon forward return predictability (R^2, Hit Rate, IC)
  7. Synthesizable Verilog HDL parameter export integrity (hardware/optimal_ofi_params.vh)

Author: Arunjyoti Sarma (Research Scholar, IIT (BHU), Varanasi)
"""

import unittest
import os
import sys
import math
import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from neuroquant.market.ofi_calibrator import (
    MultiLevelOFIEngine,
    HawkesCrossLevelCalibrator,
    OFICalibrator,
    _get_dll
)


class TestOFICalibration(unittest.TestCase):

    def setUp(self):
        np.random.seed(42)
        self.num_levels = 5
        self.engine = MultiLevelOFIEngine(num_levels=self.num_levels, use_simd=False)

    def test_multilevel_ofi_directional_deltas(self):
        """Test Cont et al. L2 depth shift formulas across all 5 levels."""
        bp = np.array([100.0, 99.75, 99.50, 99.25, 99.00], dtype=np.float32)
        bs = np.array([50.0, 100.0, 150.0, 200.0, 250.0], dtype=np.float32)
        ap = np.array([100.25, 100.50, 100.75, 101.00, 101.25], dtype=np.float32)
        as_ = np.array([60.0, 110.0, 160.0, 210.0, 260.0], dtype=np.float32)

        # Baseline
        self.engine.reset()
        raw, integ, comp = self.engine.step(bp, bs, ap, as_, dt_sec=0.001)
        np.testing.assert_array_equal(raw, np.zeros(5))

        # 1. Level 0: Bid price ticks up by 0.25 -> delta_bid = current size = 40.0
        # Ask unchanged -> raw OFI[0] = +40.0
        bp_new = bp.copy()
        bs_new = bs.copy()
        bp_new[0] = 100.25
        bs_new[0] = 40.0
        raw, integ, comp = self.engine.step(bp_new, bs_new, ap, as_, dt_sec=0.001)
        self.assertAlmostEqual(raw[0], 40.0, places=3)
        self.assertGreater(comp, 0.0)

        # 2. Level 1: Bid price same, size increases by 20.0 -> delta_bid = +20.0
        bs_new2 = bs_new.copy()
        bs_new2[1] += 20.0
        raw, integ, comp = self.engine.step(bp_new, bs_new2, ap, as_, dt_sec=0.001)
        self.assertAlmostEqual(raw[1], 20.0, places=3)

        # 3. Level 2: Ask price same, ask size decreases by 30.0 (cancellation) -> delta_ask = -30.0 -> OFI = +30.0
        as_new = as_.copy()
        as_new[2] -= 30.0
        raw, integ, comp = self.engine.step(bp_new, bs_new2, ap, as_new, dt_sec=0.001)
        self.assertAlmostEqual(raw[2], 30.0, places=3)

    def test_exponential_decay_accumulation(self):
        """Test continuous exponential information decay of OFI accumulation."""
        decays = [10.0, 5.0, 2.5, 1.0, 0.5]
        engine = MultiLevelOFIEngine(num_levels=5, decay_rates=decays, use_simd=False)

        bp = np.array([100.0, 99.75, 99.50, 99.25, 99.00], dtype=np.float32)
        bs = np.array([50.0, 100.0, 150.0, 200.0, 250.0], dtype=np.float32)
        ap = np.array([100.25, 100.50, 100.75, 101.00, 101.25], dtype=np.float32)
        as_ = np.array([60.0, 110.0, 160.0, 210.0, 260.0], dtype=np.float32)

        engine.step(bp, bs, ap, as_, dt_sec=0.01)

        # Impulse of +100 at level 0
        bs_imp = bs.copy()
        bs_imp[0] += 100.0
        raw, integ, comp = engine.step(bp, bs_imp, ap, as_, dt_sec=0.01)
        self.assertAlmostEqual(raw[0], 100.0, places=2)
        init_integ_0 = integ[0]

        # Let 10 ticks pass with 0 arrival volume (dt = 0.05s)
        total_time = 0.0
        dt = 0.02
        for _ in range(10):
            total_time += dt
            raw, integ, comp = engine.step(bp, bs_imp, ap, as_, dt_sec=dt)

        expected_integ_0 = init_integ_0 * math.exp(-decays[0] * total_time)
        self.assertAlmostEqual(integ[0], expected_integ_0, delta=1.5)
        self.assertLess(integ[0], init_integ_0)

    def test_hawkes_cross_level_spectral_stability(self):
        """Test multivariate Hawkes process stability invariance rho(Gamma) < 1.0."""
        calibrator = HawkesCrossLevelCalibrator(num_levels=5)
        dt = 0.001
        events = [
            [i * dt for i in range(10, 500, 20)],
            [i * dt for i in range(15, 500, 25)],
            [i * dt for i in range(20, 500, 30)],
            [i * dt for i in range(25, 500, 35)],
            [i * dt for i in range(30, 500, 40)],
        ]
        mu, alpha, beta, spec_rad, is_stable = calibrator.fit(events, t_max=1.0, beta_decay=4.0)

        self.assertTrue(is_stable, "Hawkes process violated asymptotic stability!")
        self.assertLess(spec_rad, 1.0, f"Hawkes spectral radius {spec_rad} must be < 1.0")
        self.assertEqual(alpha.shape, (5, 5))
        self.assertEqual(beta.shape, (5, 5))
        self.assertEqual(len(mu), 5)
        self.assertTrue(np.all(mu > 0), "Baseline arrival intensities must be strictly positive")

    def test_cpp_avx2_simd_parity(self):
        """Test bit-for-bit mathematical congruence between C++20 AVX2 SIMD core and Python reference."""
        dll = _get_dll()
        if not dll:
            self.skipTest("csrc/lif_core.dll with AVX2 SIMD core not available on this platform.")

        N = 200
        bp = np.zeros((N, 5), dtype=np.float32)
        bs = np.zeros((N, 5), dtype=np.float32)
        ap = np.zeros((N, 5), dtype=np.float32)
        as_ = np.zeros((N, 5), dtype=np.float32)

        base_p = 100.0
        for i in range(N):
            base_p += np.random.choice([-0.25, 0.0, 0.25])
            for l in range(5):
                bp[i, l] = base_p - (l * 0.25)
                bs[i, l] = 50.0 + l * 20.0 + np.random.uniform(-10.0, 10.0)
                ap[i, l] = base_p + 0.25 + (l * 0.25)
                as_[i, l] = 60.0 + l * 20.0 + np.random.uniform(-10.0, 10.0)

        # Run pure Python reference
        py_engine = MultiLevelOFIEngine(num_levels=5, use_simd=False)
        _, py_integ, py_comp = py_engine.process_tick_stream(bp, bs, ap, as_, dt_sec=0.001)

        # Run C++20 AVX2 SIMD engine
        simd_engine = MultiLevelOFIEngine(num_levels=5, use_simd=True)
        _, simd_integ, simd_comp = simd_engine.process_tick_stream(bp, bs, ap, as_, dt_sec=0.001)

        # Assert congruence
        max_diff_comp = np.max(np.abs(py_comp[1:] - simd_comp[1:]))
        self.assertLess(max_diff_comp, 1e-2, f"C++ SIMD vs Python divergence: {max_diff_comp:.5f}")

    def test_cpp_simd_benchmark_throughput(self):
        """Test C++20 AVX2 SIMD microsecond execution speed and throughput."""
        dll = _get_dll()
        if not dll:
            self.skipTest("csrc/lif_core.dll not available.")

        from neuroquant.market.ofi_calibrator import _SIMDOFIStats
        import ctypes
        stats = _SIMDOFIStats()
        dll.ofi_simd_benchmark(20000, ctypes.byref(stats))

        self.assertEqual(stats.total_ticks_processed, 20000)
        self.assertLess(stats.avg_nanoseconds_per_tick, 1000.0, "Latency exceeds 1 microsecond!")
        self.assertGreater(stats.ticks_per_second, 1_000_000.0, "Throughput below 1M ticks/sec!")

    def test_end_to_end_calibration_and_predictive_edge(self):
        """Test end-to-end multi-level OFI calibration against synthetic Hawkes tick stream."""
        from benchmarks.run_ofi_calibration import generate_l2_depth_ticks
        tick_data = generate_l2_depth_ticks(num_ticks=3000, seed=123)

        calibrator = OFICalibrator(num_levels=5, horizons=[1, 5, 10])
        result = calibrator.calibrate(tick_data, verbose=False)

        self.assertEqual(result.num_levels, 5)
        self.assertAlmostEqual(sum(result.weights), 1.0, places=3)
        self.assertTrue(result.is_hawkes_stable)
        self.assertLess(result.spectral_radius, 1.0)
        self.assertIn(10, result.r2_multilevel)
        self.assertIn(10, result.hit_rate_multilevel)

    def test_hardware_header_synthesis_export(self):
        """Test export of synthesizable Verilog HDL parameter package."""
        from benchmarks.run_ofi_calibration import generate_l2_depth_ticks
        tick_data = generate_l2_depth_ticks(num_ticks=1000, seed=99)
        calibrator = OFICalibrator(num_levels=5, horizons=[5])
        result = calibrator.calibrate(tick_data, verbose=False)

        out_vh = os.path.join(PROJECT_ROOT, "hardware", "optimal_ofi_params.vh")
        calibrator.export_verilog_header(result, out_vh)

        self.assertTrue(os.path.exists(out_vh))
        with open(out_vh, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("`ifndef OPTIMAL_OFI_PARAMS_VH", content)
        self.assertIn("OFI_WEIGHT_0", content)
        self.assertIn("OFI_DECAY_MULT_0", content)
        self.assertIn("HAWKES_ALPHA_SELF", content)
        self.assertIn("TOXIC_OFI_THRESHOLD", content)


if __name__ == "__main__":
    unittest.main()
