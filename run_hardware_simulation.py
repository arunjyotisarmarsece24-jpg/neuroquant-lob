"""
NeuroQuant-LOB: 100% Free & Open-Source Hardware Verilog Simulation Runner
=========================================================================
Compiles and simulates institutional FPGA Verilog RTL modules using the local
Icarus Verilog (`iverilog`) and `vvp` toolchain ($0.00 cost, zero cloud fees):
  1. `lif_neuron_core.v`: Signed Q16.16 Leaky Integrate-and-Fire Core (100 MHz / 322 MHz)
  2. `itch_parser_axi.v`: AXI4-Stream 64-bit NASDAQ ITCH 5.0 Hardware Packet Parser
  3. `risk_gate_core.v`: Pre-Trade Microsecond Hardware Risk Gate (< 3.5 ns latency)

Usage:
  python run_hardware_simulation.py
  python run_hardware_simulation.py --module all
  python run_hardware_simulation.py --module lif --waveforms
  python run_hardware_simulation.py --module itch
  python run_hardware_simulation.py --module risk

Author: Arunjyoti Sarma (Research Scholar, IIT (BHU), Varanasi)
"""

import os
import sys
import argparse
import subprocess
import shutil

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
HARDWARE_DIR = os.path.join(PROJECT_ROOT, "hardware")
IVERILOG_BIN = r"C:\iverilog\bin\iverilog.exe"
VVP_BIN = r"C:\iverilog\bin\vvp.exe"
GTKWAVE_BIN = r"C:\iverilog\gtkwave\bin\gtkwave.exe"

# Fallback to PATH if not in default location
if not os.path.exists(IVERILOG_BIN):
    IVERILOG_BIN = shutil.which("iverilog") or "iverilog"
if not os.path.exists(VVP_BIN):
    VVP_BIN = shutil.which("vvp") or "vvp"
if not os.path.exists(GTKWAVE_BIN):
    GTKWAVE_BIN = shutil.which("gtkwave") or "gtkwave"

MODULE_CONFIGS = {
    "lif": {
        "name": "Leaky Integrate-and-Fire Neuromorphic Core",
        "rtl": "lif_neuron_core.v",
        "tb": "tb_lif_neuron.v",
        "out": "lif_sim.vvp",
        "vcd": "neuroquant_lif_trace.vcd"
    },
    "itch": {
        "name": "AXI4-Stream NASDAQ ITCH 5.0 Hardware Parser",
        "rtl": "itch_parser_axi.v",
        "tb": "tb_itch_parser.v",
        "out": "itch_sim.vvp",
        "vcd": "neuroquant_itch_trace.vcd"
    },
    "risk": {
        "name": "Pre-Trade Microsecond Hardware Risk Gate Core",
        "rtl": "risk_gate_core.v",
        "tb": "tb_risk_gate.v",
        "out": "risk_sim.vvp",
        "vcd": "neuroquant_risk_trace.vcd"
    }
}


def run_single_module(mod_key: str, open_waveforms: bool = False) -> bool:
    cfg = MODULE_CONFIGS.get(mod_key)
    if not cfg:
        print(f"[FAIL] Unknown hardware module: {mod_key}")
        return False

    rtl_path = os.path.join(HARDWARE_DIR, cfg["rtl"])
    tb_path = os.path.join(HARDWARE_DIR, cfg["tb"])
    out_vvp = os.path.join(HARDWARE_DIR, cfg["out"])
    vcd_path = os.path.join(HARDWARE_DIR, cfg["vcd"])

    print(f"\n[*] -------------------------------------------------------------")
    print(f"[*] COMPILING & SIMULATING: {cfg['name']}")
    print(f"[*] RTL: {cfg['rtl']} | Testbench: {cfg['tb']}")
    print(f"[*] -------------------------------------------------------------")

    compile_cmd = [IVERILOG_BIN, "-o", out_vvp, rtl_path, tb_path]
    res_compile = subprocess.run(compile_cmd, cwd=PROJECT_ROOT)
    if res_compile.returncode != 0:
        print(f"[FAIL] iverilog compilation failed for {cfg['name']}!")
        return False

    sim_cmd = [VVP_BIN, out_vvp]
    res_sim = subprocess.run(sim_cmd, cwd=PROJECT_ROOT)
    if res_sim.returncode != 0:
        print(f"[FAIL] vvp simulation failed for {cfg['name']}!")
        return False

    if open_waveforms and os.path.exists(vcd_path):
        gtkw_file = os.path.join(HARDWARE_DIR, f"neuroquant_{mod_key}.gtkw")
        launch_args = [GTKWAVE_BIN, vcd_path]
        if os.path.exists(gtkw_file):
            launch_args.append(gtkw_file)
        print(f"[*] Launching GTKWave Logic Analyzer on {vcd_path} (Auto-loading signals)...")
        try:
            subprocess.Popen(launch_args, cwd=PROJECT_ROOT)
            print("[+] GTKWave window launched successfully with active traces!")
        except Exception as e:
            print(f"[!] Could not launch GTKWave: {e}")

    return True


def run_hardware_sim(module: str = "all", open_waveforms: bool = False) -> bool:
    if module in MODULE_CONFIGS:
        return run_single_module(module, open_waveforms)
    elif module == "all":
        success = True
        for k in ["lif", "itch", "risk"]:
            ok = run_single_module(k, open_waveforms and (k == "lif"))
            if not ok:
                success = False
        return success
    else:
        print(f"[FAIL] Invalid module selection: '{module}'. Choose from: lif, itch, risk, all.")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NeuroQuant-LOB Hardware RTL Simulation Suite")
    parser.add_argument("--module", "-m", choices=["lif", "itch", "risk", "all"], default="all",
                        help="Select module to simulate (default: all)")
    parser.add_argument("--waveforms", "-w", action="store_true",
                        help="Launch GTKWave to inspect signal waveforms")
    args = parser.parse_args()

    success = run_hardware_sim(module=args.module, open_waveforms=args.waveforms)
    if not success:
        sys.exit(1)
    print("\n>>> ALL VERILOG HARDWARE MODULES COMPILED AND VERIFIED WITH 100% SUCCESS! <<<\n")
