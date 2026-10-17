"""
Institutional Quant Audit Benchmark
====================================
Simulates high-frequency market ticks with realistic FIFO queue depletion,
computes microsecond Post-Trade Markout curves, and evaluates the Deflated Sharpe Ratio (DSR).
"""

import sys
import os
import io

# Ensure UTF-8 output on Windows consoles
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
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from neuroquant.strategy import NeuromorphicAlphaSystem
from neuroquant.strategy.veteran_audit import VeteranQuantAuditor, FIFOQueueTracker

def run_audit(num_ticks: int = 2000):
    console = Console()
    console.print(Panel("[bold red][AUDIT] RUNNING VETERAN QUANTITATIVE AUDIT PROTOCOL[/bold red]\n[dim]Testing Adverse Selection, FIFO Queue Reality, and Deflated Sharpe Ratio[/dim]", border_style="red"))
    
    system = NeuromorphicAlphaSystem()
    auditor = VeteranQuantAuditor()
    
    pnl_returns = []
    prev_mtm = 0.0
    
    # Active FIFO Queue Trackers
    active_bid_queue = None
    active_ask_queue = None
    
    with console.status("[bold cyan]Simulating High-Frequency Ticks with Microstructure Stress...", spinner="dots"):
        for step in range(num_ticks):
            telemetry = system.step()
            mkt = telemetry["market"]
            curr_mid = mkt["mid_price"]
            curr_time_ms = telemetry["sim_time_ms"]
            
            # 1. Update pending markouts
            auditor.update_markouts(curr_time_ms, curr_mid)
            
            # 2. Check for executions & record markouts
            last_trade_side = mkt.get("last_trade_side")
            last_trade_price = mkt.get("last_trade_price", curr_mid)
            last_trade_size = mkt.get("last_trade_size", 0)
            
            port = telemetry["portfolio"]
            my_bid = port.get("my_bid")
            my_ask = port.get("my_ask")
            
            # Track FIFO queues
            if port.get("quote_active"):
                if active_bid_queue is None or active_bid_queue.price != my_bid:
                    vol_ahead = sum([v for p, v in mkt["bids"] if p >= my_bid])
                    active_bid_queue = FIFOQueueTracker(my_bid, 'BUY', vol_ahead)
                    
                if active_ask_queue is None or active_ask_queue.price != my_ask:
                    vol_ahead = sum([v for p, v in mkt["asks"] if p <= my_ask])
                    active_ask_queue = FIFOQueueTracker(my_ask, 'SELL', vol_ahead)
            else:
                active_bid_queue = None
                active_ask_queue = None
                
            # Simulate real fill against FIFO queue
            if last_trade_side == 'SELL' and active_bid_queue and last_trade_price <= my_bid:
                filled_qty = active_bid_queue.on_trade_at_level(last_trade_size)
                if filled_qty > 0:
                    auditor.record_fill(curr_time_ms, 'BUY', my_bid, filled_qty, curr_mid)
                    
            elif last_trade_side == 'BUY' and active_ask_queue and last_trade_price >= my_ask:
                filled_qty = active_ask_queue.on_trade_at_level(last_trade_size)
                if filled_qty > 0:
                    auditor.record_fill(curr_time_ms, 'SELL', my_ask, filled_qty, curr_mid)
                    
            # Record return
            curr_mtm = port["pnl"]
            pnl_returns.append(curr_mtm - prev_mtm)
            prev_mtm = curr_mtm

    # 3. Present Veteran Audit Results
    console.print("\n[bold green][+] Audit Simulation Complete.[/bold green]\n")
    
    # Table 1: Post-Trade Markout Curve
    markouts = auditor.calculate_markout_curves()
    t_markout = Table(title="[MARKOUT] Post-Trade Markout Curve (Adverse Selection Profile)", border_style="cyan")
    t_markout.add_column("Horizon (dt)", justify="left", style="bold yellow")
    t_markout.add_column("Average Markout ($)", justify="right")
    t_markout.add_column("Microstructure Verdict", justify="left")
    
    for h, val in markouts.items():
        val_str = f"{val:+.4f}"
        if val > 0:
            verdict = "[green][OK] Positive Edge (Alpha > Adverse Selection)[/green]"
            style = "green"
        elif val == 0:
            verdict = "[dim]Flat / Neutral[/dim]"
            style = "dim"
        else:
            verdict = "[red][FAIL] Adverse Selection Detected (Pigeon Fill)[/red]"
            style = "red"
        t_markout.add_row(f"{h:.1f} ms", f"[{style}]{val_str}[/{style}]", verdict)
        
    console.print(t_markout)
    
    # Table 2: Statistical Rigor (DSR)
    dsr_results = auditor.calculate_deflated_sharpe_ratio(np.array(pnl_returns))
    t_dsr = Table(title="[STAT] Statistical Significance & Deflated Sharpe Ratio (DSR)", border_style="magenta")
    t_dsr.add_column("Metric", style="bold")
    t_dsr.add_column("Value", justify="right")
    t_dsr.add_column("Institutional Benchmark", justify="left", style="dim")
    
    t_dsr.add_row("Total Evaluated Ticks", f"{num_ticks:,}", "N >= 1,000")
    t_dsr.add_row("Total Recorded Fills", f"{len(auditor.fill_history):,}", "Real FIFO Fills")
    t_dsr.add_row("Empirical Sharpe Ratio", f"{dsr_results['standard_sharpe']:.2f}", "> 1.50")
    t_dsr.add_row("Return Skewness", f"{dsr_results['skewness']:.2f}", "Near 0 or Positive")
    t_dsr.add_row("Return Kurtosis (Fat Tails)", f"{dsr_results['kurtosis']:.2f}", "> 3.0 (Leptokurtic)")
    t_dsr.add_row("Expected Max SR (N=50 Trials)", f"{dsr_results['expected_max_sr_trials']:.2f}", "Multiple testing haircut")
    
    dsr_p = dsr_results["dsr_prob"]
    dsr_color = "green" if dsr_p > 0.95 else "yellow" if dsr_p > 0.80 else "red"
    t_dsr.add_row("Deflated Sharpe Ratio (DSR)", f"[{dsr_color}]{dsr_p * 100:.1f}%[/{dsr_color}]", "> 95.0% for significance")
    t_dsr.add_row("Hypothesis Verdict", "[bold green]ACCEPTED (Statistically Robust)[/bold green]" if dsr_results["is_statistically_significant"] else "[bold red]REJECTED (Possible Data Snooping)[/bold red]", "p < 0.05")
    
    console.print("\n", t_dsr)

if __name__ == "__main__":
    run_audit(num_ticks=1500)
