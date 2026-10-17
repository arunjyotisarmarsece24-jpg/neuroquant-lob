"""
Veterans' Quantitative Audit Engine
====================================
Implements institutional-grade verification metrics:
  1. Microsecond Post-Trade Markout Decay Curves (Adverse Selection Analysis)
  2. FIFO Queue Position Tracking with Probabilistic Cancellation Attrition
  3. Deflated Sharpe Ratio (DSR) & Non-Normal Kurtosis/Skewness Adjustments
"""

import math
import numpy as np
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass

@dataclass
class FillEvent:
    timestamp_ms: float
    side: str
    fill_price: float
    fill_size: float
    mid_at_fill: float
    # Markout snapshots at delta-t horizons: [0.1ms, 0.5ms, 1ms, 5ms, 10ms, 50ms, 100ms]
    markouts: Dict[float, float]

class FIFOQueueTracker:
    """
    Realistic Level-3 FIFO Queue Tracker.
    Prevents unrealistic fills by tracking volume ahead and queue attrition.
    """
    def __init__(self, price: float, side: str, volume_ahead: float):
        self.price = price
        self.side = side
        self.volume_ahead = volume_ahead
        self.is_filled = False

    def on_trade_at_level(self, trade_size: float) -> float:
        """
        Incoming aggressive market trade hits the price level.
        Only fills our order after volume ahead is fully depleted.
        """
        if self.is_filled:
            return 0.0
            
        if self.volume_ahead > 0:
            depleted = min(self.volume_ahead, trade_size)
            self.volume_ahead -= depleted
            trade_size -= depleted
            
        if self.volume_ahead <= 0 and trade_size > 0:
            self.is_filled = True
            return float(trade_size) # Filled amount
            
        return 0.0

    def on_cancel_at_level(self, cancel_size: float):
        """
        Model cancel attrition: in real markets, roughly 30% of cancels
        occur ahead of you, 70% occur behind you or at the tail.
        """
        if self.volume_ahead > 0:
            attrition_ahead = cancel_size * 0.30
            self.volume_ahead = max(0.0, self.volume_ahead - attrition_ahead)

class VeteranQuantAuditor:
    """
    Institutional Audit Suite evaluating adverse selection and statistical rigor.
    """
    def __init__(self):
        self.horizons_ms = [0.1, 0.5, 1.0, 5.0, 10.0, 50.0, 100.0]
        self.fill_history: List[FillEvent] = []
        self.pending_markouts: List[FillEvent] = []
        self.pnl_returns: List[float] = []

    def record_fill(self, timestamp_ms: float, side: str, fill_price: float, fill_size: float, mid_at_fill: float):
        event = FillEvent(
            timestamp_ms=timestamp_ms,
            side=side,
            fill_price=fill_price,
            fill_size=fill_size,
            mid_at_fill=mid_at_fill,
            markouts={}
        )
        self.pending_markouts.append(event)
        self.fill_history.append(event)

    def update_markouts(self, current_time_ms: float, current_mid: float):
        """Update unresolved markouts as time horizons lapse."""
        still_pending = []
        for event in self.pending_markouts:
            elapsed = current_time_ms - event.timestamp_ms
            for h in self.horizons_ms:
                if h not in event.markouts and elapsed >= h:
                    # Directional Markout:
                    # For BUY:  (Mid(t + h) - FillPrice)
                    # For SELL: (FillPrice - Mid(t + h))
                    if event.side == 'BUY':
                        markout_val = current_mid - event.fill_price
                    else:
                        markout_val = event.fill_price - current_mid
                    event.markouts[h] = markout_val
                    
            # Check if all horizons are resolved
            if len(event.markouts) < len(self.horizons_ms):
                still_pending.append(event)
                
        self.pending_markouts = still_pending

    def calculate_markout_curves(self) -> Dict[float, float]:
        """
        Computes the average markout PnL across all historical fills per horizon.
        Positive curve = Real Alpha. Negative curve = Victim of Adverse Selection.
        """
        if not self.fill_history:
            return {h: 0.0 for h in self.horizons_ms}
            
        curve = {}
        for h in self.horizons_ms:
            values = [e.markouts[h] for e in self.fill_history if h in e.markouts]
            curve[h] = float(np.mean(values)) if values else 0.0
        return curve

    def calculate_deflated_sharpe_ratio(self, returns: np.ndarray, num_trials: int = 50) -> Dict[str, float]:
        """
        Computes the Deflated Sharpe Ratio (DSR) based on Bailey and López de Prado (2014).
        Adjusts for non-normality, sample length, skewness, and multi-trial selection bias.
        """
        if len(returns) < 30:
            return {"standard_sharpe": 0.0, "dsr_p_value": 0.0, "is_statistically_significant": False}
            
        # 1. Standard Annualized Sharpe Ratio
        mean_r = np.mean(returns)
        std_r = np.std(returns)
        if std_r <= 1e-8:
            return {"standard_sharpe": 0.0, "dsr_p_value": 0.0, "is_statistically_significant": False}
            
        sr = float(mean_r / std_r)
        
        # 2. Higher Moments (Skewness & Kurtosis)
        n = len(returns)
        skew = float(np.sum((returns - mean_r) ** 3) / (n * std_r ** 3))
        kurt = float(np.sum((returns - mean_r) ** 4) / (n * std_r ** 4))
        
        # 3. Variance of Sharpe Ratio under Non-Normality
        # Var(SR) = (1 / T) * [ 1 + (0.5 * SR^2) - (skew * SR) + ((kurt - 3) / 4) * SR^2 ]
        var_sr = (1.0 / n) * (1.0 + 0.5 * (sr ** 2) - skew * sr + ((kurt - 3.0) / 4.0) * (sr ** 2))
        std_sr = np.sqrt(max(1e-6, var_sr))
        
        # 4. Expected Maximum Sharpe Ratio from multiple trials (Euler-Mascheroni approximation)
        # E[max SR] = (1 - gamma) * Z^(-1)(1 - 1/N) + gamma * Z^(-1)(1 - 1/(N * e))
        gamma = 0.5772156649  # Euler-Mascheroni constant
        z1 = np.sqrt(2.0 * np.log(max(2, num_trials)))
        expected_max_sr = z1 + (gamma / z1) if z1 > 0 else 0.0
        
        # 5. DSR Statistic (PSR with benchmark = expected_max_sr)
        dsr_z = (sr - expected_max_sr) / std_sr
        # Standard normal CDF approximation for p-value
        dsr_prob = 0.5 * (1.0 + math.erf(dsr_z / np.sqrt(2.0)))
        
        return {
            "standard_sharpe": round(sr, 4),
            "skewness": round(skew, 4),
            "kurtosis": round(kurt, 4),
            "expected_max_sr_trials": round(expected_max_sr, 4),
            "dsr_prob": round(float(dsr_prob), 4),
            "is_statistically_significant": bool(dsr_prob > 0.95)
        }
