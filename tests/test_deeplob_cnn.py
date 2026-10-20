"""
Unit Tests for DeepLOB Spatial-Temporal Convolutional Neural Network
===================================================================
Author: Arunjyoti Sarma (Research Scholar, IIT (BHU), Varanasi)
"""

import unittest
import torch
import numpy as np
from neuroquant.models.deeplob_cnn import DeepLOBCNN, DeepLOBConfig, DeepLOBEngine


class TestDeepLOBCNN(unittest.TestCase):

    def setUp(self):
        self.cfg = DeepLOBConfig(num_levels=10, seq_len=20, num_classes=3)
        self.model = DeepLOBCNN(self.cfg)

    def test_cnn_forward_shape(self):
        """Test forward pass output shape [B, 3] on synthetic LOB depth tensor."""
        batch_size = 4
        # Shape: [B, 1, T, 40]
        x = torch.randn(batch_size, 1, self.cfg.seq_len, 40)
        logits, fmaps = self.model(x, return_feature_maps=False)

        self.assertEqual(logits.shape, (batch_size, 3))
        self.assertIsNone(fmaps)

    def test_cnn_feature_map_extraction(self):
        """Test intermediate spatial-temporal feature map extraction."""
        x = torch.randn(2, 1, self.cfg.seq_len, 40)
        logits, fmaps = self.model(x, return_feature_maps=True)

        self.assertIsNotNone(fmaps)
        self.assertIn("spatial_pairs", fmaps)
        self.assertIn("level_imbalances", fmaps)
        self.assertIn("inception_features", fmaps)

        # Spatial level imbalances should have width 10 (one per LOB level)
        self.assertEqual(fmaps["level_imbalances"].shape[3], 10)

    def test_predict_probabilities_sum_to_one(self):
        """Test that predict_probabilities outputs valid probability distributions."""
        x = torch.randn(3, 1, self.cfg.seq_len, 40)
        probs = self.model.predict_probabilities(x)

        self.assertEqual(probs.shape, (3, 3))
        # Sum of probabilities across classes must be 1.0
        sums = np.sum(probs, axis=1)
        np.testing.assert_allclose(sums, np.ones(3), atol=1e-5)
        # All probabilities must be in [0, 1]
        self.assertTrue(np.all(probs >= 0.0))
        self.assertTrue(np.all(probs <= 1.0))

    def test_deeplob_engine_snapshot_inference(self):
        """Test live snapshot inference pipeline."""
        engine = DeepLOBEngine(self.cfg)
        mock_snapshot = {
            "mid_price": 18500.0,
            "bids": [[18500.0 - 0.25 * i, 10.0 + i] for i in range(10)],
            "asks": [[18500.25 + 0.25 * i, 10.0 + i] for i in range(10)]
        }
        res = engine.update_with_snapshot(mock_snapshot)

        self.assertIn("prediction", res)
        self.assertIn(res["prediction"], ["DOWN", "STATIONARY", "UP"])
        self.assertIn("probabilities", res)
        self.assertIn("alpha_signal", res)
        self.assertIn("spatial_imbalance_activations", res)
        self.assertEqual(len(res["spatial_imbalance_activations"]), 10)


if __name__ == "__main__":
    unittest.main()
