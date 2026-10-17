"""
Live Real-Time Market Feed & Spike Ingestion Runner
===================================================
Streams live Level-2 order book depth and executed trades from public cryptocurrency
exchanges (Binance BTC/USDT) directly into the OrderBook and Neuromorphic Spiking Engine.
Requires ZERO API keys.
"""

import sys
import os
import time

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

import numpy as np
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from neuroquant.market import OrderBook, LivePublicMarketFeed
from neuroquant.neuromorphic import LOBSpikeEncoder, DigitalNeuromorphicCore
from config import MarketConfig, NeuromorphicConfig

def main():
    console = Console()
    console.print(Panel("[bold green]📡 CONNECTING TO LIVE PUBLIC CRYPTO EXCHANGE FEED (BTC/USDT)[/bold green]\n[dim]Streaming real-world order book depth directly into the Neuromorphic Spiking Core (Zero API Keys)[/dim]", border_style="green"))

    # 1. Initialize real-world BTC/USDT config
    mkt_cfg = MarketConfig(symbol="BTCUSDT", tick_size=0.1, initial_mid_price=68000.0)
    neuro_cfg = NeuromorphicConfig()

    book = OrderBook(mkt_cfg)
    feed = LivePublicMarketFeed(order_book=book, symbol="BTCUSDT", poll_interval_sec=0.2)
    encoder = LOBSpikeEncoder(mkt_cfg, neuro_cfg)
    brain = DigitalNeuromorphicCore(neuro_cfg)

    console.print("[cyan]Starting background live WebSocket/REST polling worker...[/cyan]")
    feed.start()
    time.sleep(1.5)  # Allow initial depth snapshot to seed the book

    console.print("[bold green]✔ Live feed connected! Streaming real-time ticks & spikes... (Press Ctrl+C to stop)[/bold green]\n")

    t_table = Table(title="Live Bitcoin Level-2 Market Stream & Spiking Reaction", border_style="cyan")
    t_table.add_column("Timestamp", style="dim", width=12)
    t_table.add_column("Live Mid ($)", style="bold yellow", justify="right")
    t_table.add_column("Best Bid", style="green", justify="right")
    t_table.add_column("Best Ask", style="red", justify="left")
    t_table.add_column("Spread", justify="right")
    t_table.add_column("Sensory Spikes", style="bold cyan")
    t_table.add_column("Readout Skew", justify="right")
    t_table.add_column("Toxicity", justify="right")

    try:
        start_time = time.time()
        for i in range(15):  # Sample 15 live ticks
            current_time_ms = (time.time() - start_time) * 1000.0
            snapshot, desc = feed.step(dt_sec=0.2)
            
            # Encode live real market book into digital spikes
            sensory_spikes = encoder.encode(snapshot, current_time_ms)
            s_spk, h_spk, m_spk = brain.step(sensory_spikes, reward=0.0)
            signals = brain.get_motor_readout_signals()

            mid_p = snapshot.get("mid_price", 0.0)
            best_b = snapshot.get("best_bid", 0.0)
            best_a = snapshot.get("best_ask", 0.0)
            spread = snapshot.get("spread", 0.0)
            num_spikes = int(np.sum(s_spk))
            skew = signals.get("skew", 0.0)
            tox = signals.get("toxicity_prob", 0.0) * 100

            tox_style = "red" if tox > 60 else "green"
            skew_style = "green" if skew > 0 else "red"

            t_table.add_row(
                f"{current_time_ms:.0f} ms",
                f"${mid_p:,.2f}",
                f"${best_b:,.2f}",
                f"${best_a:,.2f}",
                f"${spread:.2f}",
                f"{num_spikes} active",
                f"[{skew_style}]{skew:+.3f}[/{skew_style}]",
                f"[{tox_style}]{tox:.1f}%[/{tox_style}]"
            )
            time.sleep(0.5)

        console.print(t_table)
        console.print("\n[bold green]✔ Live real-world ingestion test successfully completed![/bold green]")

    except KeyboardInterrupt:
        console.print("\n[yellow]Stopping live stream...[/yellow]")
    finally:
        feed.stop()

if __name__ == "__main__":
    main()
