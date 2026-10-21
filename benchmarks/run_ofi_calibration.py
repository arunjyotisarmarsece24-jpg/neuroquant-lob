"""
NeuroQuant-LOB: Day 2 OFI Calibration Benchmark Runner
======================================================
Executes institutional calibration of multi-level Order Flow Imbalance (OFI)
decay rates and cross-level Hawkes kernels against high-frequency L2 depth ticks.
Calibrates C++20 AVX2 SIMD core and synthesizable Verilog HDL RTL parameters.

Usage:
  python benchmarks/run_ofi_calibration.py
  python benchmarks/run_ofi_calibration.py --quick
  python benchmarks/run_ofi_calibration.py --ticks 50000

Author: Arunjyoti Sarma (Research Scholar, IIT (BHU), Varanasi)
"""

import os
import sys
import argparse
import time
import json
import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from config import MarketConfig
from neuroquant.market.order_book import OrderBook
from neuroquant.market.feed_simulator import HawkesMarketFeed
from neuroquant.market.ofi_calibrator import (
    OFICalibrator,
    plot_ofi_calibration_analysis
)


def generate_l2_depth_ticks(num_ticks: int = 25000, seed: int = 42) -> dict:
    """
    Generates realistic 5-level L2 depth ticks using self-exciting Hawkes process.
    """
    np.random.seed(seed)
    cfg = MarketConfig()
    book = OrderBook(cfg)
    feed = HawkesMarketFeed(book, cfg)

    bid_p = np.zeros((num_ticks, 5), dtype=np.float32)
    bid_s = np.zeros((num_ticks, 5), dtype=np.float32)
    ask_p = np.zeros((num_ticks, 5), dtype=np.float32)
    ask_s = np.zeros((num_ticks, 5), dtype=np.float32)
    mid_p = np.zeros(num_ticks, dtype=np.float32)
    timestamps = np.zeros(num_ticks, dtype=np.float32)

    dt_sec = 0.001
    sim_time = 0.0

    print(f"[*] Generating {num_ticks:,} realistic L2 depth ticks via Hawkes Market Feed...")
    t0 = time.perf_counter()

    for i in range(num_ticks):
        sim_time += dt_sec
        snap, _ = feed.step(dt_sec)

        bids = snap.get("bids", [])
        asks = snap.get("asks", [])
        mid = snap.get("mid_price", cfg.initial_mid_price)
        mid_p[i] = mid
        timestamps[i] = sim_time

        # Fill up to 5 levels
        for l in range(5):
            if l < len(bids):
                bid_p[i, l] = bids[l][0]
                bid_s[i, l] = bids[l][1]
            else:
                bid_p[i, l] = (bids[-1][0] - (l - len(bids) + 1) * cfg.tick_size) if bids else mid - (l + 1) * cfg.tick_size
                bid_s[i, l] = 20.0 + l * 15.0

            if l < len(asks):
                ask_p[i, l] = asks[l][0]
                ask_s[i, l] = asks[l][1]
            else:
                ask_p[i, l] = (asks[-1][0] + (l - len(asks) + 1) * cfg.tick_size) if asks else mid + (l + 1) * cfg.tick_size
                ask_s[i, l] = 20.0 + l * 15.0

    elapsed = time.perf_counter() - t0
    rate = num_ticks / max(1e-5, elapsed)
    print(f"  -> Generated {num_ticks:,} ticks in {elapsed:.2f}s ({rate:,.0f} ticks/s)")

    return {
        "bid_prices": bid_p,
        "bid_sizes": bid_s,
        "ask_prices": ask_p,
        "ask_sizes": ask_s,
        "mid_prices": mid_p,
        "timestamps": timestamps
    }


def run_ofi_calibration(quick: bool = False, ticks: int = 25000, verbose: bool = True) -> bool:
    print("\n" + "=" * 80)
    print("   NEUROQUANT-LOB: DAY 2 ORDER-FLOW IMBALANCE (OFI) CALIBRATION")
    print("   Hardware Target: C++20 AVX2 SIMD Core & Verilog HDL RTL")
    print("=" * 80)

    num_ticks = 10000 if quick else ticks
    tick_data = generate_l2_depth_ticks(num_ticks=num_ticks)

    calibrator = OFICalibrator(num_levels=5, horizons=[1, 5, 10, 20, 50])
    result = calibrator.calibrate(tick_data, verbose=verbose)

    if not result.is_hawkes_stable:
        print("[FAIL] Hawkes cross-excitation matrix violated stability condition rho(Gamma) < 1.0!")
        return False

    # 1. Save JSON records
    json_path = os.path.join(PROJECT_ROOT, "benchmarks", "ofi_calibration_results.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, indent=2)
    print(f"[+] Calibration results saved to: {json_path}")

    # 2. Export synthesizable Verilog HDL parameters
    vh_path = os.path.join(PROJECT_ROOT, "hardware", "optimal_ofi_params.vh")
    calibrator.export_verilog_header(result, vh_path)

    # 3. Render 4-panel publication visualization
    png_path = os.path.join(PROJECT_ROOT, "benchmarks", "ofi_calibration_analysis.png")
    try:
        plot_ofi_calibration_analysis(result, png_path)
    except Exception as e:
        print(f"[WARNING] Could not render matplotlib plot: {e}")

    print("\n>>> DAY 2 ORDER-FLOW IMBALANCE (OFI) CALIBRATION 100% COMPLETE! <<<\n")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NeuroQuant-LOB Day 2 OFI Calibration Benchmark")
    parser.add_argument("--quick", action="store_true", help="Run high-speed verification calibration (10,000 ticks)")
    parser.add_argument("--ticks", type=int, default=25000, help="Total L2 order book ticks to evaluate")
    args = parser.parse_args()

    success = run_ofi_calibration(quick=args.quick, ticks=args.ticks, verbose=True)
    if not success:
        sys.exit(1)
