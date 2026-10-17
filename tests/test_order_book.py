"""
Unit Tests: Order Book & Hawkes Feed Engine
===========================================
"""

import unittest
from config import MarketConfig
from neuroquant.market.order_book import OrderBook
from neuroquant.market.feed_simulator import HawkesMarketFeed

class TestOrderBook(unittest.TestCase):
    def setUp(self):
        self.cfg = MarketConfig()
        self.book = OrderBook(self.cfg)

    def test_book_initialization(self):
        self.assertGreater(self.book.best_ask, self.book.best_bid)
        self.assertAlmostEqual(self.book.spread, self.book.best_ask - self.book.best_bid, places=2)
        self.assertAlmostEqual(self.book.mid_price, (self.book.best_ask + self.book.best_bid) / 2.0, places=2)

    def test_add_and_cancel_order(self):
        initial_bid_vol = self.book.bids[self.book.best_bid]
        self.book.add_limit_order('BUY', self.book.best_bid, 15.0)
        self.assertAlmostEqual(self.book.bids[self.book.best_bid], initial_bid_vol + 15.0, places=5)
        
        self.book.cancel_order('BUY', self.book.best_bid, 15.0)
        self.assertAlmostEqual(self.book.bids[self.book.best_bid], initial_bid_vol, places=5)

    def test_market_order_fill(self):
        ask_price = self.book.best_ask
        ask_volume = self.book.asks[ask_price]
        
        # Execute buy order smaller than top ask volume
        fills = self.book.match_market_order('BUY', 5.0)
        self.assertEqual(len(fills), 1)
        self.assertEqual(fills[0][0], ask_price)
        self.assertEqual(fills[0][1], 5.0)
        self.assertEqual(self.book.asks[ask_price], ask_volume - 5.0)

    def test_hawkes_feed_stepping(self):
        feed = HawkesMarketFeed(self.book, self.cfg)
        for _ in range(20):
            snapshot, desc = feed.step(dt_sec=0.01)
            self.assertIn("mid_price", snapshot)
            self.assertIn("bids", snapshot)
            self.assertIn("asks", snapshot)

if __name__ == "__main__":
    unittest.main()
