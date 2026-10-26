"""
NeuroQuant-LOB: Physical Hardware Interactive Console & LED Diagnostic Tester
=============================================================================
Principal Architect: Arunjyoti Sarma (Research Scholar, IIT (BHU), Varanasi)

Connects to:
  [1] Digilent Arty S7-25 (COM9) @ 921,600 Baud
  [2] Arduino Nano (COM5) @ 115,200 Baud

Allows direct physical testing of FPGA LEDs:
  • LD0 (E18): Accelerator Ready (Solid Green)
  • LD1 (F13): 0x55AA Framing Synchronized (Solid Green)
  • LD2 (E13): LIF Spiking Action Potential (Rapid Green Pulse)
  • LD3 (H15): Pre-Trade Risk Gate Approved (Solid Green)
  • RGB0 (F15/J15/G17): Green = Normal | Red = Breaker Tripped | Blue = Ingress
"""

import sys
import os
import time
import struct
import serial

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def build_itch_packet(order_ref: int, side: str, shares: int, symbol: str, price_cents: int) -> bytes:
    sync = bytes([0x55, 0xAA])
    beat0 = struct.pack(">B H H 3s", 0x41, 1, 2, bytes([0x00, 0x00, 0x12]))
    beat1 = struct.pack(">3s 5s", bytes([0x34, 0x56, 0x78]), bytes([0x00] * 5))
    ref_lo = bytes([(order_ref >> 16) & 0xFF, (order_ref >> 8) & 0xFF, order_ref & 0xFF])
    side_b = b'B' if side.upper() == 'B' else b'S'
    beat2 = ref_lo + side_b + struct.pack(">I", shares)
    sym_padded = symbol.ljust(8)[:8].encode("ascii")
    beat3 = sym_padded
    beat4 = struct.pack(">I 4s", price_cents, bytes([0x00] * 4))
    return sync + beat0 + beat1 + beat2 + beat3 + beat4

def run_physical_test(port="COM9", baud=921600):
    print("=" * 80)
    print(f"   NEUROQUANT-LOB: PHYSICAL FPGA LED ILLUMINATION TESTER")
    print(f"   Target Port: {port} @ {baud} Baud")
    print("=" * 80)
    
    try:
        ser = serial.Serial(port=port, baudrate=baud, timeout=0.2)
        print(f"[+] Successfully opened {port}! Flushing buffers...")
        ser.reset_input_buffer()
        ser.reset_output_buffer()
    except Exception as e:
        print(f"[-] Could not open {port}: {e}")
        return

    print("\n[INSTRUCTIONS] Watch the Physical LEDs on your Digilent Arty S7 Board:")
    print("  • LD0: Ready indicator (Solid Green)")
    print("  • LD1: RX Sync indicator (Turns ON when packet stream locks 0x55AA)")
    print("  • LD2: Neuromorphic Spike (Flashes Green when toxic orders fire LIF action potentials)")
    print("  • LD3: Risk Gate Approval (Illuminates Green on valid orders)")
    print("  • RGB0: Status (Green = Clean Operating | Red = Breaker Tripped | Blue = Ingress)")
    print("\n--------------------------------------------------------------------------------")

    print("\n[*] TEST 1: Sending 10 Normal Compliant Orders ($185.00, 100 shares)...")
    print("    -> Expected: LD1 ON, LD3 GREEN, RGB0 GREEN")
    for i in range(1, 11):
        pkt = build_itch_packet(i, 'B', 100, "AAPL    ", 1850000)
        ser.write(pkt)
        time.sleep(0.05)
    print("    [+] Sent 10 normal orders!")

    time.sleep(0.5)

    print("\n[*] TEST 2: Injecting Toxic Volatility Sweep (5,000 shares @ $180.00)...")
    print("    -> Expected: LD2 SPIKE FLASHES GREEN (LIF Action Potential fired!)")
    for i in range(11, 16):
        pkt = build_itch_packet(i, 'S', 5000, "AAPL    ", 1800000)
        ser.write(pkt)
        time.sleep(0.05)
    print("    [+] Sent 5 toxic sweeps!")

    time.sleep(0.5)

    print("\n[*] TEST 3: Injecting Fat-Finger Price Breach ($250.00 vs $185.00 mid)...")
    print("    -> Expected: RGB0 FLASHES BLINDING RED, LD3 TURNS OFF (Order Rejected)")
    pkt = build_itch_packet(99, 'B', 100, "AAPL    ", 2500000)
    ser.write(pkt)
    print("    [+] Sent fat-finger order!")

    ser.close()
    print("\n" + "=" * 80)
    print("   PHYSICAL BENCHMARK STIMULATION COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    target_port = sys.argv[1] if len(sys.argv) > 1 else "COM9"
    target_baud = int(sys.argv[2]) if len(sys.argv) > 2 else 921600
    run_physical_test(target_port, target_baud)
