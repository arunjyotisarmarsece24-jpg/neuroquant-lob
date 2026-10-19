"""
NeuroQuant-LOB: Application Launcher & Mobile Companion Host
============================================================
Launches the full digital neuromorphic web application and mobile companion.
Author: Arunjyoti Sarma
"""

import sys
import os
import socket
import webbrowser
import threading
import time
import io
from rich.console import Console
from rich.panel import Panel

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Ensure project root is in Python module search path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from web_app.server import app

def get_local_ip() -> str:
    """Detect the local Wi-Fi / LAN IP address for mobile access."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Doesn't actually send packet; connects to public DNS to find outbound interface IP
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        try:
            ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            ip = "127.0.0.1"
    finally:
        s.close()
    return ip

def open_browser_delayed(url: str, delay_sec: float = 1.2):
    time.sleep(delay_sec)
    webbrowser.open_new_tab(url)

def main():
    console = Console()
    local_ip = get_local_ip()
    local_url = "http://127.0.0.1:5000"
    mobile_url = f"http://{local_ip}:5000"
    
    # Try generating an ASCII QR code for fast mobile camera scanning
    qr_ascii_str = ""
    try:
        import qrcode
        qr = qrcode.QRCode(border=1)
        qr.add_data(mobile_url)
        qr.make(fit=True)
        buf = io.StringIO()
        qr.print_ascii(out=buf, invert=True)
        qr_ascii_str = buf.getvalue()
    except Exception:
        qr_ascii_str = ""

    panel_content = (
        "[bold cyan]🧠 NeuroQuant-LOB | Digital Neuromorphic Spiking Engine[/bold cyan]\n"
        "[bold white]Author: Arunjyoti Sarma | Personal Quantitative Architecture[/bold white]\n"
        "[dim]Asynchronous Microstructure Event-Driven RSNN • 230ns SIMD • Almgren-Chriss Execution[/dim]\n\n"
        f"[bold green]💻 Desktop Browser:[/bold green]     [underline cyan]{local_url}[/underline cyan]\n"
        f"[bold yellow]📱 Mobile Phone / Tablet:[/bold yellow] [underline green]{mobile_url}[/underline green]\n\n"
        "[bold white]✨ Mobile Features:[/bold white]\n"
        "  • [cyan]Explainer Guide:[/cyan] Interactive visual tour of LOB microstructure & 230ns SIMD core\n"
        "  • [cyan]Live L2 DOM:[/cyan] Real-time order book depth with manual toxic sweep triggers\n"
        "  • [cyan]Brain Oscilloscope:[/cyan] Touch-interactive membrane potential & raster spike plots\n"
        "  • [cyan]Execution Lab:[/cyan] Almgren-Chriss non-linear slippage & maker rebate simulator\n"
        "  • [cyan]Proof Attacks:[/cyan] In-app 1,000,000-trial adversarial mathematical falsification\n"
        "  • [cyan]Whitepaper Reader:[/cyan] 6-page technical whitepaper with pinch-to-zoom & PDF export\n\n"
        "[dim]To open on mobile: connect phone to same Wi-Fi and browse the Mobile URL or scan below.[/dim]"
    )
    try:
        console = Console(force_terminal=True, legacy_windows=False)
        console.print(Panel(panel_content, border_style="cyan", expand=False))
        if qr_ascii_str:
            console.print("[bold yellow]Scan QR Code on your Phone Camera:[/bold yellow]")
            print(qr_ascii_str)
        console.print("[dim]Press Ctrl+C in this terminal to gracefully shutdown the server.[/dim]\n")
    except Exception:
        print("=" * 70)
        print("NEUROQUANT-LOB: DIGITAL NEUROMORPHIC SPIKING ENGINE")
        print(f"Desktop URL: {local_url}")
        print(f"Mobile URL:  {mobile_url}")
        print("=" * 70)

    # Launch desktop browser automatically
    threading.Thread(target=open_browser_delayed, args=(local_url,), daemon=True).start()
    
    # Run Flask Application binding to 0.0.0.0 for LAN access
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)

if __name__ == "__main__":
    main()
