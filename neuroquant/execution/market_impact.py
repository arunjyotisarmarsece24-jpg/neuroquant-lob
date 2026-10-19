"""
Non-Linear Market Impact Engine
===============================
Implements institutional market microstructure price impact modeling:
  1. Permanent Price Impact: g(v) = gamma * v
  2. Temporary Non-Linear Price Impact: h(v) = eta * sign(v) * |v|^alpha
     (Defaults to the universal square-root law of market impact: alpha = 0.5)
  3. Half-Spread Friction: epsilon = 0.5 * spread
  4. Realized Execution Price & Slippage Decomposition

References:
  - Almgren, R., & Chriss, N. (2000). Optimal execution of portfolio transactions.
  - Bouchaud, J. P., Farmer, J. D., & Lillo, F. (2009). How markets slowly digest changes in supply and demand.
  - Kyle, A. S., & Obizhaeva, A. A. (2016). Market microstructure invariance: Empirical hypotheses.
"""

import numpy as np
from typing import Dict, Any, Tuple, Optional
from dataclasses import dataclass

@dataclass
class MarketImpactConfig:
    gamma: float = 2.5e-7       # Permanent price impact parameter ($ / share^2 / sec)
    eta: float = 5.0e-5         # Temporary price impact parameter ($ / (share / sec)^alpha)
    alpha: float = 0.5          # Square-root impact exponent (0.5 for empirical Bouchaud / Kyle law)
    default_spread: float = 0.25 # Bid-ask spread ($)
    tick_size: float = 0.25

class NonLinearMarketImpactEngine:
    """
    Computes instantaneous and permanent market impact for aggressive and passive executions.
    """
    def __init__(self, config: Optional[MarketImpactConfig] = None):
        self.config = config or MarketImpactConfig()

    def permanent_impact(self, trade_rate: float) -> float:
        """
        Permanent price displacement per unit time: g(v) = gamma * v.
        Trade rate v = trade_qty / dt.
        
        A sell order (v > 0) causes a downward permanent price drift (-gamma * v).
        A buy order (v < 0) causes an upward permanent price drift (+gamma * |v|).
        """
        return self.config.gamma * trade_rate

    def temporary_impact(self, trade_rate: float) -> float:
        """
        Temporary price impact: h(v) = eta * sign(v) * |v|^alpha.
        With alpha = 0.5, this implements the square-root law of price impact.
        """
        if abs(trade_rate) < 1e-12:
            return 0.0
        return self.config.eta * np.sign(trade_rate) * (abs(trade_rate) ** self.config.alpha)

    def calculate_execution(self, 
                            mid_price: float, 
                            order_qty: float, 
                            dt: float, 
                            is_selling: bool = True,
                            is_taker: bool = True,
                            current_spread: Optional[float] = None) -> Dict[str, float]:
        """
        Calculate realized execution price, slippage, and price displacement for a trade slice.
        
        Parameters:
            mid_price: Prevailing mid-market price prior to trade
            order_qty: Quantity of shares/contracts executed in this interval (must be >= 0)
            dt: Time duration of interval in seconds
            is_selling: True if liquidating / selling, False if purchasing / buying
            is_taker: True if executing aggressively across spread (market order),
                      False if executing passively as limit order (maker)
            current_spread: Prevailing bid-ask spread (defaults to config.default_spread)
            
        Returns:
            Dictionary containing:
              - 'exec_price': Realized average execution price
              - 'new_mid_price': Mid price after permanent price impact
              - 'half_spread_cost': Half-spread concession ($ / share)
              - 'perm_impact_per_share': Permanent impact concession ($ / share)
              - 'temp_impact_per_share': Temporary impact concession ($ / share)
              - 'total_slippage_per_share': Total per-share slippage from arrival mid-price
              - 'total_dollar_slippage': Total dollar slippage for the entire order slice
        """
        if order_qty <= 0 or dt <= 0:
            return {
                "exec_price": mid_price,
                "new_mid_price": mid_price,
                "half_spread_cost": 0.0,
                "perm_impact_per_share": 0.0,
                "temp_impact_per_share": 0.0,
                "total_slippage_per_share": 0.0,
                "total_dollar_slippage": 0.0
            }

        spread = current_spread if current_spread is not None else self.config.default_spread
        half_spread = 0.5 * spread
        trade_rate = order_qty / dt

        # Direction signs:
        # For selling: price moves down, so realized price is lower than mid.
        # For buying: price moves up, so realized price is higher than mid.
        direction_sign = -1.0 if is_selling else 1.0

        if is_taker:
            # Aggressive taker crosses the half-spread and induces temporary non-linear impact
            h_v = self.temporary_impact(trade_rate)
            # Permanent impact during the trade interval: on average half the permanent displacement affects this trade
            perm_effective = 0.5 * self.permanent_impact(trade_rate) * dt
            spread_cost = half_spread
        else:
            # Passive maker sits on resting order book:
            # Maker earns half-spread, experiences zero adverse temporary impact
            h_v = 0.0
            perm_effective = 0.0
            spread_cost = -half_spread  # spread capture!

        # Total permanent mid-price displacement after entire trade completes
        total_perm_displacement = self.permanent_impact(trade_rate) * dt
        new_mid = mid_price + direction_sign * total_perm_displacement

        # Realized execution price
        # Selling: P_exec = P_mid - spread_cost - perm_effective - h_v
        # Buying:  P_exec = P_mid + spread_cost + perm_effective + h_v
        price_concession = spread_cost + perm_effective + abs(h_v)
        exec_price = mid_price + direction_sign * price_concession

        # Total per-share slippage relative to initial mid price:
        # Selling: mid_price - exec_price
        # Buying:  exec_price - mid_price
        per_share_slippage = price_concession
        total_dollar_slippage = per_share_slippage * order_qty

        return {
            "exec_price": float(exec_price),
            "new_mid_price": float(new_mid),
            "half_spread_cost": float(spread_cost),
            "perm_impact_per_share": float(perm_effective),
            "temp_impact_per_share": float(abs(h_v)),
            "total_slippage_per_share": float(per_share_slippage),
            "total_dollar_slippage": float(total_dollar_slippage)
        }
