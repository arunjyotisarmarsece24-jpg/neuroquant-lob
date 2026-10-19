"""
Neuromorphic RSNN Adaptive Urgency Execution Bridge
===================================================
Connects biological spiking neural network (RSNN) motor readout signals
to the Almgren-Chriss dynamic liquidation trajectory and exchange routing:

Microstructural Signals & Execution Actions:
  1. Toxicity Spike (Motor Channel 2):
     Institutional sweep / adverse flow detected.
     -> Drastically increases liquidation urgency (kappa_eff = kappa_0 * (1 + beta * tox))
     -> Aggressively unloads inventory to avoid toxic flash crash drops.
  2. Micro-Volatility Burst (Motor Channel 3):
     Elevated order book turbulence / widened spreads.
     -> Throttles aggressive taker velocity to avoid non-linear impact penalties (eta * v^0.5).
  3. Directional Momentum (Motor Channel 0 & 1):
     Favorable order book imbalance:
     -> Channel 0 (Upward Move while Selling): Passive maker limit quoting on Ask to capture
        half-spread and harvest the -0.002% maker rebate!
     -> Channel 1 (Downward Move while Selling): Immediate taker market sweep to cut inventory.
"""

import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from .market_impact import NonLinearMarketImpactEngine, MarketImpactConfig
from .fee_model import TieredExchangeFeeModel, FeeModelConfig, ExecutionFillRecord
from .almgren_chriss import AlmgrenChrissOptimizer, AlmgrenChrissConfig, LiquidationSchedule

@dataclass
class AdaptiveUrgencyConfig:
    total_shares: float = 10_000.0
    time_horizon_sec: float = 60.0
    num_intervals: int = 20
    base_lambda: float = 1e-4
    volatility_sigma: float = 0.20
    gamma: float = 2.5e-7
    eta: float = 5.0e-5
    alpha: float = 0.5               # Square-root non-linear impact
    spread: float = 0.25
    toxicity_urgency_gain: float = 3.5 # Multiplier on urgency when toxicity spikes
    volatility_throttle_gain: float = 0.5 # Impact dampener during volatility bursts
    maker_rebate_rate: float = -0.00002 # -0.002%
    taker_fee_rate: float = 0.00005     # +0.005%

class NeuromorphicAdaptiveExecutionEngine:
    """
    Event-driven adaptive execution simulator combining Almgren-Chriss optimal control,
    non-linear square-root market impact, tiered maker/taker fees, and RSNN motor signals.
    """
    def __init__(self, config: Optional[AdaptiveUrgencyConfig] = None):
        self.config = config or AdaptiveUrgencyConfig()

        # Internal execution components
        impact_cfg = MarketImpactConfig(
            gamma=self.config.gamma,
            eta=self.config.eta,
            alpha=self.config.alpha,
            default_spread=self.config.spread
        )
        self.impact_engine = NonLinearMarketImpactEngine(impact_cfg)

        fee_cfg = FeeModelConfig(
            maker_fee_rate=self.config.maker_rebate_rate,
            taker_fee_rate=self.config.taker_fee_rate
        )
        self.fee_model = TieredExchangeFeeModel(fee_cfg)

        ac_cfg = AlmgrenChrissConfig(
            total_shares=self.config.total_shares,
            time_horizon_sec=self.config.time_horizon_sec,
            num_intervals=self.config.num_intervals,
            risk_aversion_lambda=self.config.base_lambda,
            volatility_sigma=self.config.volatility_sigma,
            gamma=self.config.gamma,
            eta=self.config.eta,
            alpha=self.config.alpha,
            spread=self.config.spread
        )
        self.ac_optimizer = AlmgrenChrissOptimizer(ac_cfg)

        # State tracking
        self.remaining_shares: float = self.config.total_shares
        self.current_step: int = 0
        self.time_elapsed: float = 0.0
        self.tau: float = self.config.time_horizon_sec / self.config.num_intervals

        # Telemetry histories
        self.step_history: List[Dict[str, Any]] = []

    def compute_adaptive_trade_slice(self, 
                                     remaining_shares: float,
                                     intervals_left: int,
                                     neuro_signals: Dict[str, float]) -> Tuple[float, bool, float]:
        """
        Calculates the adaptive trade quantity and maker/taker routing for the current interval.
        
        Parameters:
            remaining_shares: Outstanding shares to liquidate
            intervals_left: Number of remaining execution intervals (including this one)
            neuro_signals: Motor signals:
                           'toxicity_prob': probability of toxic adverse flow [0, 1]
                           'volatility_pulse': localized microstructure volatility burst [0, 1]
                           'upward_prob': probability of upward micro-price drift [0, 1]
                           'downward_prob': probability of downward micro-price drift [0, 1]
                           
        Returns:
            Tuple of (trade_slice_qty, is_maker, effective_kappa)
        """
        if intervals_left <= 0 or remaining_shares <= 0:
            return 0.0, False, 0.0

        if intervals_left == 1:
            # Final interval: must liquidate all remaining shares immediately
            return remaining_shares, False, 1.0

        tox = float(neuro_signals.get("toxicity_prob", 0.0))
        vol = float(neuro_signals.get("volatility_pulse", 0.0))
        up_prob = float(neuro_signals.get("upward_prob", 0.0))
        down_prob = float(neuro_signals.get("downward_prob", 0.0))

        # 1. Dynamic Urgency Scaling:
        # High toxicity increases effective risk aversion (accelerates schedule)
        urgency_multiplier = 1.0 + (self.config.toxicity_urgency_gain * tox)
        adaptive_lambda = self.config.base_lambda * (urgency_multiplier ** 2)

        # Compute dynamic Almgren-Chriss schedule for remaining horizon
        temp_cfg = AlmgrenChrissConfig(
            total_shares=remaining_shares,
            time_horizon_sec=intervals_left * self.tau,
            num_intervals=intervals_left,
            risk_aversion_lambda=adaptive_lambda,
            volatility_sigma=self.config.volatility_sigma,
            gamma=self.config.gamma,
            eta=self.config.eta,
            alpha=self.config.alpha,
            spread=self.config.spread
        )
        temp_opt = AlmgrenChrissOptimizer(temp_cfg)
        sched = temp_opt.calculate_optimal_schedule(remaining_shares, adaptive_lambda)

        target_slice = sched.trades[0]
        eff_kappa = sched.kappa

        # 2. Volatility Throttling:
        # If volatility bursts, reduce aggressive market impact by dampening slice
        if vol > 0.30:
            throttle = max(0.5, 1.0 - (self.config.volatility_throttle_gain * vol))
            target_slice = target_slice * throttle

        # 3. Maker vs Taker Routing & Rebate Capture:
        # When upward price drift is detected with low toxicity, place passive Limit Ask (Maker)
        # to earn maker rebate (-0.002%) and capture the half-spread without temporary impact.
        is_maker = False
        if up_prob >= 0.30 and tox < 0.20:
            is_maker = True
        elif down_prob > 0.40 or tox > 0.30:
            # Force aggressive taker market order to exit immediately
            is_maker = False

        # Clamp trade slice within physical boundaries
        trade_slice = max(0.0, min(float(target_slice), remaining_shares))
        return trade_slice, is_maker, eff_kappa

    def execute_interval(self, 
                         current_mid: float, 
                         neuro_signals: Dict[str, float]) -> Dict[str, Any]:
        """
        Simulates execution of one discrete interval tau.
        """
        self.current_step += 1
        self.time_elapsed += self.tau
        intervals_left = self.config.num_intervals - self.current_step + 1

        slice_qty, is_maker, eff_kappa = self.compute_adaptive_trade_slice(
            self.remaining_shares, intervals_left, neuro_signals
        )

        # Calculate market impact & execution price
        impact_res = self.impact_engine.calculate_execution(
            mid_price=current_mid,
            order_qty=slice_qty,
            dt=self.tau,
            is_selling=True,
            is_taker=not is_maker,
            current_spread=self.config.spread
        )

        exec_price = impact_res["exec_price"]
        new_mid = impact_res["new_mid_price"]

        # Record exchange fill, fee, or rebate
        fill_record = self.fee_model.record_fill(
            timestamp=self.time_elapsed,
            order_id=self.current_step,
            quantity=slice_qty,
            exec_price=exec_price,
            is_selling=True,
            is_maker=is_maker
        )

        # Update remaining inventory
        self.remaining_shares -= slice_qty
        if self.remaining_shares < 1e-6:
            self.remaining_shares = 0.0

        step_telemetry = {
            "step": self.current_step,
            "time_sec": round(self.time_elapsed, 2),
            "slice_qty": round(slice_qty, 2),
            "remaining_shares": round(self.remaining_shares, 2),
            "is_maker": is_maker,
            "order_type": "MAKER_LIMIT" if is_maker else "TAKER_MARKET",
            "pre_trade_mid": round(current_mid, 4),
            "exec_price": round(exec_price, 4),
            "new_mid": round(new_mid, 4),
            "spread_cost_per_share": round(impact_res["half_spread_cost"], 4),
            "temp_impact_per_share": round(impact_res["temp_impact_per_share"], 4),
            "perm_impact_per_share": round(impact_res["perm_impact_per_share"], 4),
            "fee_dollars": round(fill_record.fee_or_rebate_dollars, 4),
            "effective_kappa": round(eff_kappa, 4),
            "neuro_signals": {k: round(float(v), 3) for k, v in neuro_signals.items()}
        }
        self.step_history.append(step_telemetry)
        return step_telemetry

    def get_summary_report(self, arrival_price: float) -> Dict[str, Any]:
        """
        Generates comprehensive TCA and execution quality report.
        """
        tca = self.fee_model.compute_implementation_shortfall(
            arrival_price=arrival_price,
            target_quantity=self.config.total_shares,
            is_selling=True
        )
        return {
            "strategy": "Neuromorphic_Adaptive_Almgren_Chriss",
            "tca": tca,
            "step_count": len(self.step_history),
            "total_executed_shares": round(tca["executed_quantity"], 2),
            "remaining_unfilled_shares": round(self.remaining_shares, 2),
            "steps": self.step_history
        }
