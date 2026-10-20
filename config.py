"""
NeuroQuant-LOB: Configuration & Hyperparameters
================================================
Centralized configuration defining physical neuromorphic neuron dynamics,
LOB microstructure constants, and simulation execution boundaries.
"""

from dataclasses import dataclass

@dataclass
class NeuromorphicConfig:
    # Neuron Dynamics (Leaky Integrate-and-Fire)
    # Day 1 Pareto-Frontier Hardened Champion: tau_m = 25.0 ms, v_thresh = -50.0 mV, learning_rate = 0.0010
    tau_m: float = 20.0             # Membrane time constant (milliseconds) [Pareto Optimal: 25.0 ms]
    v_rest: float = -70.0           # Resting membrane potential (mV)
    v_reset: float = -75.0          # Hyperpolarization reset potential (mV)
    v_thresh: float = -55.0         # Firing action potential threshold (mV) [Pareto Optimal: -50.0 mV]
    refractory_period_ms: float = 2.0  # Absolute refractory duration (ms)
    time_step_ms: float = 0.5       # Simulation integration step dt (ms)
    
    # Network Topology
    num_sensory_neurons: int = 32   # Input encoding channels (price deltas, depth deltas, OFI, inter-arrival)
    num_hidden_neurons: int = 64    # Recurrent spiking reservoir
    num_motor_neurons: int = 4      # Readout channels: [Quote Skew (+), Quote Skew (-), Toxicity Alert, Volatility Burst]
    
    # Plasticity & Learning (R-STDP)
    enable_r_stdp: bool = True
    learning_rate: float = 0.005
    tau_eligibility: float = 40.0   # Eligibility trace decay constant (ms)
    weight_decay: float = 0.0001
    w_min: float = -2.0
    w_max: float = 2.0
    max_reward_magnitude: float = 10.0 # Strict bound for Lemma 3 compact projection

@dataclass
class MarketConfig:
    symbol: str = "NQ-NEURO"
    initial_mid_price: float = 18500.00
    tick_size: float = 0.25
    book_depth_levels: int = 10     # L2 book depth tracked per side
    hawkes_baseline_lambda: float = 80.0  # Base event arrival rate (events/sec)
    hawkes_alpha: float = 0.6       # Self-excitation coefficient
    hawkes_beta: float = 1.2        # Excitation decay rate
    toxic_order_ratio: float = 0.15 # Probability of informed/toxic institutional sweeping order
    
    # Microstructure Spike Encoding Thresholds
    delta_price_threshold: float = 0.25   # Min price shift to fire directional sensory spike
    delta_volume_threshold: float = 15.0  # Min volume shift at level to trigger spike
    burst_interarrival_cutoff_ms: float = 1.5 # Inter-arrival time below which burst neuron fires

@dataclass
class ExecutionConfig:
    initial_capital: float = 1_000_000.00
    max_inventory: int = 50         # Max contracts / shares held
    inventory_risk_aversion: float = 0.01 # Avellaneda-Stoikov gamma parameter
    order_size: int = 1
    latency_penalty_ms: float = 0.5 # Simulated colocation wire-to-decision latency
    maker_fee_bps: float = -0.002   # Negative fee = maker rebate (-0.002% = -0.2 bps)
    taker_fee_bps: float = 0.005    # Taker fee (+0.005% = +0.5 bps)
    maker_rebate_pct: float = -0.00002 # Exact decimal rate (-0.002%)
    taker_fee_pct: float = 0.00005     # Exact decimal rate (+0.005%)
    permanent_impact_gamma: float = 2.5e-7
    temporary_impact_eta: float = 5.0e-5
    impact_power: float = 0.5       # Non-linear square-root market impact law

@dataclass
class AlmgrenChrissExecutionConfig:
    total_shares: float = 10_000.0
    time_horizon_sec: float = 60.0
    num_intervals: int = 20
    risk_aversion_lambda: float = 1e-4
    volatility_sigma: float = 0.20
    gamma: float = 2.5e-7
    eta: float = 5.0e-5
    alpha: float = 0.5              # Non-linear square root exponent
    spread: float = 0.25
    maker_rebate_rate: float = -0.00002 # -0.002%
    taker_fee_rate: float = 0.00005     # +0.005%

CONFIG_NEURO = NeuromorphicConfig()
CONFIG_MARKET = MarketConfig()
CONFIG_EXEC = ExecutionConfig()
CONFIG_AC = AlmgrenChrissExecutionConfig()

