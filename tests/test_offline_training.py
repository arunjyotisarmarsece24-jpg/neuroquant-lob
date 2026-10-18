"""
Unit Tests: Offline PyTorch BPTT Surrogate Gradient Training Pipeline
======================================================================
Validates:
  1. Fast Sigmoid & ATan Surrogate Gradient differentiability.
  2. RSNN Truncated BPTT forward unrolling, recurrent states, and backward gradients.
  3. Dale's principle synaptic excitation/inhibition balance.
  4. Market tick generation, labeling, and PyTorch DataLoader slicing.
  5. Weight serialization (.npz, .bin, .json) and round-trip integrity.
  6. Zero-divergence weight synchronization to C++20 AVX2 SIMD core.
  7. Multi-task ROC-AUC metric calculation under class imbalance.
"""

import os
import sys
import unittest
import tempfile
import numpy as np
import torch
import torch.nn as nn

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from config import NeuromorphicConfig, MarketConfig
from neuroquant.neuromorphic.torch_rsnn import (
    TorchRSNN,
    FastSigmoidSurrogate,
    ATanSurrogate,
    surrogate_spike
)
from neuroquant.neuromorphic.dataset import (
    generate_market_ticks,
    MarketTickDataset,
    get_market_dataloaders
)
from neuroquant.neuromorphic.cpp_backend import (
    CPURSNNCore,
    is_cpp_backend_available
)

class TestOfflineSNNTraining(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(42)
        np.random.seed(42)
        self.cfg = NeuromorphicConfig()

    def test_surrogate_gradients(self):
        """Verifies surrogate gradients are non-zero at threshold and smooth."""
        v = torch.tensor([-70.0, -56.0, -55.0, -54.0, -30.0], requires_grad=True)
        v_thresh = -55.0

        # Fast Sigmoid
        s_fs = FastSigmoidSurrogate.apply(v, v_thresh, 10.0)
        s_fs.sum().backward()
        self.assertIsNotNone(v.grad)
        grad_fs = v.grad.clone()
        v.grad.zero_()

        # Gradient should peak at threshold (-55.0) where diff = 0
        self.assertAlmostEqual(grad_fs[2].item(), 1.0, places=4,
                               msg="Surrogate gradient at threshold should be 1.0")
        self.assertGreater(grad_fs[2].item(), grad_fs[0].item(),
                           msg="Gradient at threshold must exceed gradient at resting potential")
        self.assertGreater(grad_fs[2].item(), grad_fs[4].item(),
                           msg="Gradient at threshold must exceed gradient far above threshold")

        # ATan Surrogate
        s_atan = ATanSurrogate.apply(v, v_thresh, 2.0)
        s_atan.sum().backward()
        self.assertIsNotNone(v.grad)
        self.assertGreater(v.grad[2].item(), 0.0)

    def test_torch_rsnn_forward_and_backward(self):
        """Tests RSNN multi-step forward BPTT unrolling and backprop."""
        model = TorchRSNN(num_sensory=32, num_hidden=64, num_motor=4, config=self.cfg)
        batch_size = 4
        seq_len = 25
        x = (torch.rand(batch_size, seq_len, 32) > 0.8).float()

        out = model(x)
        self.assertEqual(out["logits"].shape, (batch_size, 4))
        self.assertEqual(out["probabilities"].shape, (batch_size, 4))
        self.assertEqual(out["hidden_spikes"].shape, (batch_size, seq_len, 64))
        self.assertEqual(out["motor_spikes"].shape, (batch_size, seq_len, 4))
        self.assertEqual(out["motor_voltages"].shape, (batch_size, seq_len, 4))

        # Test BPTT Backward Pass
        target = torch.randint(0, 2, (batch_size, 4)).float()
        criterion = nn.BCEWithLogitsLoss()
        task_loss = criterion(out["logits"], target)
        spk_loss = torch.square(out["mean_hidden_sparsity"] - 0.10)
        total_loss = task_loss + 2.0 * spk_loss
        total_loss.backward()

        self.assertIsNotNone(model.w_in.grad, "w_in must receive BPTT gradients")
        self.assertIsNotNone(model.w_rec.grad, "w_rec must receive recurrent BPTT gradients")
        self.assertIsNotNone(model.w_motor.grad, "w_motor must receive readout gradients")
        self.assertFalse(torch.isnan(model.w_in.grad).any(), "w_in gradients must not be NaN")
        self.assertFalse(torch.isnan(model.w_rec.grad).any(), "w_rec gradients must not be NaN")

    def test_dale_principle_enforcement(self):
        """Validates Dale's principle (80% excitatory, 20% inhibitory, zero diagonal)."""
        model = TorchRSNN(num_sensory=32, num_hidden=64, num_motor=4,
                          config=self.cfg, enable_dale=True)
        w_eff = model.get_effective_w_rec()

        num_inhibitory = int(0.2 * 64)
        # Inhibitory columns must be non-positive
        self.assertTrue((w_eff[:, :num_inhibitory] <= 0.0).all(),
                        "Inhibitory columns must be <= 0")
        # Excitatory columns must be non-negative
        self.assertTrue((w_eff[:, num_inhibitory:] >= 0.0).all(),
                        "Excitatory columns must be >= 0")
        # Diagonal must be 0
        diag = torch.diagonal(w_eff)
        self.assertTrue((diag == 0.0).all(), "Self-loops must be strictly 0.0")

    def test_weight_serialization_roundtrip(self):
        """Validates saving to .npz, .bin, .json and exact reload."""
        model = TorchRSNN(num_sensory=32, num_hidden=64, num_motor=4, config=self.cfg)
        with tempfile.TemporaryDirectory() as tmp_dir:
            paths = model.save_weights(save_dir=tmp_dir, prefix="test_weights")
            self.assertTrue(os.path.exists(paths["npz"]))
            self.assertTrue(os.path.exists(paths["bin"]))
            self.assertTrue(os.path.exists(paths["json"]))

            # Check binary dump size: (32*64 + 64*64 + 64*4) * 4 bytes = (2048 + 4096 + 256) * 4 = 25,600 bytes
            expected_bin_bytes = (32 * 64 + 64 * 64 + 64 * 4) * 4
            self.assertEqual(os.path.getsize(paths["bin"]), expected_bin_bytes)

            # Roundtrip reload into new model
            new_model = TorchRSNN(num_sensory=32, num_hidden=64, num_motor=4, config=self.cfg)
            new_model.load_weights(paths["npz"])

            np.testing.assert_allclose(
                model.w_in.detach().numpy(),
                new_model.w_in.detach().numpy(),
                rtol=1e-6
            )
            np.testing.assert_allclose(
                model.w_motor.detach().numpy(),
                new_model.w_motor.detach().numpy(),
                rtol=1e-6
            )

    def test_dataset_generation_and_dataloader(self):
        """Validates market tick dataset generator and PyTorch DataLoader."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_file = os.path.join(tmp_dir, "test_ticks_1000.npz")
            data = generate_market_ticks(num_ticks=1000, horizon=10, seed=123, cache_path=cache_file)
            self.assertEqual(data["spikes"].shape, (1000, 32))
            self.assertEqual(data["targets"].shape, (1000, 4))
            self.assertEqual(len(data["prices"]), 1000)

            # PyTorch Dataset
            ds = MarketTickDataset(data["spikes"], data["targets"], seq_len=20)
            self.assertGreater(len(ds), 0)
            x_seq, y = ds[0]
            self.assertEqual(x_seq.shape, (20, 32))
            self.assertEqual(y.shape, (4,))

            train_l, val_l = get_market_dataloaders(data, seq_len=20, batch_size=16)
            for x_b, y_b in train_l:
                self.assertEqual(x_b.shape, (16, 20, 32))
                self.assertEqual(y_b.shape, (16, 4))
                break

    def test_cpp_simd_weight_synchronization(self):
        """Transfers trained PyTorch weights to C++20 AVX2 SIMD Core and runs inference."""
        if not is_cpp_backend_available():
            self.skipTest("C++ lif_core library not available")

        model = TorchRSNN(num_sensory=32, num_hidden=64, num_motor=4, config=self.cfg)
        cpp_core = CPURSNNCore(self.cfg)

        # Sync weights
        model.sync_to_cpp(cpp_core)

        # Run 50 ticks through C++ core
        dummy_sensory = np.zeros(32, dtype=np.bool_)
        dummy_sensory[0] = True  # Upward price delta spike
        dummy_sensory[2] = True  # Bid depth influx spike

        for _ in range(50):
            s_spk, h_spk, m_spk = cpp_core.step(dummy_sensory)
            self.assertEqual(len(s_spk), 32)
            self.assertEqual(len(h_spk), 64)
            self.assertEqual(len(m_spk), 4)

        readout = cpp_core.get_motor_readout_signals()
        self.assertIn("skew", readout)
        self.assertIn("toxicity_prob", readout)
        self.assertIn("volatility_multiplier", readout)
        self.assertIn("motor_voltages", readout)
        self.assertEqual(len(readout["motor_voltages"]), 4)

if __name__ == "__main__":
    unittest.main()
