"""
Unit Tests for Lemma 3: Compact Synaptic Projection Invariant
=============================================================
Validates that under extreme Black-Swan flash-crash reward shocks R in (-inf, +inf),
the synaptic weight matrix remains strictly compact inside the L2 Frobenius ball:
    ||W[t]||_F <= sqrt(N_pre * N_post) * max(|w_min|, |w_max|) < inf
preventing catastrophic runaway divergence or vanishing weights.

Author: Arunjyoti Sarma (Research Scholar, IIT (BHU), Varanasi)
"""

import unittest
import numpy as np
from config import CONFIG_NEURO, NeuromorphicConfig
from neuroquant.neuromorphic.stdp import RewardModulatedSTDP


class TestLemma3SynapticInvariance(unittest.TestCase):

    def setUp(self):
        self.cfg = NeuromorphicConfig(
            w_min=-2.0,
            w_max=2.0,
            max_reward_magnitude=10.0,
            learning_rate=0.01
        )
        self.pre_size = 64
        self.post_size = 4
        self.stdp = RewardModulatedSTDP(self.pre_size, self.post_size, self.cfg)

    def test_compact_norm_bound_initial(self):
        """Initial weights must be well inside the theoretical Frobenius ball."""
        f_norm = self.stdp.get_frobenius_norm()
        max_bound = self.stdp.get_max_theoretical_norm()
        self.assertLess(f_norm, max_bound)
        self.assertEqual(max_bound, np.sqrt(64 * 4) * 2.0) # 16 * 2.0 = 32.0

    def test_extreme_flash_crash_reward_shock(self):
        """Simulate catastrophic -$1,000,000 reward shock over 1,000 steps."""
        max_bound = self.stdp.get_max_theoretical_norm()
        np.random.seed(42)

        for _ in range(1000):
            pre = np.random.rand(self.pre_size) > 0.8
            post = np.random.rand(self.post_size) > 0.8
            # Extreme negative shock
            self.stdp.step(pre, post, reward=-1_000_000.0)

            f_norm = self.stdp.get_frobenius_norm()
            self.assertLessEqual(f_norm, max_bound + 1e-6)
            self.assertTrue(np.all(self.stdp.weights >= self.cfg.w_min))
            self.assertTrue(np.all(self.stdp.weights <= self.cfg.w_max))
            self.assertFalse(np.any(np.isnan(self.stdp.weights)))
            self.assertFalse(np.any(np.isinf(self.stdp.weights)))

    def test_extreme_euphoric_runaway_reward_shock(self):
        """Simulate runaway +$1,000,000 positive rewards."""
        max_bound = self.stdp.get_max_theoretical_norm()
        np.random.seed(1337)

        for _ in range(1000):
            pre = np.random.rand(self.pre_size) > 0.7
            post = np.random.rand(self.post_size) > 0.7
            self.stdp.step(pre, post, reward=+1_000_000.0)

            f_norm = self.stdp.get_frobenius_norm()
            self.assertLessEqual(f_norm, max_bound + 1e-6)
            self.assertTrue(np.all(self.stdp.weights <= self.cfg.w_max))
            self.assertTrue(np.all(self.stdp.weights >= self.cfg.w_min))
            self.assertFalse(np.any(np.isnan(self.stdp.weights)))
            self.assertFalse(np.any(np.isinf(self.stdp.weights)))


if __name__ == "__main__":
    unittest.main()
