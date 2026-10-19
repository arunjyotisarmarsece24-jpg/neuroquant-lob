"""
Unit Tests for NeuroQuant-LOB Institutional FIX 4.4 Engine
===========================================================
Validates Tag-Value wire serialization, checksum verification, FIFO queue priority,
maker rebates vs taker fees, and sub-microsecond toxic sweep cancellation races.

Author: Arunjyoti Sarma (Research Scholar, IIT (BHU), Varanasi)
"""

import unittest
from neuroquant.execution.fix.protocol import (
    FixMessage,
    FixMsgType,
    FixSide,
    FixOrdType,
    FixOrdStatus,
    FixExecType,
    FixTag,
    FixProtocolEngine,
    SOH
)
from neuroquant.execution.fix.matching_simulator import (
    InstitutionalVenueSimulator,
    SimulatedOrderState
)


class TestFixProtocolEngine(unittest.TestCase):

    def test_fix_serialization_and_deserialization(self):
        msg = FixMessage(FixMsgType.NEW_ORDER_SINGLE)
        msg.set(FixTag.SenderCompID, "NEUROQUANT")
        msg.set(FixTag.TargetCompID, "CITADEL_CONNECT")
        msg.set(FixTag.MsgSeqNum, 42)
        msg.set(FixTag.ClOrdID, "CL_TEST_001")
        msg.set(FixTag.Symbol, "BTCUSDT")
        msg.set(FixTag.Side, FixSide.BUY.value)
        msg.set(FixTag.OrderQty, "1.5000")
        msg.set(FixTag.Price, "65000.00")
        msg.set(FixTag.AlphaSignal, "0.8421")

        wire_bytes = FixProtocolEngine.encode(msg)
        self.assertIsInstance(wire_bytes, bytes)
        self.assertTrue(wire_bytes.startswith(b"8=FIX.4.4\x019="))
        self.assertTrue(wire_bytes.endswith(b"\x01"))

        # Decode back
        decoded = FixProtocolEngine.decode(wire_bytes)
        self.assertEqual(decoded.msg_type, FixMsgType.NEW_ORDER_SINGLE.value)
        self.assertEqual(decoded.cl_ord_id, "CL_TEST_001")
        self.assertEqual(decoded.symbol, "BTCUSDT")
        self.assertEqual(decoded.side, FixSide.BUY.value)
        self.assertAlmostEqual(decoded.order_qty, 1.5)
        self.assertAlmostEqual(decoded.price, 65000.0)
        self.assertEqual(decoded.get(FixTag.AlphaSignal), "0.8421")

    def test_checksum_validation(self):
        msg = FixProtocolEngine.create_heartbeat("NQ_SYS", "DEST_SYS", 1)
        wire_bytes = FixProtocolEngine.encode(msg)

        # Valid decode passes cleanly
        decoded = FixProtocolEngine.decode(wire_bytes)
        self.assertEqual(decoded.msg_type, FixMsgType.HEARTBEAT.value)

        # Corrupted wire checksum fails
        corrupted = wire_bytes[:-4] + b"999\x01"
        with self.assertRaises(ValueError):
            FixProtocolEngine.decode(corrupted)

    def test_human_readable_formatting(self):
        msg = FixProtocolEngine.create_heartbeat("NQ", "DEST", 1)
        hr = msg.to_human_readable("|")
        self.assertIn("8=FIX.4.4|", hr)
        self.assertIn("|35=0|", hr)
        self.assertNotIn(SOH, hr)


class TestInstitutionalVenueSimulator(unittest.TestCase):

    def setUp(self):
        self.venue = InstitutionalVenueSimulator(
            venue_id="NASDAQ_TOTALVIEW",
            sender_comp_id="NASDAQ",
            target_comp_id="NEUROQUANT"
        )

    def test_passive_limit_order_enqueued(self):
        # Best market: Bid 64990, Ask 65010
        # We place a passive buy limit at 64995 with 5.0 contracts ahead
        order = FixProtocolEngine.create_new_order_single(
            cl_ord_id="ORD_PASSIVE_1",
            symbol="BTCUSDT",
            side=FixSide.BUY,
            order_qty=2.0,
            price=64995.0,
            micro_price=64998.0
        )

        reports = self.venue.submit_order(
            order,
            current_best_bid=64990.0,
            current_best_ask=65010.0,
            resting_depth_at_price=5.0
        )

        self.assertEqual(len(reports), 1)
        ack = reports[0]
        self.assertEqual(ack.exec_type, FixExecType.NEW.value)
        self.assertEqual(ack.ord_status, FixOrdStatus.NEW.value)
        self.assertEqual(ack.get_float(FixTag.QueueDepthAhead), 5.0)

        # Verify state
        state = list(self.venue.orders.values())[0]
        self.assertTrue(state.is_active())
        self.assertEqual(state.queue_depth_ahead, 5.0)
        self.assertEqual(state.leaves_qty, 2.0)
        self.assertEqual(state.cum_qty, 0.0)

    def test_marketable_cross_taker_execution(self):
        # Best ask is 65000. We send buy limit at 65005 (crosses spread)
        order = FixProtocolEngine.create_new_order_single(
            cl_ord_id="ORD_CROSS_1",
            symbol="BTCUSDT",
            side=FixSide.BUY,
            order_qty=1.0,
            price=65005.0
        )

        reports = self.venue.submit_order(
            order,
            current_best_bid=64995.0,
            current_best_ask=65000.0,
            resting_depth_at_price=0.0
        )

        # Expect 2 reports: 1 New ack + 1 Immediate Taker Fill
        self.assertEqual(len(reports), 2)
        ack = reports[0]
        fill = reports[1]

        self.assertEqual(ack.exec_type, FixExecType.NEW.value)
        self.assertEqual(fill.exec_type, FixExecType.FILL.value)
        self.assertEqual(fill.ord_status, FixOrdStatus.FILLED.value)
        self.assertAlmostEqual(fill.get_float(FixTag.LastPx), 65000.0)  # Filled at best ask

        state = list(self.venue.orders.values())[0]
        self.assertFalse(state.is_active())
        self.assertEqual(state.cum_qty, 1.0)
        self.assertEqual(state.leaves_qty, 0.0)
        self.assertGreater(state.total_fee, 0.0)  # Taker fee paid (> 0)

    def test_fifo_queue_advancement_and_maker_rebate(self):
        # Place buy order for 1.0 @ 65000 with 2.0 depth ahead
        order = FixProtocolEngine.create_new_order_single(
            cl_ord_id="ORD_MAKER_1",
            symbol="BTCUSDT",
            side=FixSide.BUY,
            order_qty=1.0,
            price=65000.0
        )
        self.venue.submit_order(order, current_best_bid=64990.0, current_best_ask=65010.0, resting_depth_at_price=2.0)
        state = list(self.venue.orders.values())[0]

        # 1. Trade 1: Sell 1.5 @ 65000. Consumes 1.5 of queue ahead (0.5 remains)
        rpts1 = self.venue.on_market_trade(trade_price=65000.0, trade_size=1.5, aggressor_side=FixSide.SELL)
        self.assertEqual(len(rpts1), 0)
        self.assertAlmostEqual(state.queue_depth_ahead, 0.5)
        self.assertEqual(state.cum_qty, 0.0)

        # 2. Trade 2: Sell 1.0 @ 65000. Consumes remaining 0.5 queue ahead + 0.5 of our order (Partial Fill)
        rpts2 = self.venue.on_market_trade(trade_price=65000.0, trade_size=1.0, aggressor_side=FixSide.SELL)
        self.assertEqual(len(rpts2), 1)
        self.assertEqual(rpts2[0].exec_type, FixExecType.PARTIAL_FILL.value)
        self.assertEqual(rpts2[0].ord_status, FixOrdStatus.PARTIALLY_FILLED.value)
        self.assertAlmostEqual(state.cum_qty, 0.5)
        self.assertAlmostEqual(state.leaves_qty, 0.5)
        self.assertLess(state.total_fee, 0.0)  # Rebate earned (< 0)

        # 3. Trade 3: Sell 1.0 @ 65000. Fills remaining 0.5 (Full Fill)
        rpts3 = self.venue.on_market_trade(trade_price=65000.0, trade_size=1.0, aggressor_side=FixSide.SELL)
        self.assertEqual(len(rpts3), 1)
        self.assertEqual(rpts3[0].exec_type, FixExecType.FILL.value)
        self.assertEqual(rpts3[0].ord_status, FixOrdStatus.FILLED.value)
        self.assertAlmostEqual(state.cum_qty, 1.0)
        self.assertAlmostEqual(state.leaves_qty, 0.0)

    def test_order_cancellation(self):
        order = FixProtocolEngine.create_new_order_single(
            cl_ord_id="ORD_TO_CANCEL",
            symbol="BTCUSDT",
            side=FixSide.BUY,
            order_qty=2.0,
            price=64900.0
        )
        self.venue.submit_order(order, 64800.0, 65000.0, resting_depth_at_price=10.0)

        cancel_msg = FixProtocolEngine.create_order_cancel_request(
            orig_cl_ord_id="ORD_TO_CANCEL",
            cl_ord_id="CXL_01",
            symbol="BTCUSDT",
            side=FixSide.BUY,
            order_qty=2.0
        )
        cxl_ack = self.venue.cancel_order(cancel_msg)
        self.assertEqual(cxl_ack.exec_type, FixExecType.CANCELED.value)
        self.assertEqual(cxl_ack.ord_status, FixOrdStatus.CANCELED.value)

        # Subsequent cancel should be rejected
        cxl_reject = self.venue.cancel_order(cancel_msg)
        self.assertEqual(cxl_reject.msg_type, FixMsgType.ORDER_CANCEL_REJECT.value)

    def test_toxic_sweep_race_cancel_wins(self):
        # We have an active quote. SNN detects toxicity.
        # Cancel latency (50 us) beats Toxic Sweep delay (200 us)
        order = FixProtocolEngine.create_new_order_single(
            cl_ord_id="ORD_TOXIC_RACE_1",
            symbol="BTCUSDT",
            side=FixSide.BUY,
            order_qty=5.0,
            price=65000.0
        )
        self.venue.submit_order(order, 64990.0, 65010.0, resting_depth_at_price=1.0)
        state = list(self.venue.orders.values())[0]

        cancel_won, rpts = self.venue.simulate_toxic_sweep_race(
            order_id=state.order_id,
            sweep_size=10.0,
            sweep_delay_us=200.0,
            cancel_latency_us=50.0
        )

        self.assertTrue(cancel_won)
        self.assertEqual(len(rpts), 1)
        self.assertEqual(rpts[0].ord_status, FixOrdStatus.CANCELED.value)
        self.assertEqual(state.cum_qty, 0.0)  # Saved from adverse execution!

    def test_toxic_sweep_race_sweep_wins(self):
        # Network delay is slow (300 us), toxic sweep hits in 100 us.
        order = FixProtocolEngine.create_new_order_single(
            cl_ord_id="ORD_TOXIC_RACE_2",
            symbol="BTCUSDT",
            side=FixSide.BUY,
            order_qty=3.0,
            price=65000.0
        )
        self.venue.submit_order(order, 64990.0, 65010.0, resting_depth_at_price=1.0)
        state = list(self.venue.orders.values())[0]

        cancel_won, rpts = self.venue.simulate_toxic_sweep_race(
            order_id=state.order_id,
            sweep_size=10.0,
            sweep_delay_us=100.0,
            cancel_latency_us=300.0
        )

        self.assertFalse(cancel_won)
        self.assertEqual(len(rpts), 1)
        self.assertEqual(rpts[0].ord_status, FixOrdStatus.FILLED.value)
        self.assertEqual(state.cum_qty, 3.0)  # Adversely filled!


if __name__ == "__main__":
    unittest.main()
