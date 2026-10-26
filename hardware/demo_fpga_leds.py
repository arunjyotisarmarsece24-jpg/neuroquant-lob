"""
================================================================================
NEUROQUANT-LOB: PHYSICAL ARTY S7 FPGA HARDWARE LED DEMONSTRATOR
================================================================================
Principal Architect: Arunjyoti Sarma (Research Scholar, IIT (BHU), Varanasi)
Target: Digilent Arty S7-25 (Spartan-7) via COM9 @ 921,600 Baud
================================================================================
"""

import sys
import os
import time
import struct
import serial

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

def run_led_show(port="COM9", baud=921600):
    print("\n" + "=" * 80)
    print("   NEUROQUANT-LOB: PHYSICAL FPGA LED ILLUMINATION DEMO")
    print(f"   Connecting to Digilent Arty S7 on {port} @ {baud} Baud...")
    print("=" * 80)

    try:
        ser = serial.Serial(port=port, baudrate=baud, timeout=0.1)
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        print(f"[+] Connected to {port}! Silicon ready.\n")
    except Exception as e:
        print(f"[-] Error opening {port}: {e}")
        return

    print("WATCH YOUR ARTY S7 BOARD LEDS CAREFULLY:")
    print("  LED 0 (LD0, Pin E18 Green) : SOLID ON (System Ready)")
    print("  LED 1 (LD1, Pin F13 Green) : PACKET INGRESS SYNC (Flashes/Glows when ITCH arrives)")
    print("  LED 2 (LD2, Pin E13 Green) : NEUROMORPHIC SPIKE (Flashes on LIF Action Potential)")
    print("  LED 3 (LD3, Pin H15 Green) : RISK APPROVED (Flashes on Cleared Execution)")
    print("  RGB 0 (LD4, Pins J15/G17/F15): SOLID GREEN = Clean | FLASHES RED = Breaker Tripped\n")

    input(">>> Press ENTER to start Sequence 1: Compliant Order Inflow (watch LD1 & LD3 blink green)... ")

    print("\n[*] Sequence 1: 15 Compliant Orders (100 shares @ $185.00)...")
    for i in range(1, 16):
        pkt = build_itch_packet(i, 'B', 100, "AAPL    ", 1850000)
        ser.write(pkt)
        time.sleep(0.12)
        print(f"    -> Ingested Order #{i:02d}: LD3 Approved (GREEN), LD1 Sync (GREEN)")

    time.sleep(1.0)
    print("\n" + "-" * 80)
    input(">>> Press ENTER to start Sequence 2: Neuromorphic Spike Burst (watch LD2 flash bright green)... ")

    print("\n[*] Sequence 2: 8 High-Volatility Sweeps (5,000 shares @ $180.00)...")
    for i in range(101, 109):
        pkt = build_itch_packet(i, 'S', 5000, "AAPL    ", 1800000)
        ser.write(pkt)
        time.sleep(0.15)
        print(f"    -> Ingested Toxic Sweep #{i:03d}: [LD2 SPIKE FLASHED GREEN!]")

    time.sleep(1.0)
    print("\n" + "-" * 80)
    input(">>> Press ENTER to start Sequence 3: Fat-Finger Price Breach (watch RGB0 turn RED)... ")

    print("\n[*] Sequence 3: Injecting 3 Fat-Finger Breaches ($250.00 vs $185.00 mid)...")
    for i in range(201, 204):
        pkt = build_itch_packet(i, 'B', 500, "AAPL    ", 2500000)
        ser.write(pkt)
        time.sleep(0.3)
        print(f"    -> Fat-Finger Breach #{i:03d}: [RGB0 FLASHED BLINDING RED! LD3 OFF!]")

    ser.close()
    print("\n" + "=" * 80)
    print("   FPGA HARDWARE DEMONSTRATION COMPLETE!")
    print("=" * 80 + "\n")

if __name__ == "__main__":
    p = sys.argv[1] if len(sys.argv) > 1 else "COM9"
    b = int(sys.argv[2]) if len(sys.argv) > 2 else 921600
    run_led_show(p, b)
