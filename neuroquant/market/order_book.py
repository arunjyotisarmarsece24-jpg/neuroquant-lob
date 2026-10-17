"""
Level 2 / Level 3 Limit Order Book (LOB) Engine
================================================
Deterministic in-memory limit order book maintaining discrete price ladders,
depth queues, and real-time microstructural metrics (Micro-price, OFI, Spread).
"""

import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from collections import defaultdict
from config import MarketConfig

class OrderBook:
    """
    In-memory Level 2 / Level 3 Limit Order Book.
    """
    def __init__(self, config: MarketConfig):
        self.cfg = config
        self.tick_size = config.tick_size
        
        # Bids: sorted descending by price (highest bid first)
        # Asks: sorted ascending by price (lowest ask first)
        self.bids: Dict[float, float] = defaultdict(float) # price -> total volume
        self.asks: Dict[float, float] = defaultdict(float) # price -> total volume
        
        # Microstructure tracking
        self.prev_best_bid = config.initial_mid_price - (config.tick_size / 2.0)
        self.prev_best_ask = config.initial_mid_price + (config.tick_size / 2.0)
        self.prev_bid_size = 50.0
        self.prev_ask_size = 50.0
        self.current_ofi = 0.0
        
        # Trade reporting
        self.last_trade_side: Optional[str] = None
        self.last_trade_size: float = 0.0
        self.last_trade_price: float = config.initial_mid_price
        
        self.reset()

    def reset(self):
        """Seed book with initial balanced two-sided depth."""
        self.bids.clear()
        self.asks.clear()
        
        mid = self.cfg.initial_mid_price
        
        # Seed top 10 levels on both sides on exact tick multiples
        for i in range(self.cfg.book_depth_levels):
            bid_p = round(mid - self.tick_size - (i * self.tick_size), 4)
            ask_p = round(mid + (i * self.tick_size), 4)
            base_vol = 20.0 + (i * 5.0) + np.random.uniform(0.0, 10.0)
            self.bids[bid_p] = float(base_vol)
            self.asks[ask_p] = float(base_vol)
            
        self.prev_best_bid = max(self.bids.keys())
        self.prev_best_ask = min(self.asks.keys())
        self.prev_bid_size = self.bids[self.prev_best_bid]
        self.prev_ask_size = self.asks[self.prev_best_ask]
        self.current_ofi = 0.0

    def add_limit_order(self, side: str, price: float, size: float):
        """Insert or append liquidity to the order book."""
        price = round(price, 2)
        if side.upper() == 'BUY':
            self.bids[price] += size
        else:
            self.asks[price] += size
        self._update_microstructure()

    def cancel_order(self, side: str, price: float, size: float):
        """Remove liquidity from the order book."""
        price = round(price, 2)
        if side.upper() == 'BUY':
            if price in self.bids:
                self.bids[price] = max(0.0, self.bids[price] - size)
                if self.bids[price] == 0.0:
                    del self.bids[price]
        else:
            if price in self.asks:
                self.asks[price] = max(0.0, self.asks[price] - size)
                if self.asks[price] == 0.0:
                    del self.asks[price]
        self._update_microstructure()

    def match_market_order(self, side: str, size: float) -> List[Tuple[float, float]]:
        """
        Execute an incoming aggressive market order against resting limit orders.
        Returns list of (fill_price, fill_size).
        """
        fills = []
        remaining = size
        self.last_trade_side = side.upper()
        self.last_trade_size = size
        
        if side.upper() == 'BUY':
            # Buyer lifts the ask
            sorted_ask_prices = sorted(self.asks.keys())
            for p in sorted_ask_prices:
                avail = self.asks[p]
                if avail <= 0:
                    continue
                fill_qty = min(remaining, avail)
                fills.append((p, fill_qty))
                self.asks[p] -= fill_qty
                remaining -= fill_qty
                if self.asks[p] <= 0:
                    del self.asks[p]
                if remaining <= 0:
                    break
            self.last_trade_price = fills[-1][0] if fills else self.prev_best_ask
        else:
            # Seller hits the bid
            sorted_bid_prices = sorted(self.bids.keys(), reverse=True)
            for p in sorted_bid_prices:
                avail = self.bids[p]
                if avail <= 0:
                    continue
                fill_qty = min(remaining, avail)
                fills.append((p, fill_qty))
                self.bids[p] -= fill_qty
                remaining -= fill_qty
                if self.bids[p] <= 0:
                    del self.bids[p]
                if remaining <= 0:
                    break
            self.last_trade_price = fills[-1][0] if fills else self.prev_best_bid
            
        self._update_microstructure()
        return fills

    def _update_microstructure(self):
        """Recalculate Order Flow Imbalance (OFI) based on Cont et al. formula."""
        best_b = self.best_bid
        best_a = self.best_ask
        curr_b_sz = self.bids.get(best_b, 0.0)
        curr_a_sz = self.asks.get(best_a, 0.0)
        
        # Calculate Bid contribution
        if best_b > self.prev_best_bid:
            delta_bid = curr_b_sz
        elif best_b == self.prev_best_bid:
            delta_bid = curr_b_sz - self.prev_bid_size
        else:
            delta_bid = -self.prev_bid_size
            
        # Calculate Ask contribution
        if best_a < self.prev_best_ask:
            delta_ask = curr_a_sz
        elif best_a == self.prev_best_ask:
            delta_ask = curr_a_sz - self.prev_ask_size
        else:
            delta_ask = -self.prev_ask_size
            
        self.current_ofi = delta_bid - delta_ask
        
        self.prev_best_bid = best_b
        self.prev_best_ask = best_a
        self.prev_bid_size = curr_b_sz
        self.prev_ask_size = curr_a_sz

    @property
    def best_bid(self) -> float:
        return max(self.bids.keys()) if self.bids else self.cfg.initial_mid_price - 0.25

    @property
    def best_ask(self) -> float:
        return min(self.asks.keys()) if self.asks else self.cfg.initial_mid_price + 0.25

    @property
    def mid_price(self) -> float:
        return (self.best_bid + self.best_ask) / 2.0

    @property
    def spread(self) -> float:
        return max(self.tick_size, round(self.best_ask - self.best_bid, 2))

    @property
    def micro_price(self) -> float:
        """Volume-weighted micro-price accounting for queue imbalance."""
        q_b = self.bids.get(self.best_bid, 1.0)
        q_a = self.asks.get(self.best_ask, 1.0)
        total_q = q_b + q_a
        if total_q <= 0:
            return self.mid_price
        return (self.best_ask * q_b + self.best_bid * q_a) / total_q

    def get_snapshot(self) -> Dict[str, Any]:
        """Returns structured top-K depth ladder and microstructural stats."""
        sorted_bids = sorted(self.bids.items(), key=lambda x: x[0], reverse=True)[:self.cfg.book_depth_levels]
        sorted_asks = sorted(self.asks.items(), key=lambda x: x[0])[:self.cfg.book_depth_levels]
        
        return {
            "mid_price": round(self.mid_price, 2),
            "micro_price": round(self.micro_price, 4),
            "spread": self.spread,
            "best_bid": self.best_bid,
            "best_ask": self.best_ask,
            "bids": [(round(p, 2), round(v, 1)) for p, v in sorted_bids],
            "asks": [(round(p, 2), round(v, 1)) for p, v in sorted_asks],
            "ofi": round(self.current_ofi, 2),
            "last_trade_side": self.last_trade_side,
            "last_trade_size": self.last_trade_size,
            "last_trade_price": self.last_trade_price
        }
