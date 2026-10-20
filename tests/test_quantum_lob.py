"""
Unit Tests for Absolute Quantum Computation Engine (8-Qubit State Vector Circuit)
================================================================================
Author: Arunjyoti Sarma (Research Scholar, IIT (BHU), Varanasi)
"""

import unittest
import numpy as np
from neuroquant.quantum.quantum_lob_circuit import QuantumLOBCircuit, QuantumLOBConfig


class TestQuantumLOBCircuit(unittest.TestCase):

    def setUp(self):
        self.cfg = QuantumLOBConfig(num_qubits=8, hilbert_dim=256)
        self.qc = QuantumLOBCircuit(self.cfg)

    def test_state_initialization_norm(self):
        """Test initial ground state |00000000> normalization."""
        self.qc.reset()
        probs = self.qc.get_probabilities()
        self.assertEqual(len(probs), 256)
        self.assertAlmostEqual(probs[0], 1.0, places=6)
        self.assertAlmostEqual(np.sum(probs), 1.0, places=6)

    def test_hadamard_uniform_superposition(self):
        r"""Test that H^{\otimes 8} creates equal superposition |alpha_k|^2 = 1/256."""
        self.qc.reset()
        self.qc.apply_hadamard_all()
        probs = self.qc.get_probabilities()
        expected_prob = 1.0 / 256.0
        np.testing.assert_allclose(probs, np.full(256, expected_prob), atol=1e-5)

    def test_lob_feature_encoding_and_entanglement(self):
        """Test encoding L2 OFI into rotation angles and entangling across levels."""
        ofi = np.array([12.5, -8.0, 5.2, -3.1, 15.0, -10.2, 4.4, -2.0])
        vol = np.array([100.0, 120.0, 80.0, 95.0, 110.0, 105.0, 90.0, 85.0])
        self.qc.encode_lob_features(ofi, vol)

        probs = self.qc.get_probabilities()
        # Total probability must strictly equal 1.0
        self.assertAlmostEqual(float(np.sum(probs)), 1.0, places=6)

        # Entanglement entropy between Bid and Ask halves must be strictly positive
        entropy = self.qc.get_entanglement_entropy()
        self.assertGreater(entropy, 0.0)

    def test_bloch_sphere_vectors(self):
        """Test that Bloch vectors (u, v, w) satisfy ||r|| <= 1.0 for all 8 qubits."""
        ofi = np.array([10.0, -5.0, 8.0, -4.0, 6.0, -2.0, 3.0, -1.0])
        vol = np.array([50.0] * 8)
        self.qc.encode_lob_features(ofi, vol)

        bloch = self.qc.get_bloch_vectors()
        self.assertEqual(len(bloch), 8)

        for i, (u, v, w) in enumerate(bloch):
            norm = np.sqrt(u**2 + v**2 + w**2)
            # Mixed or pure state Bloch sphere radius must be <= 1.0001
            self.assertLessEqual(norm, 1.0001, f"Qubit {i} breached Bloch sphere! Norm = {norm}")

    def test_vqe_dark_pool_routing(self):
        """Test VQE multi-venue execution routing."""
        ofi = np.array([20.0, 15.0, 10.0, 5.0, -5.0, -10.0, -15.0, -20.0])
        vol = np.array([100.0] * 8)
        self.qc.encode_lob_features(ofi, vol)

        vqe = self.qc.solve_vqe_execution_routing(order_qty=5000.0)
        self.assertIn("optimal_basis_state", vqe)
        self.assertIn("ground_state_energy_hartree", vqe)
        self.assertIn("quantum_routing_advantage_pct", vqe)
        self.assertEqual(len(vqe["venues"]), 8)
        # Sum of shares allocated must equal order quantity
        total_allocated = sum(v["shares"] for v in vqe["venues"])
        self.assertAlmostEqual(total_allocated, 5000.0, delta=1.0)

    def test_quantum_amplitude_estimation_speedup(self):
        """Test Quantum Amplitude Estimation quadratic speedup calculation."""
        qae = self.qc.compute_quantum_amplitude_estimation_var(confidence=0.999)
        self.assertIn("quantum_computational_speedup", qae)
        self.assertIn("simulated_999_var_dollars", qae)
        self.assertIn("simulated_999_cvar_dollars", qae)
        self.assertGreater(qae["classical_monte_carlo_samples"], qae["quantum_amplitude_estimation_oracle_calls"])


if __name__ == "__main__":
    unittest.main()
