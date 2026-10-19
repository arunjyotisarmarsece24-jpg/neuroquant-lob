"""
NeuroQuant-LOB: Institutional Matching Venue & FIX Execution Simulator
======================================================================
High-fidelity institutional exchange matching engine modeling:
  - Strict FIFO order book queue priority
  - Level-2 depth tracking ahead of resting orders (QueueDepthAhead)
  - Partial and complete fills with realistic volume degradation
  - Maker rebates (-0.002%) vs Taker fees (+0.005%)
  - Sub-microsecond adverse selection race condition (Toxic Sweep vs Cancel)

Author: Arunjyoti Sarma (Research Scholar, IIT (BHU), Varanasi)
Project: NeuroQuant-LOB Flagship Quantitative Architecture
Version: 1.1.0-PROD
"""

from __future__ import annotations
import uuid
import time
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field

from .protocol import (
    FixMessage,
    FixMsgType,
    FixSide,
    FixOrdType,
    FixOrdStatus,
    FixExecType,
    FixProtocolEngine
)


MAKER_REBATE_BPS = -0.002  # -0.2 bps rebate for passive liquidity provision
TAKER_FEE_BPS = 0.005      # +0.5 bps fee for aggressive liquidity removal


@dataclass
class SimulatedOrderState:
    order_id: str
    cl_ord_id: str
    symbol: str
    side: FixSide
    price: float
    order_qty: float
    cum_qty: float = 0.0
    leaves_qty: float = 0.0
    avg_px: float = 0.0
    ord_status: FixOrdStatus = FixOrdStatus.NEW
    queue_depth_ahead: float = 0.0
    is_passive: bool = True
    total_fee: float = 0.0  # negative is rebate earned
    placed_timestamp_ns: int = 0
    history: List[str] = field(default_factory=list)

    def is_active(self) -> bool:
        return self.ord_status in (FixOrdStatus.NEW, FixOrdStatus.PARTIALLY_FILLED)


class InstitutionalVenueSimulator:
    """
    Simulates a Tier-1 institutional electronic exchange matching venue (CME / Nasdaq / Binance).
    Tracks active orders with exact queue priority, volume progression, and FIX execution reports.
    """

    def __init__(
        self,
        venue_id: str = "CITADEL_CONNECT",
        sender_comp_id: str = "CITADEL_CONNECT",
        target_comp_id: str = "NEUROQUANT"
    ):
        self.venue_id = venue_id
        self.sender_comp_id = sender_comp_id
        self.target_comp_id = target_comp_id
        self.orders: Dict[str, SimulatedOrderState] = {}
        self.cl_to_order_id: Dict[str, str] = {}
        self.seq_num: int = 1
        self.exec_counter: int = 1
        self.total_pnl: float = 0.0
        self.total_fees_paid: float = 0.0
        self.total_volume_traded: float = 0.0

    def _next_exec_id(self) -> str:
        eid = f"EXEC_{self.venue_id}_{self.exec_counter:07d}"
        self.exec_counter += 1
        return eid

    def _next_seq(self) -> int:
        seq = self.seq_num
        self.seq_num += 1
        return seq

    def submit_order(
        self,
        new_order: FixMessage,
        current_best_bid: float = 0.0,
        current_best_ask: float = float("inf"),
        resting_depth_at_price: float = 0.0
    ) -> List[FixMessage]:
        """
        Processes an incoming 35=D NewOrderSingle.
        Returns a list of 35=8 ExecutionReports (e.g. New Ack, followed by Taker fill if marketable).
        """
        cl_ord_id = new_order.cl_ord_id or str(uuid.uuid4())[:8]
        symbol = new_order.symbol or "BTCUSDT"
        side_val = new_order.side or FixSide.BUY.value
        side = FixSide(side_val)
        price = new_order.price
        qty = new_order.order_qty
        ord_type_val = new_order.get(40, FixOrdType.LIMIT.value)

        order_id = f"ORD_{uuid.uuid4().hex[:10].upper()}"

        state = SimulatedOrderState(
            order_id=order_id,
            cl_ord_id=cl_ord_id,
            symbol=symbol,
            side=side,
            price=price,
            order_qty=qty,
            leaves_qty=qty,
            cum_qty=0.0,
            avg_px=0.0,
            ord_status=FixOrdStatus.NEW,
            queue_depth_ahead=resting_depth_at_price,
            placed_timestamp_ns=time.perf_counter_ns()
        )

        self.orders[order_id] = state
        self.cl_to_order_id[cl_ord_id] = order_id
        reports: List[FixMessage] = []

        # 1. Immediate Acceptance Report (35=8, ExecType=0, OrdStatus=0)
        ack_report = FixProtocolEngine.create_execution_report(
            order_id=order_id,
            cl_ord_id=cl_ord_id,
            exec_id=self._next_exec_id(),
            exec_type=FixExecType.NEW,
            ord_status=FixOrdStatus.NEW,
            symbol=symbol,
            side=side,
            order_qty=qty,
            leaves_qty=qty,
            cum_qty=0.0,
            avg_px=0.0,
            price=price,
            sender_comp_id=self.sender_comp_id,
            target_comp_id=self.target_comp_id,
            seq_num=self._next_seq(),
            queue_depth_ahead=resting_depth_at_price,
            text="Order accepted and enqueued in venue L2 book"
        )
        reports.append(ack_report)
        state.history.append("NEW")

        # 2. Check if marketable (crosses the spread immediately -> Taker execution)
        is_marketable = False
        fill_price = price

        if ord_type_val == FixOrdType.MARKET.value:
            is_marketable = True
            fill_price = current_best_ask if side == FixSide.BUY else current_best_bid
        elif side == FixSide.BUY and current_best_ask > 0 and price >= current_best_ask:
            is_marketable = True
            fill_price = current_best_ask
        elif side == FixSide.SELL and current_best_bid > 0 and price <= current_best_bid:
            is_marketable = True
            fill_price = current_best_bid

        if is_marketable:
            state.is_passive = False
            state.leaves_qty = 0.0
            state.cum_qty = qty
            state.avg_px = fill_price
            state.ord_status = FixOrdStatus.FILLED

            # Taker fee calculation
            notional = qty * fill_price
            fee = notional * (TAKER_FEE_BPS / 100.0)
            state.total_fee = fee
            self.total_fees_paid += fee
            self.total_volume_traded += notional

            fill_report = FixProtocolEngine.create_execution_report(
                order_id=order_id,
                cl_ord_id=cl_ord_id,
                exec_id=self._next_exec_id(),
                exec_type=FixExecType.FILL,
                ord_status=FixOrdStatus.FILLED,
                symbol=symbol,
                side=side,
                order_qty=qty,
                leaves_qty=0.0,
                cum_qty=qty,
                avg_px=fill_price,
                last_px=fill_price,
                last_qty=qty,
                price=price,
                sender_comp_id=self.sender_comp_id,
                target_comp_id=self.target_comp_id,
                seq_num=self._next_seq(),
                text=f"Marketable cross: Taker fill @ {fill_price:.2f} (Fee: ${fee:.4f})"
            )
            reports.append(fill_report)
            state.history.append("FILLED_TAKER")

        return reports

    def on_market_trade(
        self,
        trade_price: float,
        trade_size: float,
        aggressor_side: FixSide
    ) -> List[FixMessage]:
        """
        Advances the order book queue as trades execute on the exchange.
        If an order's queue depth ahead is cleared, incoming volume fills the order (Maker).
        """
        reports: List[FixMessage] = []

        for order_id, state in list(self.orders.items()):
            if not state.is_active():
                continue

            # Trade matches our resting quote if:
            # - Our order is BUY and aggressor is SELL (selling into our bid) at or below our price
            # - Our order is SELL and aggressor is BUY (buying into our ask) at or above our price
            can_match = False
            if state.side == FixSide.BUY and aggressor_side == FixSide.SELL and trade_price <= state.price:
                can_match = True
            elif state.side == FixSide.SELL and aggressor_side == FixSide.BUY and trade_price >= state.price:
                can_match = True

            if not can_match:
                continue

            # Check FIFO queue position ahead
            if state.queue_depth_ahead > 0:
                if trade_size <= state.queue_depth_ahead:
                    # Trade only consumes queue ahead of us
                    state.queue_depth_ahead -= trade_size
                    continue
                else:
                    # Trade consumes remaining queue ahead and remaining volume touches our order
                    available_fill = trade_size - state.queue_depth_ahead
                    state.queue_depth_ahead = 0.0
            else:
                available_fill = trade_size

            # Fill our order
            fill_qty = min(available_fill, state.leaves_qty)
            if fill_qty <= 0:
                continue

            # Update order state
            new_cum_qty = state.cum_qty + fill_qty
            state.avg_px = ((state.avg_px * state.cum_qty) + (state.price * fill_qty)) / new_cum_qty
            state.cum_qty = new_cum_qty
            state.leaves_qty -= fill_qty

            is_full_fill = state.leaves_qty <= 1e-6
            exec_type = FixExecType.FILL if is_full_fill else FixExecType.PARTIAL_FILL
            ord_status = FixOrdStatus.FILLED if is_full_fill else FixOrdStatus.PARTIALLY_FILLED
            state.ord_status = ord_status

            # Maker rebate calculation (negative fee)
            fill_notional = fill_qty * state.price
            rebate = fill_notional * (abs(MAKER_REBATE_BPS) / 100.0)
            state.total_fee -= rebate  # negative fee = earned rebate
            self.total_fees_paid -= rebate
            self.total_volume_traded += fill_notional

            rpt = FixProtocolEngine.create_execution_report(
                order_id=state.order_id,
                cl_ord_id=state.cl_ord_id,
                exec_id=self._next_exec_id(),
                exec_type=exec_type,
                ord_status=ord_status,
                symbol=state.symbol,
                side=state.side,
                order_qty=state.order_qty,
                leaves_qty=state.leaves_qty,
                cum_qty=state.cum_qty,
                avg_px=state.avg_px,
                last_px=state.price,
                last_qty=fill_qty,
                price=state.price,
                sender_comp_id=self.sender_comp_id,
                target_comp_id=self.target_comp_id,
                seq_num=self._next_seq(),
                text=f"Passive match: Maker {'Full' if is_full_fill else 'Partial'} Fill (Rebate: +${rebate:.4f})"
            )
            reports.append(rpt)
            state.history.append("FILLED_MAKER" if is_full_fill else "PARTIAL_MAKER")

        return reports

    def cancel_order(self, cancel_request: FixMessage) -> FixMessage:
        """
        Processes a 35=F OrderCancelRequest.
        Returns a 35=8 ExecutionReport with OrdStatus=4 (Canceled) or 35=9 Reject.
        """
        orig_cl_id = cancel_request.get(41) or cancel_request.cl_ord_id
        order_id = self.cl_to_order_id.get(orig_cl_id)

        if order_id is None or order_id not in self.orders:
            # Order not found or already terminal
            rej = FixMessage(FixMsgType.ORDER_CANCEL_REJECT)
            rej.set(37, order_id or "UNKNOWN")
            rej.set(11, cancel_request.cl_ord_id or "UNKNOWN")
            rej.set(41, orig_cl_id or "UNKNOWN")
            rej.set(39, FixOrdStatus.REJECTED.value)
            rej.set(434, "1")  # CxlRejResponseTo = Order Cancel Request
            rej.set(58, "Order not active or not found")
            return rej

        state = self.orders[order_id]
        if not state.is_active():
            rej = FixMessage(FixMsgType.ORDER_CANCEL_REJECT)
            rej.set(37, state.order_id)
            rej.set(11, cancel_request.cl_ord_id or state.cl_ord_id)
            rej.set(41, orig_cl_id)
            rej.set(39, state.ord_status.value)
            rej.set(434, "1")
            rej.set(58, f"Too late to cancel: Order status is {state.ord_status.name}")
            return rej

        state.ord_status = FixOrdStatus.CANCELED
        state.leaves_qty = 0.0
        state.history.append("CANCELED")

        rpt = FixProtocolEngine.create_execution_report(
            order_id=state.order_id,
            cl_ord_id=state.cl_ord_id,
            exec_id=self._next_exec_id(),
            exec_type=FixExecType.CANCELED,
            ord_status=FixOrdStatus.CANCELED,
            symbol=state.symbol,
            side=state.side,
            order_qty=state.order_qty,
            leaves_qty=0.0,
            cum_qty=state.cum_qty,
            avg_px=state.avg_px,
            price=state.price,
            sender_comp_id=self.sender_comp_id,
            target_comp_id=self.target_comp_id,
            seq_num=self._next_seq(),
            text="Canceled successfully upon client request"
        )
        return rpt

    def simulate_toxic_sweep_race(
        self,
        order_id: str,
        sweep_size: float,
        sweep_delay_us: float,
        cancel_latency_us: float
    ) -> Tuple[bool, List[FixMessage]]:
        """
        Simulates the critical HFT microsecond race condition:
        An aggressive toxic sweep is launched against our price level.
        Our SNN toxicity detector signals an emergency 35=F cancel request.

        If cancel_latency_us < sweep_delay_us:
          -> Cancel reaches matching engine first. Order successfully canceled! No adverse fill.
        Else:
          -> Toxic sweep arrives first. Order is filled passively at stale price with adverse selection!

        Returns (cancel_won_race, execution_reports).
        """
        if order_id not in self.orders:
            raise KeyError(f"Order {order_id} not found in venue.")

        state = self.orders[order_id]
        if not state.is_active():
            return False, []

        reports: List[FixMessage] = []
        if cancel_latency_us < sweep_delay_us:
            # CANCEL WINS THE RACE
            cancel_msg = FixProtocolEngine.create_order_cancel_request(
                orig_cl_ord_id=state.cl_ord_id,
                cl_ord_id=f"CXL_{uuid.uuid4().hex[:6]}",
                symbol=state.symbol,
                side=state.side,
                order_qty=state.leaves_qty,
                toxicity_score=0.95
            )
            cxl_report = self.cancel_order(cancel_msg)
            reports.append(cxl_report)
            return True, reports
        else:
            # TOXIC SWEEP WINS THE RACE (Adverse fill)
            # The toxic sweep consumes all queue ahead and hits our resting volume
            aggressor_side = FixSide.SELL if state.side == FixSide.BUY else FixSide.BUY
            state.queue_depth_ahead = 0.0
            fill_reports = self.on_market_trade(
                trade_price=state.price,
                trade_size=sweep_size,
                aggressor_side=aggressor_side
            )
            return False, fill_reports

    def get_metrics(self) -> Dict[str, Any]:
        """Returns comprehensive venue execution summary."""
        active_count = sum(1 for o in self.orders.values() if o.is_active())
        filled_count = sum(1 for o in self.orders.values() if o.ord_status == FixOrdStatus.FILLED)
        canceled_count = sum(1 for o in self.orders.values() if o.ord_status == FixOrdStatus.CANCELED)

        return {
            "total_orders": len(self.orders),
            "active_orders": active_count,
            "filled_orders": filled_count,
            "canceled_orders": canceled_count,
            "total_volume_traded": self.total_volume_traded,
            "net_fees_paid": self.total_fees_paid,  # negative means net rebates earned
            "maker_rebate_bps": MAKER_REBATE_BPS,
            "taker_fee_bps": TAKER_FEE_BPS
        }
