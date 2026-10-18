"""
PyTorch Recurrent Spiking Neural Network (RSNN) with Surrogate Gradient BPTT
=============================================================================
Differentiable Leaky Integrate-and-Fire (LIF) network with recurrent reservoir
dynamics, surrogate gradient backpropagation through time (BPTT), spiking
sparsity regularization, and zero-overhead weight export to the C++20 AVX2 SIMD core.
"""

import os
import json
import numpy as np
import torch
import torch.nn as nn
from typing import Tuple, Dict, Any, Optional
from config import NeuromorphicConfig, CONFIG_NEURO

class FastSigmoidSurrogate(torch.autograd.Function):
    """
    Fast Sigmoid Surrogate Gradient for non-differentiable Dirac-delta spike generation:
      Forward:  S = (V >= V_thresh).float()
      Backward: dS/dV = 1 / (1 + beta * |V - V_thresh|)^2
    """
    @staticmethod
    def forward(ctx, v: torch.Tensor, v_thresh: float = -55.0, beta: float = 10.0) -> torch.Tensor:
        ctx.save_for_backward(v)
        ctx.v_thresh = v_thresh
        ctx.beta = beta
        return (v >= v_thresh).float()

    @staticmethod
    def backward(ctx, grad_output: torch.Tensor) -> Tuple[torch.Tensor, None, None]:
        v, = ctx.saved_tensors
        beta = ctx.beta
        v_thresh = ctx.v_thresh
        diff = v - v_thresh
        surrogate_grad = 1.0 / (1.0 + beta * torch.abs(diff)) ** 2
        return grad_output * surrogate_grad, None, None

class ATanSurrogate(torch.autograd.Function):
    """
    Arc-Tangent Surrogate Gradient:
      Backward: dS/dV = 1 / (pi * (1 + (pi * (V - V_thresh))^2))
    """
    @staticmethod
    def forward(ctx, v: torch.Tensor, v_thresh: float = -55.0, alpha: float = 2.0) -> torch.Tensor:
        ctx.save_for_backward(v)
        ctx.v_thresh = v_thresh
        ctx.alpha = alpha
        return (v >= v_thresh).float()

    @staticmethod
    def backward(ctx, grad_output: torch.Tensor) -> Tuple[torch.Tensor, None, None]:
        v, = ctx.saved_tensors
        alpha = ctx.alpha
        v_thresh = ctx.v_thresh
        diff = v - v_thresh
        surrogate_grad = (alpha / 2.0) / (1.0 + (torch.pi / 2.0 * alpha * diff) ** 2)
        return grad_output * surrogate_grad, None, None

def surrogate_spike(v: torch.Tensor, v_thresh: float, surrogate_type: str = "fast_sigmoid", beta: float = 10.0) -> torch.Tensor:
    if surrogate_type == "atan":
        return ATanSurrogate.apply(v, v_thresh, beta)
    return FastSigmoidSurrogate.apply(v, v_thresh, beta)

class TorchRSNN(nn.Module):
    """
    Differentiable Recurrent Spiking Neural Network (RSNN) for BPTT Training.
    Architecture:
      - Sensory Inputs: 32 delta-modulated LOB channels
      - Hidden Reservoir: 64 recurrent LIF neurons (supports Dale's Principle)
      - Motor Readout: 4 LIF neurons [Upward Skew, Downward Skew, Toxicity, Volatility]
    
    Guarantees 100% parameter and architectural compatibility with C++20 RSNNCoreSIMD:
      - Input synaptic scaling: 12.0
      - Recurrent synaptic scaling: 8.0
      - Motor synaptic scaling: 15.0
      - Subthreshold exponential decay: exp(-dt / tau_m)
      - Absolute refractory clamping and hard voltage reset
    """
    def __init__(self,
                 num_sensory: int = 32,
                 num_hidden: int = 64,
                 num_motor: int = 4,
                 config: NeuromorphicConfig = CONFIG_NEURO,
                 surrogate_type: str = "fast_sigmoid",
                 surrogate_beta: float = 10.0,
                 enable_dale: bool = False):
        super().__init__()
        self.num_sensory = num_sensory
        self.num_hidden = num_hidden
        self.num_motor = num_motor
        self.cfg = config
        self.surrogate_type = surrogate_type
        self.surrogate_beta = surrogate_beta
        self.enable_dale = enable_dale

        # Membrane Dynamics Constants
        self.dt = config.time_step_ms
        self.tau_m = config.tau_m
        self.decay = float(np.exp(-self.dt / self.tau_m))
        self.v_rest = config.v_rest
        self.v_reset = config.v_reset
        self.v_thresh = config.v_thresh
        self.refractory_steps = int(config.refractory_period_ms / self.dt)

        # Constant scaling factors strictly matching C++20 RSNNCoreSIMD
        self.scale_in = 12.0
        self.scale_rec = 8.0
        self.scale_motor = 15.0
        self.scale_sensory_drive = 25.0

        # Synaptic Weights
        # W_in: [num_sensory, num_hidden]
        self.w_in = nn.Parameter(torch.empty(num_sensory, num_hidden))
        # W_rec: [num_hidden, num_hidden]
        self.w_rec = nn.Parameter(torch.empty(num_hidden, num_hidden))
        # W_motor: [num_hidden, num_motor]
        self.w_motor = nn.Parameter(torch.empty(num_hidden, num_motor))

        # Learnable readout temperature / scale for motor membrane potentials
        self.readout_scale = nn.Parameter(torch.ones(num_motor) * 1.5)
        self.readout_bias = nn.Parameter(torch.zeros(num_motor))

        # Dale's principle mask: 20% inhibitory (-1), 80% excitatory (+1), diagonal 0
        if self.enable_dale:
            num_inhibitory = int(0.2 * num_hidden)
            dale_mask = torch.ones(num_hidden, num_hidden)
            dale_mask[:, :num_inhibitory] = -1.0
            dale_mask.fill_diagonal_(0.0)
            self.register_buffer("dale_mask", dale_mask)
        else:
            self.register_buffer("dale_mask", None)

        self.reset_parameters()

    def reset_parameters(self):
        """Kaiming / He normal initialization tailored for spiking dynamics."""
        nn.init.normal_(self.w_in, mean=0.08, std=0.04)
        nn.init.normal_(self.w_rec, mean=0.0, std=0.04)
        with torch.no_grad():
            self.w_rec.fill_diagonal_(0.0)
            if self.dale_mask is not None:
                # Align initial signs with Dale's mask
                num_inhibitory = int(0.2 * self.num_hidden)
                self.w_rec[:, :num_inhibitory] = -torch.abs(self.w_rec[:, :num_inhibitory])
                self.w_rec[:, num_inhibitory:] = torch.abs(self.w_rec[:, num_inhibitory:])
        nn.init.normal_(self.w_motor, mean=0.08, std=0.04)

    def get_effective_w_rec(self) -> torch.Tensor:
        """Applies Dale's principle mask and removes self-loops if enabled."""
        if self.dale_mask is not None:
            w = torch.abs(self.w_rec) * self.dale_mask
            return w
        # Otherwise ensure zero diagonal
        mask = torch.ones_like(self.w_rec)
        mask.fill_diagonal_(0.0)
        return self.w_rec * mask

    def forward_step(self,
                     x_sensory_spikes: torch.Tensor,
                     v_hidden: torch.Tensor,
                     s_hidden: torch.Tensor,
                     v_motor: torch.Tensor,
                     s_motor: torch.Tensor,
                     refr_hidden: Optional[torch.Tensor] = None,
                     refr_motor: Optional[torch.Tensor] = None
                    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Advance RSNN by one discrete time-step dt with exact refractory clamping.
        
        Parameters:
            x_sensory_spikes: [B, num_sensory] binary spike float tensor
            v_hidden: [B, num_hidden] previous hidden membrane potential
            s_hidden: [B, num_hidden] previous hidden spike vector
            v_motor: [B, num_motor] previous motor membrane potential
            s_motor: [B, num_motor] previous motor spike vector
            refr_hidden: [B, num_hidden] remaining hidden refractory steps
            refr_motor: [B, num_motor] remaining motor refractory steps
            
        Returns:
            v_hidden_new, s_hidden_new, v_motor_new, s_motor_new, refr_hidden_new, refr_motor_new
        """
        if refr_hidden is None:
            refr_hidden = torch.zeros_like(v_hidden)
        if refr_motor is None:
            refr_motor = torch.zeros_like(v_motor)

        w_rec_eff = self.get_effective_w_rec()

        # 1. Sensory to Hidden Current
        # In C++: I_hidden = 12.0 * (S_sensory @ W_in) + 8.0 * (S_hidden_prev @ W_rec)
        i_from_sensory = torch.matmul(x_sensory_spikes, self.w_in) * self.scale_in
        i_from_rec = torch.matmul(s_hidden, w_rec_eff) * self.scale_rec
        i_hidden = i_from_sensory + i_from_rec

        # 2. Hidden LIF Integration with Exact Refractory Clamping
        is_refr_h = refr_hidden > 0
        refr_h_dec = torch.clamp(refr_hidden - 1, min=0)
        v_h_int = v_hidden * self.decay + self.v_rest * (1.0 - self.decay) + i_hidden
        v_h_sub = torch.where(is_refr_h, torch.full_like(v_h_int, self.v_reset), v_h_int)

        s_h_raw = surrogate_spike(v_h_sub, self.v_thresh, self.surrogate_type, self.surrogate_beta)
        s_h_new = s_h_raw * (~is_refr_h).float()

        v_h_new = torch.where(s_h_new.bool(), torch.full_like(v_h_sub, self.v_reset), v_h_sub)
        refr_h_new = torch.where(s_h_new.bool(), torch.full_like(refr_h_dec, self.refractory_steps), refr_h_dec)

        # 3. Motor Layer Current
        # In C++: I_motor = 15.0 * (S_hidden @ W_motor)
        i_motor = torch.matmul(s_h_new, self.w_motor) * self.scale_motor

        # 4. Motor LIF Integration with Exact Refractory Clamping
        is_refr_m = refr_motor > 0
        refr_m_dec = torch.clamp(refr_motor - 1, min=0)
        v_m_int = v_motor * self.decay + self.v_rest * (1.0 - self.decay) + i_motor
        v_m_sub = torch.where(is_refr_m, torch.full_like(v_m_int, self.v_reset), v_m_int)

        s_m_raw = surrogate_spike(v_m_sub, self.v_thresh, self.surrogate_type, self.surrogate_beta)
        s_m_new = s_m_raw * (~is_refr_m).float()

        v_m_new = torch.where(s_m_new.bool(), torch.full_like(v_m_sub, self.v_reset), v_m_sub)
        refr_m_new = torch.where(s_m_new.bool(), torch.full_like(refr_m_dec, self.refractory_steps), refr_m_dec)

        return v_h_new, s_h_new, v_m_new, s_m_new, refr_h_new, refr_m_new

    def forward(self,
                x_seq: torch.Tensor,
                init_state: Optional[Tuple] = None
               ) -> Dict[str, Any]:
        """
        Execute Truncated BPTT forward sequence over T ticks.
        
        Parameters:
            x_seq: [Batch, T, num_sensory] FloatTensor of sensory spikes
            init_state: Optional initial (v_h, s_h, v_m, s_m, refr_h, refr_m) for TBPTT state chaining
            
        Returns:
            Dict containing:
              - 'logits': [Batch, num_motor] continuous logit readout for BCE loss
              - 'probabilities': [Batch, num_motor] sigmoid probabilities in [0, 1]
              - 'hidden_spikes': [Batch, T, num_hidden] full hidden spike raster
              - 'motor_spikes': [Batch, T, num_motor] full motor spike raster
              - 'motor_voltages': [Batch, T, num_motor] motor voltage traces
              - 'final_state': tuple for next TBPTT window
              - 'mean_hidden_sparsity': scalar mean firing rate of reservoir
        """
        batch_size, seq_len, _ = x_seq.shape
        device = x_seq.device

        # Initialize membrane potentials and spike histories
        if init_state is not None:
            if len(init_state) == 6:
                v_h, s_h, v_m, s_m, refr_h, refr_m = init_state
            else:
                v_h, s_h, v_m, s_m = init_state
                refr_h = torch.zeros((batch_size, self.num_hidden), device=device)
                refr_m = torch.zeros((batch_size, self.num_motor), device=device)
        else:
            v_h = torch.full((batch_size, self.num_hidden), self.v_rest, device=device)
            s_h = torch.zeros((batch_size, self.num_hidden), device=device)
            v_m = torch.full((batch_size, self.num_motor), self.v_rest, device=device)
            s_m = torch.zeros((batch_size, self.num_motor), device=device)
            refr_h = torch.zeros((batch_size, self.num_hidden), device=device)
            refr_m = torch.zeros((batch_size, self.num_motor), device=device)

        hidden_spikes_list = []
        motor_spikes_list = []
        motor_voltages_list = []

        # Recurrent BPTT loop across time steps
        for t in range(seq_len):
            x_t = x_seq[:, t, :]
            v_h, s_h, v_m, s_m, refr_h, refr_m = self.forward_step(
                x_t, v_h, s_h, v_m, s_m, refr_h, refr_m
            )
            hidden_spikes_list.append(s_h)
            motor_spikes_list.append(s_m)
            motor_voltages_list.append(v_m)

        # Stack temporal traces: [Batch, T, Neurons]
        all_hidden_spikes = torch.stack(hidden_spikes_list, dim=1)
        all_motor_spikes = torch.stack(motor_spikes_list, dim=1)
        all_motor_voltages = torch.stack(motor_voltages_list, dim=1)

        # Compute Motor Readout Logits:
        # Recency-weighted temporal aggregation emphasizing recent motor state dynamics
        temporal_weights = torch.linspace(0.2, 1.8, seq_len, device=device).view(1, seq_len, 1)
        norm_v = (all_motor_voltages - self.v_rest) / (self.v_thresh - self.v_rest + 1e-5) - 1.0
        weighted_v = torch.sum(norm_v * temporal_weights, dim=1) / float(seq_len)
        weighted_spikes = torch.sum(all_motor_spikes * temporal_weights, dim=1) / float(seq_len)

        # Final readout logit
        raw_readout = weighted_v + (weighted_spikes * 3.0)
        logits = raw_readout * self.readout_scale + self.readout_bias
        probabilities = torch.sigmoid(logits)

        # Reservoir Spiking Sparsity (fraction of active spikes per neuron per tick)
        mean_hidden_sparsity = torch.mean(all_hidden_spikes)

        return {
            "logits": logits,
            "probabilities": probabilities,
            "hidden_spikes": all_hidden_spikes,
            "motor_spikes": all_motor_spikes,
            "motor_voltages": all_motor_voltages,
            "final_state": (v_h.detach(), s_h.detach(), v_m.detach(), s_m.detach(), refr_h.detach(), refr_m.detach()),
            "mean_hidden_sparsity": mean_hidden_sparsity
        }

    # =========================================================================
    # Synaptic Weight Export & Synchronization with C++20 AVX2 SIMD Core
    # =========================================================================
    def export_weights(self) -> Dict[str, np.ndarray]:
        """
        Exports synaptic matrices as contiguous float32 NumPy arrays
        strictly formatted for C++20 RSNNCoreSIMD:
          - w_in: [32, 64] row-major
          - w_rec: [64, 64] row-major
          - w_motor: [64, 4] row-major
        """
        w_rec_eff = self.get_effective_w_rec()
        return {
            "w_in": self.w_in.detach().cpu().numpy().astype(np.float32),
            "w_rec": w_rec_eff.detach().cpu().numpy().astype(np.float32),
            "w_motor": self.w_motor.detach().cpu().numpy().astype(np.float32),
            "readout_scale": self.readout_scale.detach().cpu().numpy().astype(np.float32),
            "readout_bias": self.readout_bias.detach().cpu().numpy().astype(np.float32),
        }

    def save_weights(self, save_dir: str = "weights", prefix: str = "rsnn_trained") -> Dict[str, str]:
        """
        Serializes trained weights to multiple institutional formats:
          1. .npz: Complete NumPy bundle with metadata
          2. .bin: Direct zero-copy binary C-array layout for mmap / C++ loading
          3. .json: High-level architectural config and weight statistics
        """
        os.makedirs(save_dir, exist_ok=True)
        weights = self.export_weights()

        # 1. NumPy Compressed Archive
        npz_path = os.path.join(save_dir, f"{prefix}.npz")
        np.savez_compressed(
            npz_path,
            w_in=weights["w_in"],
            w_rec=weights["w_rec"],
            w_motor=weights["w_motor"],
            readout_scale=weights["readout_scale"],
            readout_bias=weights["readout_bias"],
            num_sensory=self.num_sensory,
            num_hidden=self.num_hidden,
            num_motor=self.num_motor,
            decay=self.decay,
            v_rest=self.v_rest,
            v_reset=self.v_reset,
            v_thresh=self.v_thresh
        )

        # 2. Raw Binary Dump (w_in, w_rec, w_motor in continuous sequence)
        bin_path = os.path.join(save_dir, f"{prefix}.bin")
        with open(bin_path, "wb") as f:
            f.write(weights["w_in"].tobytes())
            f.write(weights["w_rec"].tobytes())
            f.write(weights["w_motor"].tobytes())

        # 3. JSON Metadata & Weight Norm Diagnostics
        json_path = os.path.join(save_dir, f"{prefix}.json")
        meta = {
            "num_sensory": self.num_sensory,
            "num_hidden": self.num_hidden,
            "num_motor": self.num_motor,
            "dt_ms": self.dt,
            "tau_m_ms": self.tau_m,
            "decay": self.decay,
            "v_rest": self.v_rest,
            "v_reset": self.v_reset,
            "v_thresh": self.v_thresh,
            "w_in_l2_norm": float(np.linalg.norm(weights["w_in"])),
            "w_rec_l2_norm": float(np.linalg.norm(weights["w_rec"])),
            "w_motor_l2_norm": float(np.linalg.norm(weights["w_motor"])),
            "readout_scale": weights["readout_scale"].tolist(),
            "readout_bias": weights["readout_bias"].tolist(),
        }
        with open(json_path, "w") as f:
            json.dump(meta, f, indent=2)

        return {"npz": npz_path, "bin": bin_path, "json": json_path}

    def load_weights(self, npz_path: str):
        """Loads weights from a saved .npz archive."""
        data = np.load(npz_path)
        with torch.no_grad():
            self.w_in.copy_(torch.from_numpy(data["w_in"]))
            self.w_rec.copy_(torch.from_numpy(data["w_rec"]))
            self.w_motor.copy_(torch.from_numpy(data["w_motor"]))
            if "readout_scale" in data:
                self.readout_scale.copy_(torch.from_numpy(data["readout_scale"]))
            if "readout_bias" in data:
                self.readout_bias.copy_(torch.from_numpy(data["readout_bias"]))

    def sync_to_cpp(self, cpp_rsnn_core) -> None:
        """Transfers trained weights directly into the C++20 SIMD RSNN core."""
        weights = self.export_weights()
        cpp_rsnn_core.set_weights(weights["w_in"], weights["w_rec"], weights["w_motor"])
