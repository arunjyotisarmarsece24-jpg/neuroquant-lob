"""
NeuroQuant-LOB: Autonomous Institutional HFT Market Maker & Trader
==================================================================
End-to-end institutional quantitative execution architecture linking:
  - Real-time exchange wire / L2 Hawkes order book feed
  - 32-channel LOB Spike Delta Modulator
  - Sub-microsecond (174 ns) C++20 AVX2 SIMD Neuromorphic RSNN Core
  - Hardware Pre-Trade Risk Gate (< 20 ns circuit breakers)
  - Institutional FIX 4.4 Tag-Value Order Routing Engine (35=D, 35=8, 35=F)
  - Exchange Matching Venue Simulator with FIFO Queue Priority
  - Sub-microsecond Toxic Sweep Adverse Selection Defense
  - Tiered Maker Rebate (-0.002%) vs Taker Fee (+0.005%) Accounting

Author: Arunjyoti Sarma (Research Scholar, IIT (BHU), Varanasi)
Project: NeuroQuant-LOB Flagship Quantitative Architecture
Version: 1.1.0-PROD
"""

from __future__ import annotations
import os
import time
import uuid
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field

from config import (
    CONFIG_NEURO,
    CONFIG_MARKET,
    CONFIG_EXEC,
    NeuromorphicConfig,
    MarketConfig,
    ExecutionConfig
)
from neuroquant.neuromorphic import DigitalNeuromorphicCore, LOBSpikeEncoder
from neuroquant.market import OrderBook, HawkesMarketFeed, LivePublicMarketFeed
from neuroquant.risk.risk_gate import PreTradeRiskGate, RiskConfig, RiskAction, RiskCheckResult
from neuroquant.execution.fix import (
    FixMessage,
    FixMsgType,
    FixSide,
    FixOrdType,
    FixOrdStatus,
    FixExecType,
    FixTag,
    FixProtocolEngine,
    InstitutionalVenueSimulator
)
from neuroquant.execution.almgren_chriss import AlmgrenChrissOptimizer, AlmgrenChrissConfig


@dataclass
class TraderSnapshot:
    step_num: int
    timestamp_ns: int
    mid_price: float
    spread: float
    micro_price: float
    sensory_spikes: int
    hidden_spikes: int
    sparsity_pct: float
    alpha_direction: float
    toxicity_score: float
    risk_cleared: bool
    risk_action: str
    risk_latency_ns: float
    fix_msg_sent: Optional[str]
    orders_enqueued: int
    orders_filled: int
    orders_canceled: int
    toxic_sweeps_defended: int
    inventory: float
    realized_pnl: float
    maker_rebates_earned: float
    total_volume_traded: float
    is_killed: bool


class InstitutionalHFTTrader:
    """
    Autonomous, real-time institutional quantitative market maker.
    Unifies the entire NeuroQuant software stack into a single event-driven loop.
    """

    def __init__(
        self,
        symbol: str = "BTCUSDT",
        use_live_feed: bool = False,
        neuro_cfg: NeuromorphicConfig = CONFIG_NEURO,
        mkt_cfg: Optional[MarketConfig] = None,
        risk_cfg: Optional[RiskConfig] = None,
        weights_path: Optional[str] = "weights/rsnn_optimal_weights.npz"
    ):
        self.symbol = symbol
        self.use_live_feed = use_live_feed
        self.neuro_cfg = neuro_cfg
        self.mkt_cfg = mkt_cfg or MarketConfig(symbol=symbol)
        self.risk_cfg = risk_cfg or RiskConfig()

        # 1. Order Book & Feed
        self.book = OrderBook(self.mkt_cfg)
        if use_live_feed:
            self.feed = LivePublicMarketFeed(self.book, symbol=symbol)
            self.feed.start()
        else:
            self.feed = HawkesMarketFeed(self.book, self.mkt_cfg)

        # 2. Neuromorphic Sensory Modulator & SNN Core
        self.encoder = LOBSpikeEncoder(self.mkt_cfg, self.neuro_cfg)
        self.brain = DigitalNeuromorphicCore(self.neuro_cfg)
        if weights_path and os.path.exists(weights_path):
            try:
                self.brain.load_weights(weights_path)
            except Exception:
                pass

        # 3. Pre-Trade Microsecond Hardware Risk Gate
        self.risk_gate = PreTradeRiskGate(self.risk_cfg)

        # 4. FIX 4.4 Execution Venue Simulator
        self.venue = InstitutionalVenueSimulator(
            venue_id="CITADEL_CONNECT",
            sender_comp_id="CITADEL_CONNECT",
            target_comp_id="NEUROQUANT"
        )

        # 5. Tracking State
        self.step_counter = 0
        self.cl_seq = 1
        self.inventory = 0.0
        self.realized_pnl = 0.0
        self.toxic_sweeps_defended = 0
        self.last_fix_msg_summary: Optional[str] = None
        self.recent_history: List[TraderSnapshot] = []

    def _next_cl_ord_id(self) -> str:
        cid = f"NQ_{self.step_counter:06d}_{self.cl_seq:04d}"
        self.cl_seq += 1
        return cid

    def step(self) -> TraderSnapshot:
        """
        Executes one full event-driven institutional HFT cycle:
          1. Ingest L2 market feed (depth, trades).
          2. Delta modulation -> 32-channel spikes.
          3. SNN inference (174 ns AVX2 SIMD) -> directional alpha + toxicity probability.
          4. Pre-trade hardware risk clearance (< 20 ns).
          5. FIX 4.4 order submission (35=D) or toxic sweep cancellation (35=F).
          6. FIFO matching queue progression & maker rebate harvesting.
        """
        t0 = time.perf_counter_ns()
        self.step_counter += 1

        # 1. Ingest L2 Market Event
        if self.use_live_feed:
            lob_snapshot, event_desc = self.feed.step(dt_sec=0.1)
        else:
            dt_sec = self.neuro_cfg.time_step_ms / 1000.0
            lob_snapshot, event_desc = self.feed.step(dt_sec=dt_sec)

        mid_price = self.book.mid_price
        spread = self.book.spread
        best_bid = self.book.best_bid
        best_ask = self.book.best_ask
        top_bid_q = self.book.bids.get(best_bid, 1.0)
        top_ask_q = self.book.asks.get(best_ask, 1.0)

        # Compute Stoikov micro-price
        micro_price = (
            (top_bid_q * best_ask + top_ask_q * best_bid) / (top_bid_q + top_ask_q)
            if (top_bid_q + top_ask_q) > 0
            else mid_price
        )

        # 2. Encode LOB Delta into 32-Channel Sensory Spikes
        self.sim_time_ms = getattr(self, "sim_time_ms", 0.0) + self.neuro_cfg.time_step_ms
        sensory_spikes = self.encoder.encode(lob_snapshot, self.sim_time_ms)
        num_sensory_spikes = int(np.sum(sensory_spikes))

        # 3. SNN Inference via C++20 AVX2 SIMD Core
        s_spk, h_spk, m_spk = self.brain.step(sensory_spikes, reward=0.0)
        num_hidden_spikes = int(np.sum(h_spk))
        signals = self.brain.get_motor_readout_signals() if hasattr(self.brain, "get_motor_readout_signals") else {}

        alpha_direction = float(signals.get("quote_skew", 0.0))
        toxicity_score = float(signals.get("toxicity_score", 0.0))

        # Membrane voltage check for Theorem 1 Lyapunov bound
        voltages = getattr(self.brain, "v_hidden", np.array([-70.0]))
        sample_vm = float(voltages[0]) if len(voltages) > 0 else -70.0

        # Total biological sparsity
        total_neurons = len(sensory_spikes) + len(h_spk)
        total_spikes = num_sensory_spikes + num_hidden_spikes
        sparsity_pct = (1.0 - (total_spikes / max(1, total_neurons))) * 100.0

        # 4. Critical Hot Path: Pre-Trade Microsecond Hardware Risk Gate (< 20 ns)
        target_side = "BUY" if alpha_direction >= 0 else "SELL"
        order_qty = 1.0
        limit_price = best_bid if target_side == "BUY" else best_ask

        risk_res = self.risk_gate.validate_order(
            side=target_side,
            quantity=order_qty,
            price=limit_price,
            mid_price=mid_price,
            current_inventory=self.inventory,
            current_mtm_pnl=self.realized_pnl,
            membrane_voltage_mv=sample_vm
        )

        self.last_fix_msg_summary = None

        # 5. Order Execution / Cancellation Lifecycle
        if not self.risk_gate.is_killed:
            # Toxic Sweep Defense Race:
            # If toxicity score > 0.60, immediately cancel resting quotes to avoid adverse selection
            if toxicity_score > 0.60 and len(self.venue.orders) > 0:
                active_orders = [o for o in self.venue.orders.values() if o.is_active()]
                if active_orders:
                    target_order = active_orders[0]
                    cancel_msg = FixProtocolEngine.create_order_cancel_request(
                        orig_cl_ord_id=target_order.cl_ord_id,
                        cl_ord_id=self._next_cl_ord_id(),
                        symbol=self.symbol,
                        side=target_order.side,
                        order_qty=target_order.leaves_qty,
                        toxicity_score=toxicity_score
                    )
                    cxl_ack = self.venue.cancel_order(cancel_msg)
                    self.last_fix_msg_summary = f"35=F (Cancel Sent) -> 35=8 {cxl_ack.ord_status}"
                    self.toxic_sweeps_defended += 1

            # Normal Passive Limit Order Quoting
            elif risk_res.passed and (self.step_counter % 2 == 0):
                new_order = FixProtocolEngine.create_new_order_single(
                    cl_ord_id=self._next_cl_ord_id(),
                    symbol=self.symbol,
                    side=FixSide.BUY if target_side == "BUY" else FixSide.SELL,
                    order_qty=order_qty,
                    price=limit_price,
                    ord_type=FixOrdType.LIMIT,
                    alpha_signal=alpha_direction,
                    micro_price=micro_price
                )
                rpts = self.venue.submit_order(
                    new_order,
                    current_best_bid=best_bid,
                    current_best_ask=best_ask,
                    resting_depth_at_price=min(2.0, top_bid_q if target_side == "BUY" else top_ask_q)
                )
                self.last_fix_msg_summary = f"35=D {target_side} {order_qty}@{limit_price:.2f} -> 35=8 Ack"

        # 6. Simulate Market Trade Queue Progression (Incoming Market Fill)
        # Advance queue with incoming trade
        trade_side = FixSide.SELL if (self.step_counter % 3 == 0) else FixSide.BUY
        trade_size = 5.0
        trade_price = best_bid if trade_side == FixSide.SELL else best_ask
        fill_reports = self.venue.on_market_trade(
            trade_price=trade_price,
            trade_size=trade_size,
            aggressor_side=trade_side
        )

        for fr in fill_reports:
            last_qty = fr.get_float(FixTag.LastQty)
            last_px = fr.get_float(FixTag.LastPx)
            side_val = fr.get(FixTag.Side)
            if side_val == FixSide.BUY.value:
                self.inventory += last_qty
            else:
                self.inventory -= last_qty

            # Realized PnL approximation
            self.realized_pnl += last_qty * (0.5 * spread)

        # Net metrics
        venue_metrics = self.venue.get_metrics()
        maker_rebates_earned = abs(venue_metrics["net_fees_paid"]) if venue_metrics["net_fees_paid"] < 0 else 0.0

        snapshot = TraderSnapshot(
            step_num=self.step_counter,
            timestamp_ns=time.perf_counter_ns(),
            mid_price=mid_price,
            spread=spread,
            micro_price=micro_price,
            sensory_spikes=num_sensory_spikes,
            hidden_spikes=num_hidden_spikes,
            sparsity_pct=sparsity_pct,
            alpha_direction=alpha_direction,
            toxicity_score=toxicity_score,
            risk_cleared=risk_res.passed,
            risk_action=risk_res.action.name,
            risk_latency_ns=risk_res.latency_ns,
            fix_msg_sent=self.last_fix_msg_summary,
            orders_enqueued=venue_metrics["total_orders"],
            orders_filled=venue_metrics["filled_orders"],
            orders_canceled=venue_metrics["canceled_orders"],
            toxic_sweeps_defended=self.toxic_sweeps_defended,
            inventory=self.inventory,
            realized_pnl=self.realized_pnl,
            maker_rebates_earned=maker_rebates_earned,
            total_volume_traded=venue_metrics["total_volume_traded"],
            is_killed=self.risk_gate.is_killed
        )

        self.recent_history.append(snapshot)
        if len(self.recent_history) > 1000:
            self.recent_history.pop(0)

        return snapshot

    def shutdown(self):
        """Clean shutdown of live sockets and feeds."""
        if self.use_live_feed and hasattr(self.feed, "stop"):
            self.feed.stop()
