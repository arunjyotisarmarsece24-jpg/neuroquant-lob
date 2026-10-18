"""
Recurrent Spiking Neural Network (RSNN) Architecture
=====================================================
Multi-population neuromorphic network combining sensory inputs, recurrent hidden
reservoir dynamics with Dale's principle (80% excitatory, 20% inhibitory), and
action readout motor neurons. Supports both live digital simulation and PyTorch
surrogate gradient training.
"""

import numpy as np
import torch
import torch.nn as nn
from typing import Tuple, Dict, Any, List
from config import NeuromorphicConfig
from .lif_neuron import LIFPopulation
from .stdp import RewardModulatedSTDP

class SurrogateHeaviside(torch.autograd.Function):
    """
    Differentiable surrogate gradient for Dirac-delta / Heaviside step function.
    Uses Fast Sigmoid approximation: S'(v) = 1 / (1 + beta * |v|)^2
    """
    @staticmethod
    def forward(ctx, v, v_thresh, beta=10.0):
        ctx.save_for_backward(v, v_thresh)
        ctx.beta = beta
        return (v >= v_thresh).float()

    @staticmethod
    def backward(ctx, grad_output):
        v, v_thresh = ctx.saved_tensors
        beta = ctx.beta
        diff = v - v_thresh
        surrogate_grad = 1.0 / (1.0 + beta * torch.abs(diff)) ** 2
        return grad_output * surrogate_grad, None, None

class DigitalNeuromorphicCore:
    """
    High-speed, fully digital software simulation of an RSNN.
    Operates strictly with vectorized NumPy operations for low latency and zero heap reallocation.
    """
    def __init__(self, config: NeuromorphicConfig):
        self.cfg = config
        
        # 1. Neural Populations
        self.sensory = LIFPopulation(config.num_sensory_neurons, config, name="Sensory")
        self.hidden = LIFPopulation(config.num_hidden_neurons, config, name="Hidden")
        self.motor = LIFPopulation(config.num_motor_neurons, config, name="Motor")
        
        # 2. Synaptic Weight Matrices
        # Input -> Hidden (Feedforward)
        self.w_in_hidden = np.random.normal(loc=0.3, scale=0.1, size=(config.num_sensory_neurons, config.num_hidden_neurons)).astype(np.float32)
        
        # Hidden -> Hidden (Recurrent Reservoir with Excitatory/Inhibitory Balance)
        w_rec = np.random.normal(loc=0.0, scale=0.15, size=(config.num_hidden_neurons, config.num_hidden_neurons)).astype(np.float32)
        # Dale's principle: 20% inhibitory neurons (negative weights)
        num_inhibitory = int(0.2 * config.num_hidden_neurons)
        w_rec[:, :num_inhibitory] = -np.abs(w_rec[:, :num_inhibitory])
        w_rec[:, num_inhibitory:] = np.abs(w_rec[:, num_inhibitory:])
        np.fill_diagonal(w_rec, 0.0)  # No immediate self-loops
        self.w_hidden_hidden = w_rec
        
        # Hidden -> Motor (Plastic synapses governed by R-STDP)
        self.plasticity_motor = RewardModulatedSTDP(config.num_hidden_neurons, config.num_motor_neurons, config)
        
        # Activity History for Visualization
        self.spike_raster = {
            "sensory": [],
            "hidden": [],
            "motor": []
        }
        self.max_raster_length = 150

    def set_weights(self, w_in: np.ndarray, w_rec: np.ndarray, w_motor: np.ndarray):
        """Directly sets synaptic weight matrices."""
        self.w_in_hidden = np.ascontiguousarray(w_in, dtype=np.float32)
        self.w_hidden_hidden = np.ascontiguousarray(w_rec, dtype=np.float32)
        self.plasticity_motor.weights = np.ascontiguousarray(w_motor, dtype=np.float32)

    def load_weights(self, npz_path: str):
        """Loads offline BPTT-trained weights from a serialized .npz archive."""
        data = np.load(npz_path)
        self.set_weights(data["w_in"], data["w_rec"], data["w_motor"])

    def step(self, sensory_spikes: np.ndarray, reward: float = 0.0) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Execute one discrete neuromorphic time-step.
        
        Parameters:
            sensory_spikes: Boolean array from spike encoder of shape (num_sensory,)
            reward: Financial feedback reward scalar from trading engine
            
        Returns:
            Tuple of (sensory_spikes, hidden_spikes, motor_spikes)
        """
        # 1. Sensory Population accepts spikes as incoming drive
        sensory_current = sensory_spikes.astype(np.float32) * 25.0
        s_spikes = self.sensory.step(sensory_current)
        
        # 2. Hidden Recurrent Population computes input current
        # I_hidden = (S_sensory @ W_in) + (S_hidden_prev @ W_rec)
        current_from_sensory = np.dot(s_spikes.astype(np.float32), self.w_in_hidden)
        current_from_recurrent = np.dot(self.hidden.spikes.astype(np.float32), self.w_hidden_hidden)
        hidden_current = (current_from_sensory * 12.0) + (current_from_recurrent * 8.0)
        
        h_spikes = self.hidden.step(hidden_current)
        
        # 3. Motor / Readout Population receives current from hidden layer
        # Synapses are plastic and update based on reward
        w_motor = self.plasticity_motor.step(self.hidden.spikes, self.motor.spikes, reward=reward)
        motor_current = np.dot(h_spikes.astype(np.float32), w_motor) * 15.0
        
        m_spikes = self.motor.step(motor_current)
        
        # 4. Record Raster Plot Activity
        for key, spikes in zip(["sensory", "hidden", "motor"], [s_spikes, h_spikes, m_spikes]):
            if len(self.spike_raster[key]) >= self.max_raster_length:
                self.spike_raster[key].pop(0)
            self.spike_raster[key].append(np.where(spikes)[0].tolist())
            
        return s_spikes, h_spikes, m_spikes

    def get_motor_readout_signals(self) -> Dict[str, float]:
        """
        Converts motor population firing rates / membrane potentials into actionable trading signals.
        Channels:
          [0]: Long Quote Skew (urgency to buy)
          [1]: Short Quote Skew (urgency to sell)
          [2]: Toxicity / Adverse Selection Warning
          [3]: Volatility Regime Spike
        """
        v_motor = self.motor.voltage
        v_thresh = self.motor.threshold
        
        # Normalized membrane activation above resting potential
        activation = np.clip((v_motor - self.motor.v_rest) / (v_thresh - self.motor.v_rest + 1e-5), 0.0, 1.5)
        
        skew = float(activation[0] - activation[1])  # Positive = skew toward bid (buy), Negative = skew toward ask (sell)
        toxicity_prob = float(np.clip(activation[2], 0.0, 1.0))
        volatility_pulse = float(activation[3])
        
        return {
            "skew": skew,
            "toxicity_prob": toxicity_prob,
            "volatility_pulse": volatility_pulse,
            "raw_activation": activation.tolist()
        }
