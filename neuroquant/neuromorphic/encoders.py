"""
Event-Driven Microstructure Spike Encoders
===========================================
Converts continuous & discrete Limit Order Book (LOB) dynamics into asynchronous
temporal spike trains using delta modulation and inter-arrival rate coding.
"""

import numpy as np
from typing import Dict, Any, Tuple
from config import MarketConfig, NeuromorphicConfig

class LOBSpikeEncoder:
    """
    Transforms LOB state transitions and order flow into multi-channel digital spike events.
    Sensory Channel Mapping (32 channels total):
      - [0]: Mid-price upward tick spike (Delta-P >= +threshold)
      - [1]: Mid-price downward tick spike (Delta-P <= -threshold)
      - [2..11]: Bid Depth Influx (Levels 0..9)
      - [12..21]: Ask Depth Influx (Levels 0..9)
      - [22]: Order Flow Imbalance (OFI) > 0 (Aggressive buying pressure)
      - [23]: Order Flow Imbalance (OFI) < 0 (Aggressive selling pressure)
      - [24]: Spread Widening event (liquidity withdrawal)
      - [25]: Spread Tightening event (liquidity injection)
      - [26]: Burst frequency spike (inter-arrival time < threshold)
      - [27]: Micro-price divergence (Micro-price > Mid-price by > 0.5 ticks)
      - [28]: Micro-price divergence (Micro-price < Mid-price by < -0.5 ticks)
      - [29]: Aggressive Buy Trade (Market order filled at ask)
      - [30]: Aggressive Sell Trade (Market order filled at bid)
      - [31]: Institutional Large Volume Sweep detected
    """
    def __init__(self, market_cfg: MarketConfig, neuro_cfg: NeuromorphicConfig):
        self.market_cfg = market_cfg
        self.neuro_cfg = neuro_cfg
        self.num_channels = neuro_cfg.num_sensory_neurons
        
        # State tracking for delta modulation
        self.prev_mid_price = market_cfg.initial_mid_price
        self.prev_spread = market_cfg.tick_size
        self.prev_bid_depths = np.zeros(market_cfg.book_depth_levels, dtype=np.float32)
        self.prev_ask_depths = np.zeros(market_cfg.book_depth_levels, dtype=np.float32)
        self.last_event_timestamp_ms = 0.0

    def encode(self, lob_state: Dict[str, Any], timestamp_ms: float) -> np.ndarray:
        """
        Encode current LOB update into a binary spike vector.
        
        Parameters:
            lob_state: Dictionary containing current LOB metrics
                       ('mid_price', 'micro_price', 'bids', 'asks', 'ofi', 'last_trade_side', 'last_trade_size')
            timestamp_ms: Current simulation wall/event time in milliseconds
            
        Returns:
            spikes: 1D boolean numpy array of size `num_channels`.
        """
        spikes = np.zeros(self.num_channels, dtype=np.bool_)
        
        mid_price = lob_state.get('mid_price', self.prev_mid_price)
        micro_price = lob_state.get('micro_price', mid_price)
        bids = lob_state.get('bids', [])  # list of (price, size)
        asks = lob_state.get('asks', [])  # list of (price, size)
        ofi = lob_state.get('ofi', 0.0)
        last_trade_side = lob_state.get('last_trade_side', None)
        last_trade_size = lob_state.get('last_trade_size', 0)
        
        # 1. Price Delta Modulation
        delta_p = mid_price - self.prev_mid_price
        if delta_p >= self.market_cfg.delta_price_threshold:
            spikes[0] = True
        elif delta_p <= -self.market_cfg.delta_price_threshold:
            spikes[1] = True
            
        # 2. Depth Delta Encoding (Top N Levels)
        for i in range(min(len(bids), self.market_cfg.book_depth_levels)):
            current_vol = bids[i][1]
            if current_vol - self.prev_bid_depths[i] >= self.market_cfg.delta_volume_threshold:
                spikes[2 + i] = True
            self.prev_bid_depths[i] = current_vol
            
        for i in range(min(len(asks), self.market_cfg.book_depth_levels)):
            current_vol = asks[i][1]
            if current_vol - self.prev_ask_depths[i] >= self.market_cfg.delta_volume_threshold:
                spikes[12 + i] = True
            self.prev_ask_depths[i] = current_vol
            
        # 3. Order Flow Imbalance (OFI) Spikes
        if ofi > 10.0:
            spikes[22] = True
        elif ofi < -10.0:
            spikes[23] = True
            
        # 4. Spread Dynamics
        if bids and asks:
            current_spread = asks[0][0] - bids[0][0]
            if current_spread > self.prev_spread:
                spikes[24] = True  # Spread widened
            elif current_spread < self.prev_spread:
                spikes[25] = True  # Spread tightened
            self.prev_spread = current_spread
            
        # 5. Inter-Arrival Burst Dynamics
        dt_event = timestamp_ms - self.last_event_timestamp_ms
        if 0.0 < dt_event <= self.market_cfg.burst_interarrival_cutoff_ms:
            spikes[26] = True  # High-frequency clustering / burst event
        self.last_event_timestamp_ms = timestamp_ms
        
        # 6. Micro-Price Disparity Spikes
        micro_diff = micro_price - mid_price
        if micro_diff >= 0.5 * self.market_cfg.tick_size:
            spikes[27] = True
        elif micro_diff <= -0.5 * self.market_cfg.tick_size:
            spikes[28] = True
            
        # 7. Aggressive Trade Executions
        if last_trade_side == 'BUY':
            spikes[29] = True
        elif last_trade_side == 'SELL':
            spikes[30] = True
            
        # 8. Institutional Sweep / Block Trade
        if last_trade_size >= 50:
            spikes[31] = True
            
        self.prev_mid_price = mid_price
        return spikes
