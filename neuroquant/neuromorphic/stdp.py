"""
Reward-Modulated Spike-Timing-Dependent Plasticity (R-STDP)
===========================================================
Online synaptic plasticity algorithm. Replaces offline non-causal backpropagation
with biologically plausible local eligibility traces modulated by global financial
reward (realized PnL, spread capture, and adverse selection avoidance).
"""

import numpy as np
from config import NeuromorphicConfig

class RewardModulatedSTDP:
    """
    Implements online R-STDP between a pre-synaptic population and a post-synaptic population.
    
    Mathematical Formulation:
      dx_i/dt = -x_i / tau_pre  + S_pre_i(t)
      dy_j/dt = -y_j / tau_post + S_post_j(t)
      de_ij/dt = -e_ij / tau_e  + (x_i * S_post_j - y_j * S_pre_i)
      dW_ij/dt = eta * Reward(t) * e_ij - weight_decay * W_ij
    """
    def __init__(self, pre_size: int, post_size: int, config: NeuromorphicConfig):
        self.pre_size = pre_size
        self.post_size = post_size
        self.cfg = config
        
        self.dt = config.time_step_ms
        self.tau_pre = 20.0     # Pre-synaptic trace time constant (ms)
        self.tau_post = 20.0    # Post-synaptic trace time constant (ms)
        self.tau_e = config.tau_eligibility
        
        self.decay_pre = float(np.exp(-self.dt / self.tau_pre))
        self.decay_post = float(np.exp(-self.dt / self.tau_post))
        self.decay_e = float(np.exp(-self.dt / self.tau_e))
        
        # State variables
        self.pre_trace = np.zeros(pre_size, dtype=np.float32)
        self.post_trace = np.zeros(post_size, dtype=np.float32)
        self.eligibility = np.zeros((pre_size, post_size), dtype=np.float32)
        
        # Synaptic Weights (Initialized with zero-mean Gaussian)
        self.weights = np.random.normal(loc=0.0, scale=0.15, size=(pre_size, post_size)).astype(np.float32)
        
        # Plasticity Parameters
        self.a_plus = 1.0       # LTP magnitude
        self.a_minus = 1.05     # LTD magnitude (slightly asymmetric for stability)
        self.eta = config.learning_rate
        self.w_min = config.w_min
        self.w_max = config.w_max

    def step(self, pre_spikes: np.ndarray, post_spikes: np.ndarray, reward: float = 0.0) -> np.ndarray:
        """
        Advance plasticity state by one step dt and update weights based on reward.
        
        Parameters:
            pre_spikes: Boolean array of pre-synaptic spikes of shape (pre_size,)
            post_spikes: Boolean array of post-synaptic spikes of shape (post_size,)
            reward: Scalar financial reward signal (e.g. +1.0 for profitable quote fill, -2.0 for adverse selection)
            
        Returns:
            updated_weights: Reference to self.weights
        """
        # 1. Decay Eligibility Traces
        self.eligibility *= self.decay_e
        
        # 2. Accumulate STDP Pairings into Eligibility
        # LTP: Post fires after Pre (existing pre_trace combined with current post_spikes)
        ltp_outer = np.outer(self.pre_trace, post_spikes.astype(np.float32)) * self.a_plus
        
        # LTD: Pre fires after Post (current pre_spikes combined with existing post_trace)
        ltd_outer = np.outer(pre_spikes.astype(np.float32), self.post_trace) * self.a_minus
        
        self.eligibility += (ltp_outer - ltd_outer)
        
        # 3. Update Pre- and Post-Synaptic Traces for subsequent intervals
        self.pre_trace = self.pre_trace * self.decay_pre + pre_spikes.astype(np.float32)
        self.post_trace = self.post_trace * self.decay_post + post_spikes.astype(np.float32)
        
        # 4. Modulate Synaptic Weights via Global Reward
        # Lemma 3 (Compact Synaptic Projection Invariant):
        # Under any arbitrary reward shock R in (-inf, +inf) during flash crashes,
        # the reward is strictly bounded to [-R_max, +R_max], and weights are projected
        # via Pi_{[w_min, w_max]} into the compact invariant set.
        # Guarantees ||W[t]||_F <= sqrt(N_pre * N_post) * max(|w_min|, |w_max|) < inf for all t >= 0.
        if self.cfg.enable_r_stdp and reward != 0.0:
            r_max = getattr(self.cfg, "max_reward_magnitude", 10.0)
            clipped_reward = float(np.clip(reward, -r_max, r_max))
            delta_w = self.eta * clipped_reward * self.eligibility
            
            # Apply weight update with weight decay regularization
            self.weights += delta_w - (self.cfg.weight_decay * self.weights)
            
            # Strict projection operator Pi_{[w_min, w_max]}
            np.clip(self.weights, self.w_min, self.w_max, out=self.weights)
            
        return self.weights

    def get_frobenius_norm(self) -> float:
        """Returns the L2 Frobenius norm ||W||_F of the plastic synaptic weight matrix."""
        return float(np.linalg.norm(self.weights, 'fro'))

    def get_max_theoretical_norm(self) -> float:
        """Strict compact upper bound guaranteed by Lemma 3."""
        max_val = max(abs(self.w_min), abs(self.w_max))
        return float(np.sqrt(self.pre_size * self.post_size) * max_val)
