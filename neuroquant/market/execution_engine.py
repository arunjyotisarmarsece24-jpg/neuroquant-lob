"""
Quantitative Execution & Market Making Engine
==============================================
Simulates high-frequency passive market making, tracking inventory risk,
adverse selection slippage, maker/taker fee rebates, and calculating
continuous reinforcement signals for neuromorphic plasticity.
"""

import numpy as np
from typing import Dict, Any, Tuple, Optional, List
from config import ExecutionConfig, MarketConfig
from .order_book import OrderBook

class ExecutionEngine:
    """
    Market making execution simulator with Avellaneda-Stoikov inventory control
    and neuromorphic event-driven quote placement.
    """
    def __init__(self, order_book: OrderBook, exec_cfg: ExecutionConfig, mkt_cfg: MarketConfig):
        self.book = order_book
        self.exec_cfg = exec_cfg
        self.mkt_cfg = mkt_cfg
        
        # Portfolio Accounting
        self.cash = exec_cfg.initial_capital
        self.inventory = 0  # Net contracts held
        self.realized_pnl = 0.0
        self.total_trades = 0
        self.adverse_selections_avoided = 0
        self.toxic_hits_taken = 0
        
        # Active Quotes
        self.my_bid_price: Optional[float] = None
        self.my_ask_price: Optional[float] = None
        self.quote_active: bool = False
        
        # Performance Tracking
        self.pnl_history: List[float] = []
        self.inventory_history: List[int] = []

    def update_quotes(self, neuro_signals: Dict[str, float]) -> Tuple[float, float, bool]:
        """
        Compute optimal bid and ask quotes using neuromorphic microstructural signals.
        
        Parameters:
            neuro_signals: Dict containing 'skew', 'toxicity_prob', 'volatility_pulse'
            
        Returns:
            Tuple of (my_bid, my_ask, is_quoted)
        """
        mid = self.book.mid_price
        tick = self.mkt_cfg.tick_size
        max_inv = self.exec_cfg.max_inventory
        
        # 1. Superlinear Avellaneda-Stoikov Inventory Penalty
        # Penalty grows exponentially as inventory approaches risk boundary
        inv_ratio = self.inventory / float(max_inv)
        inv_penalty = np.sign(self.inventory) * (abs(inv_ratio) ** 1.8) * (tick * 8.0)
        
        # 2. Neuromorphic Skew & Volatility Adjustment
        neuro_skew = neuro_signals.get("skew", 0.0) * tick * 2.0
        vol_pulse = neuro_signals.get("volatility_pulse", 0.0)
        toxicity_prob = neuro_signals.get("toxicity_prob", 0.0)
        
        # 3. Toxicity Defense: Pull quotes on institutional sweeps
        if toxicity_prob > 0.40:
            self.quote_active = False
            self.my_bid_price = None
            self.my_ask_price = None
            self.adverse_selections_avoided += 1
            return 0.0, 0.0, False
            
        self.quote_active = True
        half_spread = (tick * 1.5) + (vol_pulse * tick * 2.0) + (toxicity_prob * tick * 3.0)
        
        # Calculate reservation price shifted by inventory imbalance
        reservation_price = mid - inv_penalty + neuro_skew
        optimal_bid = round((reservation_price - half_spread) / tick) * tick
        optimal_ask = round((reservation_price + half_spread) / tick) * tick
        
        # 4. Asymmetric Emergency Quote Fading / Inventory Unwind
        # When long inventory >= 70% (e.g. +35), COMPLETELY PULL BID and aggressively shade Ask to liquidate
        if self.inventory >= int(0.70 * max_inv):
            self.my_bid_price = None
            optimal_ask = min(optimal_ask, self.book.best_ask)
            self.my_ask_price = round(optimal_ask, 2)
            return 0.0, self.my_ask_price, True
            
        # When short inventory <= -70% (e.g. -35), COMPLETELY PULL ASK and aggressively shade Bid to cover
        elif self.inventory <= -int(0.70 * max_inv):
            self.my_ask_price = None
            optimal_bid = max(optimal_bid, self.book.best_bid)
            self.my_bid_price = round(optimal_bid, 2)
            return self.my_bid_price, 0.0, True
            
        # Standard two-sided quote regime
        if optimal_bid >= optimal_ask:
            optimal_bid = optimal_ask - tick
            
        self.my_bid_price = round(optimal_bid, 2)
        self.my_ask_price = round(optimal_ask, 2)
        return self.my_bid_price, self.my_ask_price, True

    def process_fill_check(self, last_trade_side: Optional[str], last_trade_price: float, last_trade_size: float) -> Tuple[float, float]:
        """
        Check if our resting passive quotes got executed by incoming market order flow.
        
        Returns:
            Tuple of (step_reward, trade_pnl)
        """
        step_reward = 0.0
        trade_pnl = 0.0
        
        if not self.quote_active or last_trade_side is None:
            return step_reward, trade_pnl
            
        # Check Bid Fill: aggressive seller hit the bid
        if last_trade_side == 'SELL' and self.my_bid_price is not None:
            if last_trade_price <= self.my_bid_price:
                # We bought at my_bid_price
                fill_qty = min(self.exec_cfg.order_size, self.exec_cfg.max_inventory - self.inventory)
                if fill_qty > 0:
                    fill_cost = fill_qty * self.my_bid_price
                    self.cash -= fill_cost
                    self.inventory += fill_qty
                    self.total_trades += 1
                    
                    # Reward: spread captured minus inventory risk
                    spread_gain = (self.book.mid_price - self.my_bid_price) * fill_qty
                    step_reward += float(spread_gain * 2.0)
                    
                    # Check if immediate adverse selection occurred (price plummeted right after fill)
                    if self.book.mid_price < self.my_bid_price - (2 * self.mkt_cfg.tick_size):
                        step_reward -= 4.0
                        self.toxic_hits_taken += 1
                        
        # Check Ask Fill: aggressive buyer lifted the ask
        elif last_trade_side == 'BUY' and self.my_ask_price is not None:
            if last_trade_price >= self.my_ask_price:
                # We sold at my_ask_price
                fill_qty = min(self.exec_cfg.order_size, self.inventory + self.exec_cfg.max_inventory)
                if fill_qty > 0:
                    fill_revenue = fill_qty * self.my_ask_price
                    self.cash += fill_revenue
                    self.inventory -= fill_qty
                    self.total_trades += 1
                    
                    spread_gain = (self.my_ask_price - self.book.mid_price) * fill_qty
                    step_reward += float(spread_gain * 2.0)
                    
                    # Check if immediate adverse selection occurred (price surged right after fill)
                    if self.book.mid_price > self.my_ask_price + (2 * self.mkt_cfg.tick_size):
                        step_reward -= 4.0
                        self.toxic_hits_taken += 1
                        
        # Inventory Holding Penalty
        inv_loss = abs(self.inventory) * 0.02
        step_reward -= float(inv_loss)
        
        # Record PnL
        current_mtm_pnl = self.mark_to_market_pnl
        self.pnl_history.append(current_mtm_pnl)
        self.inventory_history.append(self.inventory)
        
        return step_reward, trade_pnl

    @property
    def mark_to_market_pnl(self) -> float:
        """Mark-to-market total portfolio equity."""
        portfolio_equity = self.cash + (self.inventory * self.book.mid_price)
        return portfolio_equity - self.exec_cfg.initial_capital

    def get_portfolio_status(self) -> Dict[str, Any]:
        """Structured telemetry dictionary."""
        pnl = self.mark_to_market_pnl
        max_inv = self.exec_cfg.max_inventory
        if self.inventory >= int(0.70 * max_inv):
            inv_state = "EMERGENCY_UNWIND_LONG"
        elif self.inventory <= -int(0.70 * max_inv):
            inv_state = "EMERGENCY_UNWIND_SHORT"
        elif self.inventory >= 15:
            inv_state = "SKEWED_LONG"
        elif self.inventory <= -15:
            inv_state = "SKEWED_SHORT"
        else:
            inv_state = "BALANCED"
            
        return {
            "pnl": round(pnl, 2),
            "cash": round(self.cash, 2),
            "inventory": self.inventory,
            "inventory_state": inv_state,
            "total_trades": self.total_trades,
            "my_bid": self.my_bid_price,
            "my_ask": self.my_ask_price,
            "quote_active": self.quote_active,
            "adverse_selections_avoided": self.adverse_selections_avoided,
            "toxic_hits_taken": self.toxic_hits_taken
        }
