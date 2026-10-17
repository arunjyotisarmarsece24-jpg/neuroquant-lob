"""
NeuroQuant-LOB: Application Launcher
====================================
Launches the full digital neuromorphic web application and interactive dashboard.
"""

import sys
import os
import webbrowser
import threading
import time
from rich.console import Console
from rich.panel import Panel

# Ensure project root is in Python module search path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from web_app.server import app

def open_browser_delayed(url: str, delay_sec: float = 1.2):
    time.sleep(delay_sec)
    webbrowser.open_new_tab(url)

def main():
    console = Console()
    url = "http://127.0.0.1:5000"
    
    panel_content = (
        "[bold cyan]🧠 NeuroQuant-LOB | Digital Neuromorphic Spiking Engine[/bold cyan]\n"
        "[dim]Asynchronous Microstructure Event-Driven RSNN with R-STDP Plasticity[/dim]\n\n"
        f"[bold green]✔ Web Dashboard live at:[/bold green] [underline cyan]{url}[/underline cyan]\n"
        "[bold yellow]✔ Hardware Status:[/bold yellow] 100% Fully Digital Software Simulation (No physical neuromorphic chip required)\n"
        "[bold white]✔ Core Features:[/bold white] Live L2 Book Ladder, Spiking Raster Plot, V_m Oscilloscope, Toxic Sweep Defense\n\n"
        "[dim]Press Ctrl+C in this terminal to gracefully shutdown the server.[/dim]"
    )
    console.print(Panel(panel_content, border_style="cyan", expand=False))
    
    # Launch browser automatically in a background daemon thread
    threading.Thread(target=open_browser_delayed, args=(url,), daemon=True).start()
    
    # Run Flask Application
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)

if __name__ == "__main__":
    main()
