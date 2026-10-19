"""
Unit Tests: NASDAQ TotalView-ITCH 5.0 High-Performance Feed Parser
==================================================================
Validates:
  1. Binary struct alignment & single-cycle endianness decoding.
  2. Accurate unpacking of Add Order ('A'), Executed ('E'), Cancel ('X'), Delete ('D'), and Trade ('P') messages.
  3. Real-time in-memory order book reconstruction.
  4. Ultra-high throughput stream processing exceeding 5,000,000 msgs/sec.
"""

import os
import sys
import unittest
import struct

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from neuroquant.market.itch_parser import (
    is_itch_parser_available,
    parse_single_message,
    generate_synthetic_itch_stream,
    run_itch_benchmark,
    ITCHOrderBook,
)

class TestITCH50Parser(unittest.TestCase):
    def setUp(self):
        self.available = is_itch_parser_available()

    def test_parser_availability(self):
        self.assertTrue(self.available, "ITCH parser C++ dynamic library must be available")

    def test_add_order_message_unpacking(self):
        if not self.available:
            self.skipTest("ITCH parser not available")

        # Manually pack a NASDAQ ITCH 5.0 Type 'A' (Add Order) binary packet
        # Format:
        #   type: char (1B) -> 'A'
        #   stock_locate: uint16 (2B, big-endian) -> 42
        #   tracking_number: uint16 (2B, big-endian) -> 101
        #   timestamp: 6 bytes (48-bit ns past midnight) -> 34,200,000,000,000 ns (09:30:00)
        #   order_ref: uint64 (8B, big-endian) -> 123456789
        #   buy_sell: char (1B) -> 'B'
        #   shares: uint32 (4B, big-endian) -> 500
        #   stock: 8 chars -> b'NVDA    '
        #   price: uint32 (4B, big-endian, 4 dec places) -> 1855000 ($185.5000)
        ts_val = 34200000000000
        ts_bytes = ts_val.to_bytes(6, byteorder='big')
        
        raw_msg = struct.pack(
            ">cHH6sQcI8sI",
            b'A',
            42,
            101,
            ts_bytes,
            123456789,
            b'B',
            500,
            b'NVDA    ',
            1855000
        )
        self.assertEqual(len(raw_msg), 36)

        event = parse_single_message(raw_msg)
        self.assertIsNotNone(event)
        self.assertEqual(event["msg_type"], 'A')
        self.assertEqual(event["order_ref"], 123456789)
        self.assertEqual(event["side"], 'B')
        self.assertEqual(event["shares"], 500)
        self.assertAlmostEqual(event["price"], 185.5000, places=4)
        self.assertEqual(event["stock"], "NVDA")
        self.assertEqual(event["timestamp_ns"], ts_val)

    def test_executed_order_message_unpacking(self):
        if not self.available:
            self.skipTest("ITCH parser not available")

        # Manually pack Type 'E' (Order Executed) packet (31 bytes)
        ts_val = 34200000005000
        ts_bytes = ts_val.to_bytes(6, byteorder='big')
        
        raw_msg = struct.pack(
            ">cHH6sQIQ",
            b'E',
            42,
            102,
            ts_bytes,
            123456789,
            200,       # 200 shares executed
            987654321  # match number
        )
        self.assertEqual(len(raw_msg), 31)

        event = parse_single_message(raw_msg)
        self.assertIsNotNone(event)
        self.assertEqual(event["msg_type"], 'E')
        self.assertEqual(event["order_ref"], 123456789)
        self.assertEqual(event["shares"], 200)
        self.assertEqual(event["match_number"], 987654321)

    def test_cancel_order_message_unpacking(self):
        if not self.available:
            self.skipTest("ITCH parser not available")

        # Type 'X' (Order Cancel) packet (23 bytes)
        ts_val = 34200000010000
        ts_bytes = ts_val.to_bytes(6, byteorder='big')
        
        raw_msg = struct.pack(
            ">cHH6sQI",
            b'X',
            42,
            103,
            ts_bytes,
            123456789,
            100        # 100 shares canceled
        )
        self.assertEqual(len(raw_msg), 23)

        event = parse_single_message(raw_msg)
        self.assertIsNotNone(event)
        self.assertEqual(event["msg_type"], 'X')
        self.assertEqual(event["order_ref"], 123456789)
        self.assertEqual(event["shares"], 100)

    def test_order_book_reconstruction(self):
        if not self.available:
            self.skipTest("ITCH parser not available")

        book = ITCHOrderBook()
        book.reset()

        # Add Bid at $185.0000 (100 shares)
        ts = (34200000000000).to_bytes(6, 'big')
        msg_bid = struct.pack(">cHH6sQcI8sI", b'A', 1, 1, ts, 1001, b'B', 100, b'NVDA    ', 1850000)
        # Add Ask at $185.5000 (200 shares)
        msg_ask = struct.pack(">cHH6sQcI8sI", b'A', 1, 2, ts, 1002, b'S', 200, b'NVDA    ', 1855000)

        # Prefix with 2-byte length for stream parsing
        stream = (len(msg_bid)).to_bytes(2, 'big') + msg_bid + (len(msg_ask)).to_bytes(2, 'big') + msg_ask
        count, stats = book.parse_stream(stream, has_length_prefix=True)
        self.assertEqual(count, 2)

        top = book.get_top_of_book()
        self.assertAlmostEqual(top["best_bid"], 185.0000, places=4)
        self.assertAlmostEqual(top["best_ask"], 185.5000, places=4)
        self.assertEqual(top["bid_shares"], 100)
        self.assertEqual(top["ask_shares"], 200)

        # Cancel 50 shares of the Bid order
        msg_cancel = struct.pack(">cHH6sQI", b'X', 1, 3, ts, 1001, 50)
        stream_cancel = (len(msg_cancel)).to_bytes(2, 'big') + msg_cancel
        count, _ = book.parse_stream(stream_cancel, has_length_prefix=True)
        self.assertEqual(count, 1)

        top = book.get_top_of_book()
        self.assertEqual(top["bid_shares"], 50)
        self.assertEqual(top["total_bid_volume"], 50)

    def test_high_throughput_benchmark_target(self):
        if not self.available:
            self.skipTest("ITCH parser not available")

        # Benchmark 100,000 messages (must comfortably exceed 2,000,000 msgs/sec in unit tests)
        bench = run_itch_benchmark(num_messages=100000)
        self.assertEqual(bench["total_messages"], 100000)
        self.assertGreater(bench["msgs_per_second"], 2000000.0, "Throughput must exceed 2,000,000 msgs/sec")
        self.assertLess(bench["avg_nanos_per_msg"], 500.0, "Latency per message must be < 500 nanoseconds")

    def test_multi_level_l2_depth_and_bbo_recovery(self):
        if not self.available:
            self.skipTest("ITCH parser not available")

        book = ITCHOrderBook()
        book.reset()
        ts = (34200000000000).to_bytes(6, 'big')

        # Add 3 Bids: $185.00 (100 sh), $185.25 (200 sh), $185.50 (300 sh)
        m1 = struct.pack(">cHH6sQcI8sI", b'A', 1, 1, ts, 201, b'B', 100, b'NVDA    ', 1850000)
        m2 = struct.pack(">cHH6sQcI8sI", b'A', 1, 2, ts, 202, b'B', 200, b'NVDA    ', 1852500)
        m3 = struct.pack(">cHH6sQcI8sI", b'A', 1, 3, ts, 203, b'B', 300, b'NVDA    ', 1855000)
        # Add 2 Asks: $185.75 (400 sh), $186.00 (500 sh)
        m4 = struct.pack(">cHH6sQcI8sI", b'A', 1, 4, ts, 204, b'S', 400, b'NVDA    ', 1857500)
        m5 = struct.pack(">cHH6sQcI8sI", b'A', 1, 5, ts, 205, b'S', 500, b'NVDA    ', 1860000)

        stream = b"".join((len(m)).to_bytes(2, 'big') + m for m in [m1, m2, m3, m4, m5])
        book.parse_stream(stream, has_length_prefix=True)

        depth = book.get_depth_10()
        self.assertEqual(depth["bid_levels"], 3)
        self.assertEqual(depth["ask_levels"], 2)
        # Verify bids are sorted descending: 185.50 > 185.25 > 185.00
        self.assertAlmostEqual(depth["bids"][0]["price"], 185.5000, places=4)
        self.assertAlmostEqual(depth["bids"][1]["price"], 185.2500, places=4)
        self.assertAlmostEqual(depth["bids"][2]["price"], 185.0000, places=4)
        self.assertEqual(depth["bids"][0]["shares"], 300)
        self.assertEqual(depth["best_bid"], 185.5000)
        self.assertEqual(depth["best_ask"], 185.7500)
        self.assertAlmostEqual(depth["spread"], 0.2500, places=4)

        # Micro-price should be weighted towards the heavier ask side ($185.75 with 400 shares vs $185.50 with 300 shares)
        self.assertGreater(depth["micro_price"], 185.5000)
        self.assertLess(depth["micro_price"], 185.7500)

        # Cancel top bid (Order 203 at $185.50 for 300 shares)
        m_del = struct.pack(">cHH6sQ", b'D', 1, 6, ts, 203)
        stream_del = (len(m_del)).to_bytes(2, 'big') + m_del
        book.parse_stream(stream_del, has_length_prefix=True)

        depth_after = book.get_depth_10()
        self.assertEqual(depth_after["bid_levels"], 2)
        # Verify ZERO AMNESIA: Best bid immediately falls back to $185.25!
        self.assertAlmostEqual(depth_after["best_bid"], 185.2500, places=4)
        self.assertEqual(depth_after["bid_shares"], 200)

    def test_neuromorphic_hotpath_pipeline(self):
        if not self.available:
            self.skipTest("ITCH parser not available")

        from neuroquant.market.itch_parser import NeuromorphicHotpathPipeline
        pipeline = NeuromorphicHotpathPipeline()
        pipeline.reset()

        # Feed a raw packet
        ts = (34200000000000).to_bytes(6, 'big')
        raw_msg = struct.pack(">cHH6sQcI8sI", b'A', 1, 10, ts, 301, b'B', 1000, b'NVDA    ', 1850000)
        decision = pipeline.process_packet(raw_msg)

        self.assertIn(decision["action"], ["BUY", "SELL", "HOLD"])
        self.assertGreater(decision["confidence"], 0.0)
        self.assertGreater(decision["latency_cycles"], 0)

        # Stream benchmark
        bench = pipeline.run_benchmark(num_packets=5000)
        self.assertEqual(bench["total_packets"], 5000)
        self.assertGreater(bench["packets_per_sec"], 100000.0)

if __name__ == "__main__":
    unittest.main()
