"""
NeuroQuant-LOB: High-Speed Interactive Terminal Dashboard
==========================================================
Displays real-time Limit Order Book depth, neuromorphic raster activity,
membrane potentials, and portfolio execution metrics in a live terminal UI.
"""

import time
import sys
from rich.console import Console, Group
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich.text import Text

from neuroquant.strategy import NeuromorphicAlphaSystem
from config import CONFIG_NEURO, CONFIG_MARKET, CONFIG_EXEC

def make_layout() -> Layout:
    layout = Layout(name="root")
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="main", ratio=1),
        Layout(name="footer", size=3)
    )
    layout["main"].split_row(
        Layout(name="market_panel", ratio=1),
        Layout(name="neuro_panel", ratio=1),
        Layout(name="exec_panel", ratio=1)
    )
    return layout

def generate_header() -> Panel:
    title = Text("🧠 NeuroQuant-LOB: Digital Neuromorphic Spiking Engine for Microstructure Alpha", style="bold cyan")
    sub = Text(" Asynchronous Event-Driven RSNN | Leaky Integrate-and-Fire | R-STDP Plasticity | Hawkes Process", style="dim")
    combined = Text.assemble(title, "\n", sub)
    return Panel(combined, style="bold blue")

def generate_market_table(mkt_data: dict) -> Panel:
    table = Table(title=f"📊 Order Book ({CONFIG_MARKET.symbol})", expand=True, show_edge=False)
    table.add_column("Bid Size", justify="right", style="green")
    table.add_column("Bid Price", justify="right", style="bold green")
    table.add_column("Ask Price", justify="left", style="bold red")
    table.add_column("Ask Size", justify="left", style="red")
    
    bids = mkt_data.get("bids", [])
    asks = mkt_data.get("asks", [])
    
    rows = max(len(bids), len(asks))
    for i in range(min(rows, 8)):
        b_sz = f"{bids[i][1]:.1f}" if i < len(bids) else ""
        b_pr = f"{bids[i][0]:.2f}" if i < len(bids) else ""
        a_pr = f"{asks[i][0]:.2f}" if i < len(asks) else ""
        a_sz = f"{asks[i][1]:.1f}" if i < len(asks) else ""
        table.add_row(b_sz, b_pr, a_pr, a_sz)
        
    stats_text = (
        f"\n[bold]Mid:[/bold] ${mkt_data.get('mid_price', 0):.2f} | "
        f"[bold]Micro:[/bold] ${mkt_data.get('micro_price', 0):.2f} | "
        f"[bold]Spread:[/bold] ${mkt_data.get('spread', 0):.2f}\n"
        f"[bold]OFI:[/bold] {mkt_data.get('ofi', 0):+.1f} | "
        f"[bold]Last Trade:[/bold] {mkt_data.get('last_trade_side', 'NONE')} "
        f"{mkt_data.get('last_trade_size', 0)} @ ${mkt_data.get('last_trade_price', 0):.2f}"
    )
    
    return Panel(Group(table, Text.from_markup(stats_text)), title="Market Microstructure", border_style="cyan")

def generate_neuro_panel(neuro_data: dict) -> Panel:
    signals = neuro_data.get("signals", {})
    skew = signals.get("skew", 0.0)
    toxicity = signals.get("toxicity_prob", 0.0)
    volatility = signals.get("volatility_pulse", 0.0)
    
    skew_color = "green" if skew > 0 else "red"
    tox_color = "red" if toxicity > 0.6 else "green"
    
    # Raster Bar Representations
    s_active = neuro_data.get("sensory_active_count", 0)
    h_active = neuro_data.get("hidden_active_count", 0)
    m_active = neuro_data.get("motor_active_count", 0)
    
    s_bar = "█" * s_active + "░" * (32 - s_active)
    h_bar = "█" * (h_active // 2) + "░" * (32 - (h_active // 2))
    
    lines = [
        f"[bold cyan]🧠 Neuromorphic RSNN Core Dynamics[/bold cyan]",
        f"Sensory Spikes (N=32): [{s_bar[:24]}] {s_active} active",
        f"Hidden Reservoir(N=64): [{h_bar[:24]}] {h_active} active",
        f"Sensory Mean Vm: {neuro_data.get('sensory_v_mean', -70):.1f} mV",
        f"Hidden Mean Vm:  {neuro_data.get('hidden_v_mean', -70):.1f} mV",
        f"Plastic Synaptic Norm: {neuro_data.get('motor_weights_norm', 0.0):.4f}",
        "",
        f"[bold yellow]⚡ Readout Action Potentials:[/bold yellow]",
        f"Quote Skew:     [{skew_color}]{skew:+.3f}[/{skew_color}]",
        f"Toxicity Alert: [{tox_color}]{toxicity * 100:.1f}%[/{tox_color}] (Sweeping Risk)",
        f"Volatility Burst: {volatility:.2f}",
        f"Motor Vm: {neuro_data.get('motor_v', [])}"
    ]
    return Panel("\n".join(lines), title="Neuromorphic Brain", border_style="magenta")

def generate_exec_panel(portfolio_data: dict, mkt_data: dict) -> Panel:
    pnl = portfolio_data.get("pnl", 0.0)
    pnl_color = "bold green" if pnl >= 0 else "bold red"
    inv = portfolio_data.get("inventory", 0)
    inv_color = "yellow" if abs(inv) > 10 else "cyan"
    
    quoted = "[green]ACTIVE[/green]" if portfolio_data.get("quote_active") else "[bold red]WITHDRAWN (TOXIC DEFENSE)[/bold red]"
    
    lines = [
        f"[bold]Status:[/bold] {quoted}",
        f"[bold]Active Bid Quote:[/bold] ${portfolio_data.get('my_bid', 0.0) or 0.0:.2f}",
        f"[bold]Active Ask Quote:[/bold] ${portfolio_data.get('my_ask', 0.0) or 0.0:.2f}",
        "",
        f"[bold]Mark-to-Market PnL:[/bold] [{pnl_color}]${pnl:+,.2f}[/{pnl_color}]",
        f"[bold]Inventory:[/bold] [{inv_color}]{inv:+d}[/{inv_color}] contracts (Limit: ±{CONFIG_EXEC.max_inventory})",
        f"[bold]Cash Balance:[/bold] ${portfolio_data.get('cash', 0.0):,.2f}",
        f"[bold]Total Executed Trades:[/bold] {portfolio_data.get('total_trades', 0)}",
        "",
        f"[bold]Adverse Sweeps Avoided:[/bold] [green]{portfolio_data.get('adverse_selections_avoided', 0)}[/green]",
        f"[bold]Toxic Hits Incurred:[/bold] [red]{portfolio_data.get('toxic_hits_taken', 0)}[/red]"
    ]
    return Panel("\n".join(lines), title="Quantitative Execution", border_style="green")

def run():
    console = Console()
    system = NeuromorphicAlphaSystem()
    layout = make_layout()
    layout["header"].update(generate_header())
    layout["footer"].update(Panel("Press Ctrl+C to stop simulation. Zero heap allocations on hot path.", style="dim"))
    
    with Live(layout, refresh_per_second=10, screen=True):
        try:
            while True:
                telemetry = system.step()
                mkt = telemetry["market"]
                neuro = telemetry["neuro"]
                port = telemetry["portfolio"]
                
                layout["main"]["market_panel"].update(generate_market_table(mkt))
                layout["main"]["neuro_panel"].update(generate_neuro_panel(neuro))
                layout["main"]["exec_panel"].update(generate_exec_panel(port, mkt))
                
                time.sleep(0.04)  # 25 FPS UI refresh
        except KeyboardInterrupt:
            pass

if __name__ == "__main__":
    run()
