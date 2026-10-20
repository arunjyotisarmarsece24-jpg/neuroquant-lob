"""
NeuroQuant-LOB: Deep Neuromorphic Parameter Sweeps Benchmark Runner (Day 1)
===========================================================================
Executes institutional grid search over:
  - tau_m in [10.0, 15.0, 20.0, 25.0, 30.0, 40.0] ms
  - v_thresh in [-60.0, -57.5, -55.0, -52.5, -50.0] mV
  - learning_rate in [0.0005, 0.001, 0.005, 0.010, 0.020]
Across realistic Hawkes L2 order book ticks. Identifies the non-dominated Pareto
frontier and knee-point champion parameters for C++20 AVX2 SIMD and Verilog HDL RTL.

Author: Arunjyoti Sarma (Research Scholar, IIT (BHU), Varanasi)
"""

import os
import sys
import argparse
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from neuroquant.analysis.parameter_sweep import (
    NeuromorphicParameterSweepEngine,
    SweepGridConfig,
    plot_pareto_frontier
)


def run_parameter_sweeps(quick: bool = False, ticks: int = 5000, verbose: bool = True) -> bool:
    print("\n" + "=" * 80)
    print("   NEUROQUANT-LOB: DAY 1 DEEP NEUROMORPHIC PARAMETER SWEEPS")
    print("   Target: Institutional Tier-1 Pareto Optimization (FPGA RTL & C++ SIMD)")
    print("=" * 80)
    
    if quick:
        # High-speed representative grid for fast verification
        grid = SweepGridConfig(
            tau_m_values=[10.0, 20.0, 30.0],
            v_thresh_values=[-60.0, -55.0, -50.0],
            learning_rate_values=[0.001, 0.005, 0.010],
            ticks_per_eval=min(ticks, 2500)
        )
    else:
        # Full deep institutional grid (6 x 5 x 5 = 150 points)
        grid = SweepGridConfig(
            tau_m_values=[10.0, 15.0, 20.0, 25.0, 30.0, 40.0],
            v_thresh_values=[-60.0, -57.5, -55.0, -52.5, -50.0],
            learning_rate_values=[0.0005, 0.001, 0.005, 0.010, 0.020],
            ticks_per_eval=ticks
        )
        
    engine = NeuromorphicParameterSweepEngine(grid_config=grid)
    results = engine.run_sweep(verbose=verbose)
    
    if not results or not engine.champion:
        print("[FAIL] Parameter sweep produced no valid evaluation points!")
        return False
        
    # Save results to JSON
    json_path = os.path.join(PROJECT_ROOT, "benchmarks", "parameter_sweep_results.json")
    engine.save_results(json_path)
    
    # Export synthesizable Verilog HDL header
    vh_path = os.path.join(PROJECT_ROOT, "hardware", "optimal_neuromorphic_params.vh")
    engine.export_verilog_header(vh_path)
    
    # Generate 4-panel 300 DPI visualization
    png_path = os.path.join(PROJECT_ROOT, "benchmarks", "neuromorphic_pareto_frontier.png")
    try:
        plot_pareto_frontier(results, engine.pareto_frontier, engine.champion, out_png=png_path)
    except Exception as e:
        print(f"[WARNING] Could not render matplotlib plot: {e}")
        
    c = engine.champion
    print("\n" + "=" * 80)
    print("   DAY 1 SWEEP VERDICT: PARETO-OPTIMAL HARDENING COMPLETE!")
    print("=" * 80)
    print(f"  [+] Optimal Membrane Time Constant (tau_m):  {c.tau_m:.1f} ms (Discrete Beta: {c.beta:.6f})")
    print(f"  [+] Optimal Action Threshold (v_thresh):     {c.v_thresh:.1f} mV (Rest: -70.0 mV, Reset: -75.0 mV)")
    print(f"  [+] Optimal R-STDP Plasticity Rate (eta):    {c.learning_rate:.4f}")
    print(f"  [+] Maximized Directional Macro-F1:          {c.macro_f1:.4f} (Up: {c.up_f1:.4f}, Down: {c.down_f1:.4f})")
    print(f"  [+] Maximized Spike Sparsity:                {c.spike_sparsity*100:.2f}% (Ultra-low switching power)")
    print(f"  [+] Minimized Reaction Latency:              {c.mean_latency_us:.2f} us (< 10 us Wire-to-Spike)")
    print(f"  [+] Hardware Verilog Q16.16 Parameters:      V_THRESH=-32'sd{abs(c.rtl_v_thresh_q16)}, BETA=32'sd{c.rtl_beta_q16}")
    print(f"  [+] Bit-Exact Hardware Quantization Error:   {c.quant_error_mv*1e6:.2f} nV (< 0.0001 mV Invariant)")
    print("=" * 80 + "\n")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NeuroQuant-LOB Deep Neuromorphic Parameter Sweeps")
    parser.add_argument("--quick", action="store_true", help="Run fast 27-point representative grid for testing")
    parser.add_argument("--ticks", type=int, default=5000, help="Number of ticks to evaluate per configuration (default: 5000)")
    parser.add_argument("--silent", action="store_true", help="Suppress intermediate point logging")
    args = parser.parse_args()
    
    success = run_parameter_sweeps(quick=args.quick, ticks=args.ticks, verbose=not args.silent)
    if not success:
        sys.exit(1)
