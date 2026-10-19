"""
Tiered Exchange Fee & Maker Rebate Accounting Model
===================================================
Implements institutional exchange fee structures:
  - Maker Rebate: -0.002% (-0.2 bps credit for resting passive liquidity)
  - Taker Fee:    +0.005% (+0.5 bps debit for aggressive liquidity-taking orders)
  - Complete Transaction Cost Analysis (TCA) & Implementation Shortfall (Perold 1988)

Equations:
  - Maker Rebate ($):  Rebate = abs(maker_rate) * notional_dollar_volume
  - Taker Fee ($):     Fee    = taker_rate * notional_dollar_volume
  - Implementation Shortfall ($):
      IS = (Arrival_Price * Total_Qty - Realized_Dollar_Value) + Total_Fees - Total_Rebates  (for Sell)
  - Implementation Shortfall (bps):
      IS_bps = (IS / (Arrival_Price * Total_Qty)) * 10,000
"""

import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field

@dataclass
class FeeModelConfig:
    maker_fee_rate: float = -0.00002   # -0.002% (-0.2 bps rebate)
    taker_fee_rate: float = 0.00005    # +0.005% (+0.5 bps fee)

@dataclass
class ExecutionFillRecord:
    timestamp: float
    order_id: int
    quantity: float
    exec_price: float
    is_selling: bool
    is_maker: bool
    fee_or_rebate_rate: float
    fee_or_rebate_dollars: float
    notional: float

class TieredExchangeFeeModel:
    """
    Tracks and accounts for institutional exchange fees, maker rebates,
    and calculates complete Implementation Shortfall Transaction Cost Analysis (TCA).
    """
    def __init__(self, config: Optional[FeeModelConfig] = None):
        self.config = config or FeeModelConfig()
        self.total_maker_rebates: float = 0.0
        self.total_taker_fees: float = 0.0
        self.total_maker_volume: float = 0.0
        self.total_taker_volume: float = 0.0
        self.fills: List[ExecutionFillRecord] = []

    def calculate_trade_fee(self, notional_value: float, is_maker: bool) -> Tuple[float, float]:
        """
        Calculates fee or rebate for a single executed trade notional.
        
        Parameters:
            notional_value: Dollar value of trade (price * quantity)
            is_maker: True if passive limit order (earns rebate), False if taker
            
        Returns:
            Tuple of (effective_rate, cash_impact_dollars)
            Note: cash_impact_dollars is positive for fees (cash drained),
                  negative for rebates (cash credited).
        """
        if is_maker:
            rate = self.config.maker_fee_rate  # Negative value e.g. -0.00002
            # Cash impact: negative means cash is added to portfolio
            dollar_impact = rate * notional_value
        else:
            rate = self.config.taker_fee_rate  # Positive value e.g. +0.00005
            dollar_impact = rate * notional_value
        return rate, dollar_impact

    def record_fill(self, 
                    timestamp: float, 
                    order_id: int, 
                    quantity: float, 
                    exec_price: float, 
                    is_selling: bool = True, 
                    is_maker: bool = False) -> ExecutionFillRecord:
        """
        Record an executed fill and update running fee/rebate tallies.
        """
        notional = float(quantity * exec_price)
        rate, dollar_impact = self.calculate_trade_fee(notional, is_maker)

        if is_maker:
            self.total_maker_rebates += abs(dollar_impact)
            self.total_maker_volume += notional
        else:
            self.total_taker_fees += dollar_impact
            self.total_taker_volume += notional

        record = ExecutionFillRecord(
            timestamp=timestamp,
            order_id=order_id,
            quantity=quantity,
            exec_price=exec_price,
            is_selling=is_selling,
            is_maker=is_maker,
            fee_or_rebate_rate=rate,
            fee_or_rebate_dollars=dollar_impact,
            notional=notional
        )
        self.fills.append(record)
        return record

    @property
    def net_fee_cash_impact(self) -> float:
        """
        Total cash debited by exchange:
        Net Fees = Total Taker Fees - Total Maker Rebates.
        Positive means net cost; negative means net rebate income.
        """
        return self.total_taker_fees - self.total_maker_rebates

    def compute_implementation_shortfall(self, 
                                         arrival_price: float, 
                                         target_quantity: float, 
                                         is_selling: bool = True) -> Dict[str, Any]:
        """
        Performs full institutional Implementation Shortfall Transaction Cost Analysis (TCA).
        
        Parameters:
            arrival_price: Mid price at the instant the portfolio liquidation order was conceived (P_0)
            target_quantity: Total contracts/shares targeted for execution (X_0)
            is_selling: True for liquidation (selling), False for acquisition (buying)
            
        Returns:
            Structured dictionary with dollar and basis point TCA metrics.
        """
        benchmark_notional = arrival_price * target_quantity
        total_executed_qty = sum(f.quantity for f in self.fills)
        total_realized_notional = sum(f.notional for f in self.fills)

        # Average execution price
        avg_exec_price = total_realized_notional / total_executed_qty if total_executed_qty > 0 else arrival_price

        # Gross Slippage (difference between paper benchmark and actual execution before fees)
        if is_selling:
            gross_slippage_dollars = (arrival_price * total_executed_qty) - total_realized_notional
        else:
            gross_slippage_dollars = total_realized_notional - (arrival_price * total_executed_qty)

        # Net Implementation Shortfall including exchange fees and maker rebates
        net_shortfall_dollars = gross_slippage_dollars + self.net_fee_cash_impact

        # Basis points conversions:
        denom = benchmark_notional if benchmark_notional > 0 else 1.0
        gross_slippage_bps = (gross_slippage_dollars / denom) * 10000.0
        fees_bps = (self.total_taker_fees / denom) * 10000.0
        rebates_bps = (self.total_maker_rebates / denom) * 10000.0
        net_fees_bps = (self.net_fee_cash_impact / denom) * 10000.0
        net_shortfall_bps = (net_shortfall_dollars / denom) * 10000.0

        total_volume = self.total_maker_volume + self.total_taker_volume
        maker_ratio = (self.total_maker_volume / total_volume) if total_volume > 0 else 0.0

        return {
            "target_quantity": target_quantity,
            "executed_quantity": total_executed_qty,
            "completion_pct": round((total_executed_qty / target_quantity) * 100.0, 2) if target_quantity > 0 else 100.0,
            "arrival_price": round(arrival_price, 4),
            "average_execution_price": round(avg_exec_price, 4),
            "benchmark_notional": round(benchmark_notional, 2),
            "realized_notional": round(total_realized_notional, 2),
            "gross_slippage_dollars": round(gross_slippage_dollars, 4),
            "gross_slippage_bps": round(gross_slippage_bps, 3),
            "total_taker_fees_dollars": round(self.total_taker_fees, 4),
            "total_taker_fees_bps": round(fees_bps, 3),
            "total_maker_rebates_dollars": round(self.total_maker_rebates, 4),
            "total_maker_rebates_bps": round(rebates_bps, 3),
            "net_fees_dollars": round(self.net_fee_cash_impact, 4),
            "net_fees_bps": round(net_fees_bps, 3),
            "net_shortfall_dollars": round(net_shortfall_dollars, 4),
            "net_shortfall_bps": round(net_shortfall_bps, 3),
            "maker_fill_ratio": round(maker_ratio, 4)
        }
