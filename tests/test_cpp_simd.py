"""
Unit Tests: C++20 AVX2 SIMD Neuromorphic Core & Hardware Timer
==============================================================
Validates:
  1. C++20 DLL dynamic loading and ABI symbols.
  2. RDTSCP hardware CPU cycle counter operation.
  3. Strict numerical equivalence between Python LIF Population and C++ AVX2 SIMD Core.
  4. Recurrent SNN SIMD Core forward propagation and motor readout dynamics.
"""

import os
import sys
import unittest
import ctypes
import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from config import NeuromorphicConfig
from neuroquant.neuromorphic.lif_neuron import LIFPopulation
from neuroquant.neuromorphic.cpp_backend import (
    is_cpp_backend_available,
    get_hardware_cycles,
    CPULIFPopulation,
    CPURSNNCore,
    run_cpp_lif_benchmark,
    run_cpp_rsnn_benchmark,
)

class TestCPPSIMDCore(unittest.TestCase):
    def setUp(self):
        self.cfg = NeuromorphicConfig()
        self.backend_available = is_cpp_backend_available()

    def test_cpp_backend_loaded(self):
        self.assertTrue(self.backend_available, "C++20 lif_core library must be built and loadable")

    def test_hardware_cycle_counter(self):
        if not self.backend_available:
            self.skipTest("C++ backend not available")
        c1 = get_hardware_cycles()
        self.assertGreater(c1, 0, "Hardware cycle counter must return positive 64-bit cycle count")
        # Run small dummy loop
        sum([i for i in range(1000)])
        c2 = get_hardware_cycles()
        self.assertGreater(c2, c1, "Hardware cycle counter must monotonically increase")

    def test_lif_subthreshold_decay_equivalence(self):
        if not self.backend_available:
            self.skipTest("C++ backend not available")

        num_neurons = 64
        py_pop = LIFPopulation(size=num_neurons, config=self.cfg)
        cpp_pop = CPULIFPopulation(size=num_neurons, config=self.cfg)

        initial_v = np.linspace(-68.0, -58.0, num_neurons, dtype=np.float32)
        py_pop.voltage = initial_v.copy()
        
        # Set C++ initial voltage via set_state
        cpp_pop.set_state(voltage=initial_v)

        # Advance 20 steps with zero current
        zero_current = np.zeros(num_neurons, dtype=np.float32)
        for _ in range(20):
            py_pop.step(zero_current)
            cpp_pop.step(zero_current)

        cpp_pop.sync_state_from_cpp()
        np.testing.assert_allclose(
            py_pop.voltage, 
            cpp_pop.voltage, 
            rtol=1e-4, 
            atol=1e-4, 
            err_msg="C++ SIMD exponential decay must match Python analytical decay"
        )

    def test_lif_spike_and_refractory_equivalence(self):
        if not self.backend_available:
            self.skipTest("C++ backend not available")

        num_neurons = 16
        py_pop = LIFPopulation(size=num_neurons, config=self.cfg)
        cpp_pop = CPULIFPopulation(size=num_neurons, config=self.cfg)

        # Alternating suprathreshold / subthreshold input
        current = np.zeros(num_neurons, dtype=np.float32)
        current[::2] = 120.0 # Even neurons fire
        current[1::2] = 0.0  # Odd neurons rest

        py_spikes = py_pop.step(current)
        cpp_spikes = cpp_pop.step(current)

        np.testing.assert_array_equal(
            py_spikes, cpp_spikes,
            "C++ AVX2 spike bitmask must fire for the exact same neurons as Python"
        )

        cpp_pop.sync_state_from_cpp()
        self.assertEqual(cpp_pop.voltage[0], self.cfg.v_reset)
        self.assertGreater(cpp_pop.refractory_timer[0], 0)
        self.assertEqual(cpp_pop.refractory_timer[1], 0)

    def test_rsnn_simd_core_forward(self):
        if not self.backend_available:
            self.skipTest("C++ backend not available")

        rsnn = CPURSNNCore(self.cfg)
        w_in = np.ones((self.cfg.num_sensory_neurons, self.cfg.num_hidden_neurons), dtype=np.float32) * 0.2
        w_rec = np.zeros((self.cfg.num_hidden_neurons, self.cfg.num_hidden_neurons), dtype=np.float32)
        w_motor = np.ones((self.cfg.num_hidden_neurons, self.cfg.num_motor_neurons), dtype=np.float32) * 0.15

        rsnn.set_weights(w_in, w_rec, w_motor)

        sensory_in = np.zeros(self.cfg.num_sensory_neurons, dtype=np.bool_)
        sensory_in[0] = True
        sensory_in[10] = True

        s, h, m = rsnn.step(sensory_in)
        self.assertEqual(len(s), self.cfg.num_sensory_neurons)
        self.assertEqual(len(h), self.cfg.num_hidden_neurons)
        self.assertEqual(len(m), self.cfg.num_motor_neurons)

        signals = rsnn.get_motor_readout_signals()
        self.assertIn("skew", signals)
        self.assertIn("toxicity_prob", signals)
        self.assertIn("volatility_multiplier", signals)

    def test_micro_benchmark_execution(self):
        if not self.backend_available:
            self.skipTest("C++ backend not available")

        lif_stats = run_cpp_lif_benchmark(num_neurons=64, iterations=5000)
        self.assertEqual(lif_stats["total_steps"], 5000)
        self.assertGreater(lif_stats["p50_cycles"], 0)
        self.assertLess(lif_stats["avg_nanoseconds"], 5000.0, "LIF step latency must be < 5us")

        rsnn_stats = run_cpp_rsnn_benchmark(iterations=5000)
        self.assertEqual(rsnn_stats["total_steps"], 5000)
        self.assertGreater(rsnn_stats["p50_cycles"], 0)
        self.assertLess(rsnn_stats["avg_nanoseconds"], 5000.0, "RSNN step latency must be < 5us")

if __name__ == "__main__":
    import ctypes
    unittest.main()
