"""
Neuromorphic Microstructure Strategy Orchestrator
==================================================
Unified coordinator linking the Hawkes Market Feed, Limit Order Book,
LOB Spike Encoder, Digital Neuromorphic RSNN, and Execution Engine.
"""

import time
import numpy as np
from typing import Dict, Any, Tuple
from config import CONFIG_NEURO, CONFIG_MARKET, CONFIG_EXEC, NeuromorphicConfig, MarketConfig, ExecutionConfig
from neuroquant.neuromorphic import DigitalNeuromorphicCore, LOBSpikeEncoder
from neuroquant.market import OrderBook, HawkesMarketFeed, ExecutionEngine

class NeuromorphicAlphaSystem:
    """
    Complete end-to-end event-driven neuromorphic trading system.
    """
    def __init__(self, 
                 neuro_cfg: NeuromorphicConfig = CONFIG_NEURO,
                 mkt_cfg: MarketConfig = CONFIG_MARKET,
                 exec_cfg: ExecutionConfig = CONFIG_EXEC):
        self.neuro_cfg = neuro_cfg
        self.mkt_cfg = mkt_cfg
        self.exec_cfg = exec_cfg
        
        # Instantiate Core Components
        self.book = OrderBook(mkt_cfg)
        self.feed = HawkesMarketFeed(self.book, mkt_cfg)
        self.encoder = LOBSpikeEncoder(mkt_cfg, neuro_cfg)
        self.brain = DigitalNeuromorphicCore(neuro_cfg)
        self.executor = ExecutionEngine(self.book, exec_cfg, mkt_cfg)
        
        self.sim_step_count = 0
        self.sim_time_ms = 0.0
        self.last_reward = 0.0

    def step(self) -> Dict[str, Any]:
        """
        Advance the entire neuromorphic market making loop by one discrete time-step.
        
        Lifecycle per step:
          1. Hawkes process generates market feed event -> updates LOB.
          2. Encoder converts LOB state delta into sensory spike vector.
          3. Brain integrates spikes across LIF populations -> updates R-STDP weights using previous reward.
          4. Motor population produces continuous quote skew & toxicity probabilities.
          5. Execution engine updates two-sided quotes & processes trade fill executions.
          6. Generates immediate financial reward for the next neuromorphic plasticity cycle.
        """
        self.sim_step_count += 1
        dt_ms = self.neuro_cfg.time_step_ms
        self.sim_time_ms += dt_ms
        
        # 1. Market Feed Step
        lob_snapshot, event_desc = self.feed.step(dt_sec=dt_ms / 1000.0)
        
        # 2. Encode LOB dynamics into asynchronous spikes
        sensory_spikes = self.encoder.encode(lob_snapshot, self.sim_time_ms)
        
        # 3. Neuromorphic RSNN Core Forward Step (with R-STDP plasticity)
        s_spk, h_spk, m_spk = self.brain.step(sensory_spikes, reward=self.last_reward)
        neuro_signals = self.brain.get_motor_readout_signals()
        
        # 4. Check for Execution Fills against incoming market flow
        fill_reward, trade_pnl = self.executor.process_fill_check(
            lob_snapshot.get('last_trade_side'),
            lob_snapshot.get('last_trade_price', self.book.mid_price),
            lob_snapshot.get('last_trade_size', 0)
        )
        self.last_reward = fill_reward
        
        # 5. Update Resting Market Making Quotes for the next tick
        my_bid, my_ask, is_quoted = self.executor.update_quotes(neuro_signals)
        
        # 6. Assemble Telemetry Bundle
        telemetry = {
            "step": self.sim_step_count,
            "sim_time_ms": round(self.sim_time_ms, 2),
            "event": event_desc,
            "market": lob_snapshot,
            "portfolio": self.executor.get_portfolio_status(),
            "neuro": {
                "signals": neuro_signals,
                "sensory_active_count": int(np.sum(s_spk)),
                "hidden_active_count": int(np.sum(h_spk)),
                "motor_active_count": int(np.sum(m_spk)),
                "sensory_firing_indices": np.where(s_spk)[0].tolist(),
                "hidden_firing_indices": np.where(h_spk)[0].tolist(),
                "motor_firing_indices": np.where(m_spk)[0].tolist(),
                "sensory_v_mean": round(self.brain.sensory.get_mean_voltage(), 2),
                "hidden_v_mean": round(self.brain.hidden.get_mean_voltage(), 2),
                "motor_v": [round(float(v), 2) for v in self.brain.motor.voltage],
                "motor_weights_norm": round(float(np.linalg.norm(self.brain.plasticity_motor.weights)), 4)
            }
        }
        return telemetry

    def reset(self):
        """Reset entire simulation to genesis state."""
        self.book.reset()
        self.brain.sensory.reset()
        self.brain.hidden.reset()
        self.brain.motor.reset()
        self.sim_step_count = 0
        self.sim_time_ms = 0.0
        self.last_reward = 0.0
