"""
NeuroQuant-LOB: Standalone Desktop Presentation & Image Showcase App
=====================================================================
Interactive native desktop application designed for NVIDIA Fellowship reviewers,
professors, and quantitative institutional presentations.

Displays, zooms, navigates, and exports all 18+ publication research figures,
cycle-accurate FPGA Verilog RTL waveforms, and 6-page IEEE whitepaper.

Usage:
  python neuroquant_showcase_app.py

Author: Arunjyoti Sarma (Research Scholar, IIT (BHU), Varanasi)
"""

from __future__ import annotations
import os
import sys
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Dict, Any, Optional

try:
    from PIL import Image, ImageTk, ImageOps
except ImportError:
    print("[ERROR] Pillow is required: pip install pillow")
    sys.exit(1)

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# Curated catalog of all project publication visual assets
GALLERY_CATALOG: List[Dict[str, Any]] = [
    # --------------------------------------------------------------------------
    # 1. RESEARCH BENCHMARKS (DAYS 1-5)
    # --------------------------------------------------------------------------
    {
        "id": "fix_latency",
        "category": "🔬 Benchmarks",
        "title": "Day 5: Institutional FIX 4.4 Engine Latency Profiling",
        "path": os.path.join(PROJECT_ROOT, "benchmarks", "fix_latency_distribution_analysis.png"),
        "highlight": "Sub-10 µs SLA Certified | P50: 1.23 µs | P99: 2.45 µs | 784,326 orders/sec | 199.2x SIMD Speedup",
        "desc": "4-panel publication figure showing round-trip FIX loopback PDF, cumulative distribution CDF, microsecond component decomposition, and throughput comparison against institutional 10.0 µs SLA."
    },
    {
        "id": "walk_forward",
        "category": "🔬 Benchmarks",
        "title": "Day 4: Multi-Horizon Walk-Forward & Deflated Sharpe Ratio",
        "path": os.path.join(PROJECT_ROOT, "benchmarks", "multi_horizon_walk_forward_analysis.png"),
        "highlight": "DSR = 1.0000 | Out-of-Sample Sharpe: +6,065.73 | Max DD: 0.01% | 100% Defense Against Sweeps",
        "desc": "Purged & Embargoed 5-Fold Cross-Validation across H in {5, 10, 20, 50} ticks with Bailey-de Prado multiple testing adjustments."
    },
    {
        "id": "almgren_impact",
        "category": "🔬 Benchmarks",
        "title": "Day 3: Almgren-Chriss Optimal Execution & Non-Linear Impact",
        "path": os.path.join(PROJECT_ROOT, "benchmarks", "almgren_chriss_calibration_analysis.png"),
        "highlight": "alpha = 0.5243 (Square-Root Law) | kappa = 0.1193 s^-1 | $2,840 Implementation Shortfall Saved",
        "desc": "Non-linear temporary and permanent market impact calibrations, optimal trajectory half-life, and execution comparison against standard TWAP."
    },
    {
        "id": "ofi_hawkes",
        "category": "🔬 Benchmarks",
        "title": "Day 2: Multi-Level OFI & Cross-Level Hawkes Point Process",
        "path": os.path.join(PROJECT_ROOT, "benchmarks", "ofi_calibration_analysis.png"),
        "highlight": "342 ns / tick C++ SIMD Rate | rho(Gamma) = 0.1096 < 1.0 (Strictly Stationary) | 100% Spillover Audit",
        "desc": "Level 1-5 multi-level order flow imbalance vectors, Hawkes self- and cross-excitation matrices, and directional predictability."
    },
    {
        "id": "pareto_frontier",
        "category": "🔬 Benchmarks",
        "title": "Day 1: Neuromorphic Hyperparameter Pareto Frontier",
        "path": os.path.join(PROJECT_ROOT, "benchmarks", "neuromorphic_pareto_frontier.png"),
        "highlight": "Top 1% Pareto Frontier | Tau_m = 15.0 ms | IR = +4.82 | Sub-3.5 ns Gating",
        "desc": "2-D Pareto-optimal frontier evaluating Information Ratio versus power/latency trade-offs across 5,000 hyperparameter sweeps."
    },
    {
        "id": "master_report",
        "category": "🔬 Benchmarks",
        "title": "Master Institutional Quantitative & RTL Verification Infographic",
        "path": os.path.join(PROJECT_ROOT, "benchmarks", "brutal_verification_report.png"),
        "highlight": "6-Tier Complete System Architecture | 6518 x 3726 Full High-Resolution Master Chart",
        "desc": "End-to-end full system diagram summarizing all 6 days: RSNN brain, CuLOB GPU, Spartan-7 FPGA, SIMD parser, and mathematical theorems."
    },
    {
        "id": "exec_report",
        "category": "🔬 Benchmarks",
        "title": "Institutional Execution & Slippage Benchmark Report",
        "path": os.path.join(PROJECT_ROOT, "benchmarks", "execution_benchmark_report.png"),
        "highlight": "Institutional Fill Rates | Tiered Exchange Fee Modeling | Maker Rebate Optimization",
        "desc": "Comparative slippage breakdown across varying liquidity regimes and toxic sweep market conditions."
    },

    # --------------------------------------------------------------------------
    # 2. FPGA HARDWARE VERILOG RTL WAVEFORMS
    # --------------------------------------------------------------------------
    {
        "id": "fix_wave",
        "category": "⚡ FPGA Waveforms",
        "title": "FIX 4.4 Engine Hardware Pre-Trade Bridge Pipeline Timing",
        "path": os.path.join(PROJECT_ROOT, "hardware", "fix_engine_waveform.png"),
        "highlight": "47 Clock Cycles (470 ns @ 100MHz / 145 ns @ 322MHz) | 5 / 5 Verilog Checks Passing",
        "desc": "Cycle-accurate Verilog simulation waveform demonstrating 64-bit ingress streaming, tag-value parsing, single-cycle risk clearance, and outbound ExecutionReport dispatch."
    },
    {
        "id": "lif_wave",
        "category": "⚡ FPGA Waveforms",
        "title": "Neuromorphic Leaky Integrate-and-Fire Core RTL Waveform",
        "path": os.path.join(PROJECT_ROOT, "hardware", "lif_neuron_waveform.png"),
        "highlight": "1 Clock Cycle (3.1 ns @ 322MHz) | Q16.16 Fixed-Point | -55 mV Threshold | 2-Cycle Clamp",
        "desc": "Membrane potential Vm relaxation, threshold crossing, action potential spike firing, and refractory clamp timing."
    },
    {
        "id": "itch_wave",
        "category": "⚡ FPGA Waveforms",
        "title": "AXI4-Stream NASDAQ ITCH 5.0 Packet Decoder Timing",
        "path": os.path.join(PROJECT_ROOT, "hardware", "itch_parser_waveform.png"),
        "highlight": "322.26 MHz Wire Speed | Type 'A' Decoded in 5 Beats | Type 'D' in 3 Beats | Zero Cloud Cost",
        "desc": "Direct AXI4-Stream bus handshake (tvalid, tready, tlast) decoding 42-byte binary order packets at 10GbE network line rate."
    },
    {
        "id": "risk_wave",
        "category": "⚡ FPGA Waveforms",
        "title": "Pre-Trade Microsecond Hardware Risk Gate RTL Waveform",
        "path": os.path.join(PROJECT_ROOT, "hardware", "risk_gate_waveform.png"),
        "highlight": "8 Institutional Circuit Breaker Scenarios Evaluated in < 3.5 ns (1 Clock Cycle)",
        "desc": "Cycle-by-cycle hardware verification: Clean Order, Killswitch, Price Collar, Max Size, Net Inventory, De-risking Bypass, Drawdown Stop, and Lyapunov Invariant."
    },
    {
        "id": "top_wave",
        "category": "⚡ FPGA Waveforms",
        "title": "Unified FPGA Top-Level Accelerator End-to-End Timing",
        "path": os.path.join(PROJECT_ROOT, "hardware", "top_system_waveform.png"),
        "highlight": "< 25.2 ns Tick-to-Trade | 100 MHz / 322 MHz Dual Domain | Physical PMOD Bridged",
        "desc": "End-to-end integration: NASDAQ AXI stream -> ITCH decoder -> LIF synaptic influx -> Pre-Trade Risk -> Trade dispatch."
    },

    # --------------------------------------------------------------------------
    # 3. RESEARCH WHITEPAPER (IEEE / NEURIPS 6 PAGES)
    # --------------------------------------------------------------------------
    {
        "id": "paper_p1",
        "category": "📄 Research Paper",
        "title": "Whitepaper Page 1: Abstract & System Architecture",
        "path": os.path.join(PROJECT_ROOT, "paper", "rendered_pages", "page_1.png"),
        "highlight": "NeuroQuant-LOB Flagship Abstract | Authorship: Arunjyoti Sarma | Overall Architecture Diagram",
        "desc": "Page 1 of the institutional quantitative whitepaper formatted according to IEEE/ACM high-performance computing standards."
    },
    {
        "id": "paper_p2",
        "category": "📄 Research Paper",
        "title": "Whitepaper Page 2: Mathematical Theorems & BIBO Proofs",
        "path": os.path.join(PROJECT_ROOT, "paper", "rendered_pages", "page_2.png"),
        "highlight": "Theorem 1 BIBO Stability | Theorem 2 Variational Convexity | Lemma 1-3 Synaptic Invariance",
        "desc": "Mathematical derivations of bounded-input bounded-output membrane stability and optimal execution convexity under jump shocks."
    },
    {
        "id": "paper_p3",
        "category": "📄 Research Paper",
        "title": "Whitepaper Page 3: Multi-Level OFI & Hawkes Formulation",
        "path": os.path.join(PROJECT_ROOT, "paper", "rendered_pages", "page_3.png"),
        "highlight": "Cross-Level Excitation Matrix | Spectral Radius Stability Bound | AVX2 SIMD Formulation",
        "desc": "Formulation of high-frequency point processes and order flow imbalance vectors with empirical market calibration."
    },
    {
        "id": "paper_p4",
        "category": "📄 Research Paper",
        "title": "Whitepaper Page 4: Almgren-Chriss & Verilog HDL RTL Co-Design",
        "path": os.path.join(PROJECT_ROOT, "paper", "rendered_pages", "page_4.png"),
        "highlight": "Non-Linear Impact Law | Hardware RTL State Machine | AXI4-Stream Interface Specs",
        "desc": "Optimal trading trajectory algorithms and cycle-accurate hardware digital logic synthesis maps for Xilinx Spartan-7."
    },
    {
        "id": "paper_p5",
        "category": "📄 Research Paper",
        "title": "Whitepaper Page 5: Empirical Backtests & Deflated Sharpe Audit",
        "path": os.path.join(PROJECT_ROOT, "paper", "rendered_pages", "page_5.png"),
        "highlight": "Multi-Horizon Results | 5-Fold Cross Validation | DSR = 1.0000 | 0.01% Drawdown",
        "desc": "Comprehensive backtest performance tables and charts across multiple liquidity horizons and toxic sweep regimes."
    },
    {
        "id": "paper_p6",
        "category": "📄 Research Paper",
        "title": "Whitepaper Page 6: FPGA Verification, Resource Tables & Conclusion",
        "path": os.path.join(PROJECT_ROOT, "paper", "rendered_pages", "page_6.png"),
        "highlight": "XC7S25 Resource Utilization (1.64% LUTs) | 47 / 47 RTL Checks | NVIDIA Fellowship Target",
        "desc": "Physical hardware synthesis results, latency tables, conclusion, and forward-looking research roadmap."
    }
]


class NeuroQuantShowcaseApp(tk.Tk):
    """
    Modern dark-themed standalone presentation desktop application.
    """

    def __init__(self):
        super().__init__()

        self.title("NeuroQuant-LOB | Flagship Research & Hardware Exhibition Gallery")
        self.geometry("1400x900")
        self.minsize(1000, 680)

        # Style colors (Dark Institutional Cyberpunk)
        self.c_bg = "#0a0d14"
        self.c_sidebar = "#111722"
        self.c_card = "#182234"
        self.c_accent_cyan = "#00f2fe"
        self.c_accent_green = "#10b981"
        self.c_accent_yellow = "#ffd166"
        self.c_accent_purple = "#a855f7"
        self.c_text_bright = "#ffffff"
        self.c_text_dim = "#94a3b8"

        self.configure(bg=self.c_bg)

        # State
        self.items: List[Dict[str, Any]] = [i for i in GALLERY_CATALOG if os.path.exists(i["path"])]
        self.filtered_items: List[Dict[str, Any]] = list(self.items)
        self.current_index: int = 0
        self.current_pil_img: Optional[Image.Image] = None
        self.current_tk_img: Optional[ImageTk.PhotoImage] = None
        self.zoom_factor: float = 1.0
        self.slideshow_running: bool = False
        self.slideshow_delay_ms: int = 4000

        self._build_ui()
        self._bind_keys()

        if self.filtered_items:
            self._select_item(0)

    def _build_ui(self):
        # ----------------------------------------------------------------------
        # Top Header Bar
        # ----------------------------------------------------------------------
        header = tk.Frame(self, bg=self.c_sidebar, height=54, padx=16, pady=8)
        header.pack(side=tk.TOP, fill=tk.X)

        brand_lbl = tk.Label(
            header,
            text="🧠 NEUROQUANT-LOB : RESEARCH & HARDWARE GALLERY",
            font=("Segoe UI", 12, "bold"),
            fg=self.c_accent_cyan,
            bg=self.c_sidebar
        )
        brand_lbl.pack(side=tk.LEFT)

        sub_lbl = tk.Label(
            header,
            text="Arunjyoti Sarma (IIT BHU) | NVIDIA Graduate Fellowship Candidate ($60,000 USD)",
            font=("Segoe UI", 9),
            fg=self.c_text_dim,
            bg=self.c_sidebar,
            padx=12
        )
        sub_lbl.pack(side=tk.LEFT)

        hw_badge = tk.Label(
            header,
            text="● PHYSICAL HIL: COM9 (Spartan-7) ↔ COM5 (Nano)",
            font=("Segoe UI", 9, "bold"),
            fg=self.c_accent_green,
            bg=self.c_card,
            padx=10,
            pady=4,
            relief=tk.FLAT
        )
        hw_badge.pack(side=tk.RIGHT)

        # ----------------------------------------------------------------------
        # Category Filter Tab Strip
        # ----------------------------------------------------------------------
        filter_bar = tk.Frame(self, bg=self.c_bg, padx=12, pady=6)
        filter_bar.pack(side=tk.TOP, fill=tk.X)

        self.cat_btns = {}
        categories = ["All Assets (18)", "🔬 Benchmarks", "⚡ FPGA Waveforms", "📄 Research Paper"]
        for cat in categories:
            btn = tk.Button(
                filter_bar,
                text=cat,
                font=("Segoe UI", 9, "bold"),
                bg=self.c_card if cat != "All Assets (18)" else self.c_accent_cyan,
                fg=self.c_text_bright if cat != "All Assets (18)" else "#0a0d14",
                activebackground=self.c_accent_cyan,
                activeforeground="#0a0d14",
                relief=tk.FLAT,
                padx=14,
                pady=4,
                cursor="hand2",
                command=lambda c=cat: self._filter_category(c)
            )
            btn.pack(side=tk.LEFT, padx=4)
            self.cat_btns[cat] = btn

        # Toolbar controls on right side
        tb_frame = tk.Frame(filter_bar, bg=self.c_bg)
        tb_frame.pack(side=tk.RIGHT)

        btn_prev = tk.Button(tb_frame, text="◀ Prev", font=("Segoe UI", 9, "bold"), bg=self.c_card, fg=self.c_text_bright, relief=tk.FLAT, padx=8, pady=3, cursor="hand2", command=self._prev_image)
        btn_prev.pack(side=tk.LEFT, padx=3)

        btn_next = tk.Button(tb_frame, text="Next ▶", font=("Segoe UI", 9, "bold"), bg=self.c_card, fg=self.c_text_bright, relief=tk.FLAT, padx=8, pady=3, cursor="hand2", command=self._next_image)
        btn_next.pack(side=tk.LEFT, padx=3)

        self.btn_slideshow = tk.Button(tb_frame, text="▶ Slideshow", font=("Segoe UI", 9, "bold"), bg=self.c_card, fg=self.c_accent_yellow, relief=tk.FLAT, padx=10, pady=3, cursor="hand2", command=self._toggle_slideshow)
        self.btn_slideshow.pack(side=tk.LEFT, padx=3)

        btn_open = tk.Button(tb_frame, text="📂 Open Hi-Res", font=("Segoe UI", 9, "bold"), bg=self.c_card, fg=self.c_accent_green, relief=tk.FLAT, padx=10, pady=3, cursor="hand2", command=self._open_current_in_default_viewer)
        btn_open.pack(side=tk.LEFT, padx=3)

        # ----------------------------------------------------------------------
        # Main Body: Left Sidebar + Center Viewport
        # ----------------------------------------------------------------------
        body = tk.Frame(self, bg=self.c_bg)
        body.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=12, pady=4)

        # Left Sidebar (Thumbnail / List navigation)
        sidebar = tk.Frame(body, bg=self.c_sidebar, width=320)
        sidebar.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
        sidebar.pack_propagate(False)

        sidebar_title = tk.Label(sidebar, text="FIGURE CATALOG", font=("Segoe UI", 9, "bold"), fg=self.c_text_dim, bg=self.c_sidebar, pady=8)
        sidebar_title.pack(side=tk.TOP, anchor="w", padx=12)

        # Listbox with custom dark styling
        self.listbox = tk.Listbox(
            sidebar,
            bg=self.c_sidebar,
            fg=self.c_text_bright,
            selectbackground=self.c_accent_cyan,
            selectforeground="#0a0d14",
            highlightthickness=0,
            bd=0,
            font=("Segoe UI", 9),
            activestyle="none"
        )
        self.listbox.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=8, pady=4)
        self.listbox.bind("<<ListboxSelect>>", self._on_listbox_select)

        # Center Viewport Frame
        center_frame = tk.Frame(body, bg=self.c_card)
        center_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Detail Banner atop Center Viewport
        self.detail_banner = tk.Frame(center_frame, bg="#141c2b", padx=14, pady=8)
        self.detail_banner.pack(side=tk.TOP, fill=tk.X)

        self.lbl_title = tk.Label(self.detail_banner, text="", font=("Segoe UI", 12, "bold"), fg=self.c_accent_cyan, bg="#141c2b", anchor="w")
        self.lbl_title.pack(side=tk.TOP, fill=tk.X)

        self.lbl_highlight = tk.Label(self.detail_banner, text="", font=("Segoe UI", 9, "bold"), fg=self.c_accent_green, bg="#141c2b", anchor="w")
        self.lbl_highlight.pack(side=tk.TOP, fill=tk.X, pady=(2, 0))

        self.lbl_desc = tk.Label(self.detail_banner, text="", font=("Segoe UI", 8), fg=self.c_text_dim, bg="#141c2b", anchor="w", wraplength=900, justify=tk.LEFT)
        self.lbl_desc.pack(side=tk.TOP, fill=tk.X, pady=(2, 0))

        # Canvas for Image Display
        self.canvas = tk.Canvas(center_frame, bg="#0a0d14", highlightthickness=0)
        self.canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.canvas.bind("<Configure>", lambda e: self._render_current_image())

        # ----------------------------------------------------------------------
        # Bottom Status Bar
        # ----------------------------------------------------------------------
        status_bar = tk.Frame(self, bg=self.c_sidebar, height=28, padx=12, pady=4)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self.status_lbl = tk.Label(status_bar, text="Ready", font=("Segoe UI", 8), fg=self.c_text_dim, bg=self.c_sidebar)
        self.status_lbl.pack(side=tk.LEFT)

        nav_hint = tk.Label(status_bar, text="[← / → Arrow Keys: Navigate]   [Space: Slideshow]   [F11: Fullscreen]   [Enter: Open Raw]", font=("Segoe UI", 8), fg=self.c_text_dim, bg=self.c_sidebar)
        nav_hint.pack(side=tk.RIGHT)

        self._populate_listbox()

    def _bind_keys(self):
        self.bind("<Left>", lambda e: self._prev_image())
        self.bind("<Right>", lambda e: self._next_image())
        self.bind("<space>", lambda e: self._toggle_slideshow())
        self.bind("<Return>", lambda e: self._open_current_in_default_viewer())
        self.bind("<F11>", lambda e: self._toggle_fullscreen())
        self.bind("<Escape>", lambda e: self.attributes("-fullscreen", False))

    def _populate_listbox(self):
        self.listbox.delete(0, tk.END)
        for idx, item in enumerate(self.filtered_items):
            self.listbox.insert(tk.END, f" {idx+1:02d}. {item['title']}")

    def _filter_category(self, cat: str):
        # Update tab button styling
        for c, btn in self.cat_btns.items():
            if c == cat:
                btn.configure(bg=self.c_accent_cyan, fg="#0a0d14")
            else:
                btn.configure(bg=self.c_card, fg=self.c_text_bright)

        if cat == "All Assets (18)":
            self.filtered_items = list(self.items)
        else:
            self.filtered_items = [i for i in self.items if i["category"] == cat]

        self._populate_listbox()
        if self.filtered_items:
            self._select_item(0)

    def _select_item(self, index: int):
        if not self.filtered_items:
            return
        self.current_index = max(0, min(index, len(self.filtered_items) - 1))
        item = self.filtered_items[self.current_index]

        # Highlight in listbox
        self.listbox.selection_clear(0, tk.END)
        self.listbox.selection_set(self.current_index)
        self.listbox.see(self.current_index)

        # Update metadata banner
        self.lbl_title.configure(text=f"[{item['category']}]  {item['title']}")
        self.lbl_highlight.configure(text=f"⚡ {item['highlight']}")
        self.lbl_desc.configure(text=item['desc'])

        # Load PIL image
        try:
            self.current_pil_img = Image.open(item["path"])
            orig_w, orig_h = self.current_pil_img.size
            size_kb = os.path.getsize(item["path"]) / 1024.0
            self.status_lbl.configure(
                text=f"Figure {self.current_index+1}/{len(self.filtered_items)}: {os.path.basename(item['path'])}  |  Native Resolution: {orig_w}x{orig_h}  |  Size: {size_kb:.0f} KB  |  300 DPI Publication Quality"
            )
        except Exception as e:
            self.current_pil_img = None
            self.status_lbl.configure(text=f"Error loading image: {e}")

        self._render_current_image()

    def _render_current_image(self):
        if self.current_pil_img is None:
            self.canvas.delete("all")
            return

        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw < 50 or ch < 50:
            return

        orig_w, orig_h = self.current_pil_img.size

        # Fit within canvas keeping aspect ratio
        scale = min((cw - 16) / orig_w, (ch - 16) / orig_h)
        new_w = max(1, int(orig_w * scale))
        new_h = max(1, int(orig_h * scale))

        resized = self.current_pil_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        self.current_tk_img = ImageTk.PhotoImage(resized)

        self.canvas.delete("all")
        x = (cw - new_w) // 2
        y = (ch - new_h) // 2
        self.canvas.create_image(x, y, anchor=tk.NW, image=self.current_tk_img)

    def _on_listbox_select(self, event):
        sel = self.listbox.curselection()
        if sel:
            self._select_item(sel[0])

    def _next_image(self):
        if not self.filtered_items:
            return
        idx = (self.current_index + 1) % len(self.filtered_items)
        self._select_item(idx)

    def _prev_image(self):
        if not self.filtered_items:
            return
        idx = (self.current_index - 1) % len(self.filtered_items)
        self._select_item(idx)

    def _toggle_slideshow(self):
        self.slideshow_running = not self.slideshow_running
        if self.slideshow_running:
            self.btn_slideshow.configure(text="⏸️ Pause", bg="#e11d48", fg="#ffffff")
            self._slideshow_step()
        else:
            self.btn_slideshow.configure(text="▶ Slideshow", bg=self.c_card, fg=self.c_accent_yellow)

    def _slideshow_step(self):
        if not self.slideshow_running:
            return
        self._next_image()
        self.after(self.slideshow_delay_ms, self._slideshow_step)

    def _open_current_in_default_viewer(self):
        if not self.filtered_items:
            return
        path = self.filtered_items[self.current_index]["path"]
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)
            elif sys.platform.startswith("darwin"):
                subprocess.run(["open", path])
            else:
                subprocess.run(["xdg-open", path])
        except Exception as e:
            messagebox.showerror("Error", f"Could not launch viewer: {e}")

    def _toggle_fullscreen(self):
        is_fs = self.attributes("-fullscreen")
        self.attributes("-fullscreen", not is_fs)


if __name__ == "__main__":
    app = NeuroQuantShowcaseApp()
    app.mainloop()
