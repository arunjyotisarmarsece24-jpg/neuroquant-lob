"""
Unit Tests: Quantitative Inventory Risk & Asymmetric Quote Fading
==================================================================
Verifies that the market maker aggressively unwinds inventory risk
and completely withdraws bids/asks when nearing risk boundaries.
"""

import unittest
from config import ExecutionConfig, MarketConfig
from neuroquant.market.order_book import OrderBook
from neuroquant.market.execution_engine import ExecutionEngine

class TestInventoryRiskEngine(unittest.TestCase):
    def setUp(self):
        self.mkt_cfg = MarketConfig()
        self.exec_cfg = ExecutionConfig(max_inventory=50)
        self.book = OrderBook(self.mkt_cfg)
        self.engine = ExecutionEngine(self.book, self.exec_cfg, self.mkt_cfg)

    def test_balanced_two_sided_quotes(self):
        # When inventory is 0, both bid and ask must be actively quoted
        self.engine.inventory = 0
        bid, ask, is_active = self.engine.update_quotes({"skew": 0.0, "toxicity_prob": 0.0, "volatility_pulse": 0.0})
        self.assertTrue(is_active)
        self.assertIsNotNone(self.engine.my_bid_price)
        self.assertIsNotNone(self.engine.my_ask_price)
        self.assertGreater(self.engine.my_ask_price, self.engine.my_bid_price)

    def test_extreme_long_inventory_pulls_bid(self):
        # When inventory is +40 (>= 70% of max 50):
        # Engine MUST completely pull Bid (my_bid_price is None) and shade Ask to liquidate
        self.engine.inventory = 40
        bid, ask, is_active = self.engine.update_quotes({"skew": 0.0, "toxicity_prob": 0.0, "volatility_pulse": 0.0})
        self.assertTrue(is_active)
        self.assertIsNone(self.engine.my_bid_price, "Bid must be pulled when heavily long")
        self.assertIsNotNone(self.engine.my_ask_price, "Ask must remain active to liquidate long inventory")
        self.assertLessEqual(self.engine.my_ask_price, self.book.best_ask)

    def test_extreme_short_inventory_pulls_ask(self):
        # When inventory is -40 (<= -70% of max 50):
        # Engine MUST completely pull Ask (my_ask_price is None) and shade Bid to cover
        self.engine.inventory = -40
        bid, ask, is_active = self.engine.update_quotes({"skew": 0.0, "toxicity_prob": 0.0, "volatility_pulse": 0.0})
        self.assertTrue(is_active)
        self.assertIsNone(self.engine.my_ask_price, "Ask must be pulled when heavily short")
        self.assertIsNotNone(self.engine.my_bid_price, "Bid must remain active to cover short inventory")
        self.assertGreaterEqual(self.engine.my_bid_price, self.book.best_bid)

if __name__ == "__main__":
    unittest.main()
