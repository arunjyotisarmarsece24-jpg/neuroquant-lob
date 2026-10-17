"""
Unit Tests: Neuromorphic Core & Plasticity Dynamics
===================================================
"""

import unittest
import numpy as np
from config import NeuromorphicConfig
from neuroquant.neuromorphic.lif_neuron import LIFPopulation
from neuroquant.neuromorphic.stdp import RewardModulatedSTDP
from neuroquant.neuromorphic.snn_network import DigitalNeuromorphicCore

class TestNeuromorphicCore(unittest.TestCase):
    def setUp(self):
        self.cfg = NeuromorphicConfig()

    def test_lif_subthreshold_decay(self):
        pop = LIFPopulation(size=4, config=self.cfg)
        pop.voltage[:] = -60.0  # Above rest (-70.0)
        # Advance with zero input current
        zero_current = np.zeros(4, dtype=np.float32)
        pop.step(zero_current)
        # Voltage should have decayed toward v_rest (-70.0)
        self.assertTrue(np.all(pop.voltage < -60.0))
        self.assertTrue(np.all(pop.voltage >= self.cfg.v_rest))

    def test_lif_spike_and_refractory(self):
        pop = LIFPopulation(size=2, config=self.cfg)
        # Inject massive suprathreshold current
        high_current = np.array([100.0, 0.0], dtype=np.float32)
        spikes = pop.step(high_current)
        
        # Neuron 0 should fire, Neuron 1 should not
        self.assertTrue(spikes[0])
        self.assertFalse(spikes[1])
        # Neuron 0 should reset to v_reset and enter refractory period
        self.assertEqual(pop.voltage[0], self.cfg.v_reset)
        self.assertGreater(pop.refractory_timer[0], 0)

    def test_r_stdp_adaptation(self):
        stdp = RewardModulatedSTDP(pre_size=4, post_size=2, config=self.cfg)
        initial_weight = float(stdp.weights[0, 0])
        
        # Causal sequence: Pre fires at t_0, Post fires at t_1 with positive financial reward
        pre_fire = np.array([True, False, False, False], dtype=np.bool_)
        no_fire_post = np.array([False, False], dtype=np.bool_)
        stdp.step(pre_fire, no_fire_post, reward=0.0)
        
        no_fire_pre = np.array([False, False, False, False], dtype=np.bool_)
        post_fire = np.array([True, False], dtype=np.bool_)
        stdp.step(no_fire_pre, post_fire, reward=5.0)
        
        # Synapse (0, 0) should have strengthened via LTP
        self.assertGreater(stdp.weights[0, 0], initial_weight)

    def test_rsnn_forward_pass(self):
        core = DigitalNeuromorphicCore(self.cfg)
        dummy_sensory = np.zeros(self.cfg.num_sensory_neurons, dtype=np.bool_)
        dummy_sensory[0] = True
        dummy_sensory[22] = True
        
        s, h, m = core.step(dummy_sensory, reward=0.0)
        self.assertEqual(len(s), self.cfg.num_sensory_neurons)
        self.assertEqual(len(h), self.cfg.num_hidden_neurons)
        self.assertEqual(len(m), self.cfg.num_motor_neurons)
        
        signals = core.get_motor_readout_signals()
        self.assertIn("skew", signals)
        self.assertIn("toxicity_prob", signals)

if __name__ == "__main__":
    unittest.main()
