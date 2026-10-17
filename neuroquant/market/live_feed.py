"""
Live High-Frequency Market Feed Ingestion Adapter
==================================================
Streams real-time Level-2 Limit Order Book depth from public cryptocurrency
exchanges (Binance / Coinbase) directly into the NeuroQuant order book engine.
Requires ZERO API keys.
"""

import time
import json
import threading
import requests
from typing import Optional, Dict, Any, Tuple
from config import MarketConfig
from .order_book import OrderBook

class LivePublicMarketFeed:
    """
    Connects to public high-frequency market depth snapshots and incremental trade streams.
    Allows testing the neuromorphic core on real-world order books (e.g., BTC/USDT, ETH/USDT).
    """
    def __init__(self, order_book: OrderBook, symbol: str = "BTCUSDT", poll_interval_sec: float = 0.1):
        self.book = order_book
        self.symbol = symbol.upper()
        self.poll_interval = poll_interval_sec
        self.is_running = False
        self.thread: Optional[threading.Thread] = None
        
        self.last_trade_side: Optional[str] = None
        self.last_trade_size: float = 0.0
        self.last_trade_price: float = 0.0
        self.latest_event_desc = "INITIALIZING_LIVE_FEED"

    def start(self):
        """Start background polling thread."""
        self.is_running = True
        self.thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.thread.start()

    def stop(self):
        """Stop background worker."""
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=1.0)

    def _worker_loop(self):
        """Continuously pulls L2 depth and recent trades from public endpoints."""
        url_depth = f"https://api.binance.com/api/v3/depth?symbol={self.symbol}&limit=10"
        url_trades = f"https://api.binance.com/api/v3/trades?symbol={self.symbol}&limit=5"
        
        while self.is_running:
            try:
                # 1. Fetch live top-10 depth
                resp = requests.get(url_depth, timeout=1.5)
                if resp.status_code == 200:
                    data = resp.json()
                    bids = data.get("bids", [])
                    asks = data.get("asks", [])
                    
                    # Update order book in-memory
                    self.book.bids.clear()
                    self.book.asks.clear()
                    for p_str, v_str in bids:
                        self.book.bids[round(float(p_str), 2)] = float(v_str)
                    for p_str, v_str in asks:
                        self.book.asks[round(float(p_str), 2)] = float(v_str)
                    self.book._update_microstructure()

                # 2. Fetch recent executed trades
                r_trades = requests.get(url_trades, timeout=1.5)
                if r_trades.status_code == 200:
                    trades = r_trades.json()
                    if trades:
                        latest = trades[-1]
                        # isBuyerMaker: true means seller hit the bid (SELL), false means buyer lifted the ask (BUY)
                        is_buyer_maker = latest.get("isBuyerMaker", False)
                        self.last_trade_side = "SELL" if is_buyer_maker else "BUY"
                        self.last_trade_price = float(latest.get("price", self.book.mid_price))
                        self.last_trade_size = float(latest.get("qty", 1.0))
                        self.book.last_trade_side = self.last_trade_side
                        self.book.last_trade_size = self.last_trade_size
                        self.book.last_trade_price = self.last_trade_price
                        self.latest_event_desc = f"LIVE_{self.last_trade_side}_{self.last_trade_size:.2f}@{self.last_trade_price:.2f}"

            except Exception:
                self.latest_event_desc = "LIVE_FEED_RECONNECTING"
                
            time.sleep(self.poll_interval)

    def step(self, dt_sec: float) -> Tuple[Dict[str, Any], str]:
        """Provides identical interface to HawkesMarketFeed for seamless plug-and-play."""
        snapshot = self.book.get_snapshot()
        return snapshot, self.latest_event_desc
