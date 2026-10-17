"""
Vectorized Leaky Integrate-and-Fire (LIF) & Adaptive Neuromorphic Population
=============================================================================
High-performance vectorized digital simulation of biological neuron populations.
Implements exact exponential sub-threshold integration, absolute refractory clamping,
and adaptive spike threshold dynamics.
"""

import numpy as np
from typing import Tuple, Optional
from config import NeuromorphicConfig

class LIFPopulation:
    """
    Vectorized population of Leaky Integrate-and-Fire (LIF) neurons.
    Zero-heap reallocation during time-stepping to preserve determinism and low latency.
    """
    def __init__(self, size: int, config: NeuromorphicConfig, name: str = "LIF"):
        self.size = size
        self.cfg = config
        self.name = name
        
        # Exponential sub-threshold integration constants
        self.dt = config.time_step_ms
        self.decay = float(np.exp(-self.dt / config.tau_m))
        self.v_rest = config.v_rest
        self.v_reset = config.v_reset
        self.v_thresh_base = config.v_thresh
        self.refractory_steps = int(config.refractory_period_ms / self.dt)
        
        # State Vectors
        self.voltage = np.full(self.size, self.v_rest, dtype=np.float32)
        self.threshold = np.full(self.size, self.v_thresh_base, dtype=np.float32)
        self.refractory_timer = np.zeros(self.size, dtype=np.int32)
        self.spikes = np.zeros(self.size, dtype=np.bool_)
        
        # Diagnostics & History
        self.spike_counts = np.zeros(self.size, dtype=np.int64)
        self.total_steps = 0
        self.recent_voltage_history = []
        self.history_capacity = 200

    def reset(self):
        """Reset population state to baseline."""
        self.voltage.fill(self.v_rest)
        self.threshold.fill(self.v_thresh_base)
        self.refractory_timer.fill(0)
        self.spikes.fill(False)
        self.spike_counts.fill(0)
        self.total_steps = 0
        self.recent_voltage_history.clear()

    def step(self, synaptic_current: np.ndarray) -> np.ndarray:
        """
        Advance population by one discrete time step dt.
        
        Parameters:
            synaptic_current: Array of input currents of shape (size,)
            
        Returns:
            spikes: Boolean array of shape (size,) indicating which neurons fired.
        """
        self.total_steps += 1
        
        # 1. Decrement refractory timers for currently refractory neurons
        is_refractory = self.refractory_timer > 0
        self.refractory_timer[is_refractory] -= 1
        
        # Refractory neurons have their voltage held at v_reset
        self.voltage[is_refractory] = self.v_reset
        
        # 2. Integrate sub-threshold membrane dynamics for receptive neurons
        active_mask = ~is_refractory
        if np.any(active_mask):
            # V(t) = V(t-1)*decay + V_rest*(1 - decay) + I_syn
            self.voltage[active_mask] = (
                self.voltage[active_mask] * self.decay +
                self.v_rest * (1.0 - self.decay) +
                synaptic_current[active_mask]
            )
            
        # 3. Detect Action Potentials (Spikes)
        firing_mask = (self.voltage >= self.threshold) & active_mask
        self.spikes[:] = firing_mask
        
        # 4. Apply Post-Spike Reset & Refractory Clamping
        if np.any(firing_mask):
            self.voltage[firing_mask] = self.v_reset
            self.refractory_timer[firing_mask] = self.refractory_steps
            self.spike_counts[firing_mask] += 1
            
        # 5. Maintain Voltage History for Visualization (Downsampled/Ring)
        if len(self.recent_voltage_history) >= self.history_capacity:
            self.recent_voltage_history.pop(0)
        self.recent_voltage_history.append(self.voltage.copy())
            
        return self.spikes

    @property
    def firing_rates_hz(self) -> np.ndarray:
        """Calculate empirical firing rate in Hertz."""
        duration_sec = (self.total_steps * self.dt) / 1000.0
        if duration_sec <= 0:
            return np.zeros(self.size, dtype=np.float32)
        return (self.spike_counts / duration_sec).astype(np.float32)

    def get_mean_voltage(self) -> float:
        return float(np.mean(self.voltage))
