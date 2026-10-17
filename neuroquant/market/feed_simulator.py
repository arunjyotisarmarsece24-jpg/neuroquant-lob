"""
Hawkes Point Process & High-Frequency Market Feed Simulator
===========================================================
Simulates realistic high-frequency financial order flow with self-exciting
Hawkes point processes, endogenous volatility bursts, and toxic institutional sweeps.
"""

import numpy as np
from typing import Dict, Any, Tuple
from config import MarketConfig
from .order_book import OrderBook

class HawkesMarketFeed:
    """
    Self-exciting Hawkes process generator for order book events.
    Intensity: lambda(t) = mu + alpha * sum(exp(-beta * (t - t_i)))
    """
    def __init__(self, order_book: OrderBook, config: MarketConfig):
        self.book = order_book
        self.cfg = config
        
        self.mu = config.hawkes_baseline_lambda
        self.alpha = config.hawkes_alpha
        self.beta = config.hawkes_beta
        
        self.current_intensity = self.mu
        self.last_event_time_sec = 0.0
        self.sim_time_sec = 0.0
        
        # Institutional toxic flow state
        self.toxic_regime = False
        self.toxic_steps_remaining = 0
        self.toxic_direction = 'BUY'

    def step(self, dt_sec: float) -> Tuple[Dict[str, Any], str]:
        """
        Advance simulation clock by dt_sec and conditionally generate order book events.
        
        Returns:
            Tuple of (lob_snapshot, event_description)
        """
        self.sim_time_sec += dt_sec
        
        # 1. Decay Hawkes Excitation
        dt_since_last = self.sim_time_sec - self.last_event_time_sec
        self.current_intensity = self.mu + (self.current_intensity - self.mu) * np.exp(-self.beta * dt_since_last)
        
        # 2. Probability of event arrival in this discrete interval (Poisson thinning)
        event_prob = 1.0 - np.exp(-self.current_intensity * dt_sec)
        event_desc = "NO_EVENT"
        
        if np.random.uniform(0.0, 1.0) < event_prob:
            # Self-excitation jump
            self.current_intensity += self.alpha * 15.0
            self.last_event_time_sec = self.sim_time_sec
            
            # 3. Determine Event Archetype
            # Check toxic regime
            if self.toxic_steps_remaining > 0:
                self.toxic_steps_remaining -= 1
                event_desc = self._execute_toxic_sweep()
            elif np.random.uniform(0.0, 1.0) < self.cfg.toxic_order_ratio:
                # Initiate a new toxic informed institutional flow cluster
                self.toxic_steps_remaining = np.random.randint(3, 8)
                self.toxic_direction = 'BUY' if np.random.uniform(0.0, 1.0) > 0.5 else 'SELL'
                event_desc = self._execute_toxic_sweep()
            else:
                event_desc = self._execute_standard_flow()
                
        snapshot = self.book.get_snapshot()
        return snapshot, event_desc

    def _execute_toxic_sweep(self) -> str:
        """Executes a large aggressive market sweep that penetrates multiple book levels."""
        sweep_size = float(np.random.randint(60, 150))
        side = self.toxic_direction
        fills = self.book.match_market_order(side, sweep_size)
        return f"TOXIC_SWEEP_{side}_{int(sweep_size)}_FILLED_{len(fills)}_LEVELS"

    def _execute_standard_flow(self) -> str:
        """Executes passive quote placements, cancellations, or small normal retail orders."""
        action_roll = np.random.uniform(0.0, 1.0)
        side = 'BUY' if np.random.uniform(0.0, 1.0) > 0.5 else 'SELL'
        tick = self.cfg.tick_size
        
        if action_roll < 0.45:
            # Add Limit Order near top of book
            price_offset = np.random.choice([0, 1, 2, 3]) * tick
            if side == 'BUY':
                p = self.book.best_bid - price_offset
            else:
                p = self.book.best_ask + price_offset
            size = float(np.random.randint(5, 25))
            self.book.add_limit_order(side, p, size)
            return f"ADD_LIMIT_{side}_{size}@{p:.2f}"
            
        elif action_roll < 0.75:
            # Cancel Order at existing level
            if side == 'BUY' and self.book.bids:
                p = np.random.choice(list(self.book.bids.keys()))
                size = float(min(self.book.bids[p], np.random.randint(5, 15)))
                self.book.cancel_order('BUY', p, size)
                return f"CANCEL_LIMIT_BUY_{size}@{p:.2f}"
            elif side == 'SELL' and self.book.asks:
                p = np.random.choice(list(self.book.asks.keys()))
                size = float(min(self.book.asks[p], np.random.randint(5, 15)))
                self.book.cancel_order('SELL', p, size)
                return f"CANCEL_LIMIT_SELL_{size}@{p:.2f}"
            return "CANCEL_NOOP"
            
        else:
            # Normal Aggressive Market Order
            size = float(np.random.randint(1, 15))
            self.book.match_market_order(side, size)
            return f"MARKET_{side}_{size}"
