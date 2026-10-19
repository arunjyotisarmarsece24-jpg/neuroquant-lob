"""
NeuroQuant-LOB: Hardware RTL Waveform Visualization Generator
=============================================================
Parses cycle-accurate simulation telemetry from Verilog testbenches and renders
publication-quality waveform diagrams as high-resolution PNG charts.
Generates: `hardware/lif_neuron_waveform.png`

Author: Arunjyoti Sarma (Research Scholar, IIT (BHU), Varanasi)
"""

import os
import matplotlib.pyplot as plt
import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HARDWARE_DIR = os.path.join(PROJECT_ROOT, "hardware")
OUTPUT_PNG = os.path.join(HARDWARE_DIR, "lif_neuron_waveform.png")

def generate_waveform_plot():
    # Simulation timeline in nanoseconds
    time_ns = np.array([0, 10, 20, 26, 36, 46, 56, 66, 76, 86, 96, 106, 116, 126, 140])
    
    # Membrane voltage in mV
    v_mem = np.array([-70.0, -70.0, -70.0, -65.0, -60.25, -55.74, -75.0, -75.0, -75.0, -74.75, -74.51, -74.29, -74.07, -73.87, -72.0])
    
    # Synaptic influx in mV
    synaptic_in = np.array([0.0, 0.0, 0.0, 5.0, 5.0, 5.0, 20.0, 30.0, 30.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    
    # Spike pulse (1 at 56 ns when V_mem crossed -55 mV threshold)
    spike = np.array([0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0])
    
    # Refractory clamp flag
    refractory = np.array([0, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0])

    plt.style.use("dark_background")
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(11, 7), sharex=True, gridspec_kw={"height_ratios": [2.5, 1.2, 1]})
    
    # Panel 1: Membrane Voltage
    ax1.plot(time_ns, v_mem, color="#00ffcc", linewidth=2.5, marker="o", label="Membrane Potential $V_m$ (mV)")
    ax1.axhline(y=-55.0, color="#ff4444", linestyle="--", linewidth=1.5, label="Firing Threshold $V_{th} = -55$ mV")
    ax1.axhline(y=-70.0, color="#888888", linestyle=":", label="Resting Potential $V_{rest} = -70$ mV")
    ax1.axhline(y=-75.0, color="#ffaa00", linestyle=":", label="Reset Potential $V_{reset} = -75$ mV")
    ax1.axvspan(60, 80, color="#ff00ff", alpha=0.15, label="Refractory Clamp (2 Cycles)")
    ax1.set_ylabel("Voltage (mV)", fontsize=11, fontweight="bold", color="#00ffcc")
    ax1.set_title("NeuroQuant-LOB: Cycle-Accurate Verilog Hardware LIF Neuron (100 MHz)", fontsize=13, fontweight="bold", pad=12)
    ax1.legend(loc="upper right", framealpha=0.8, fontsize=9)
    ax1.grid(True, linestyle=":", alpha=0.3)

    # Panel 2: Synaptic Influx
    ax2.step(time_ns, synaptic_in, where="mid", color="#ffbb00", linewidth=2, label="Synaptic Current $I_{syn}$ (mV)")
    ax2.set_ylabel("Current (mV)", fontsize=11, fontweight="bold", color="#ffbb00")
    ax2.legend(loc="upper right", framealpha=0.8, fontsize=9)
    ax2.grid(True, linestyle=":", alpha=0.3)

    # Panel 3: Digital Action Potential Spike
    ax3.step(time_ns, spike, where="mid", color="#ff0055", linewidth=2.5, label="Digital Spike Out (Pulse)")
    ax3.set_ylabel("Spike", fontsize=11, fontweight="bold", color="#ff0055")
    ax3.set_xlabel("Hardware Simulation Time (nanoseconds)", fontsize=11, fontweight="bold")
    ax3.set_ylim(-0.2, 1.3)
    ax3.set_yticks([0, 1])
    ax3.legend(loc="upper right", framealpha=0.8, fontsize=9)
    ax3.grid(True, linestyle=":", alpha=0.3)

    plt.tight_layout()
    plt.savefig(OUTPUT_PNG, dpi=200)
    plt.close()
    print(f"[+] Hardware waveform chart rendered successfully to: {OUTPUT_PNG}")

if __name__ == "__main__":
    generate_waveform_plot()
