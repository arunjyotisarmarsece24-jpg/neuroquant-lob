"""
================================================================================
NEUROQUANT-LOB: AUTOMATED PHYSICAL ARTY S7 FPGA LED SHOW
================================================================================
"""
import sys
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

def run_auto_show(port="COM9", baud=921600):
    print("=" * 80)
    print(f"   STARTING AUTOMATED FPGA LED SHOW ON {port} @ {baud} BAUD")
    print("=" * 80)
    
    try:
        ser = serial.Serial(port=port, baudrate=baud, timeout=0.1)
        ser.reset_input_buffer()
        ser.reset_output_buffer()
    except Exception as e:
        print(f"[-] Could not open {port}: {e}")
        return

    print("[PHASE 1] Blinking LD1 (Sync) and LD3 (Approved) with 10 normal orders...")
    for i in range(1, 11):
        pkt = build_itch_packet(i, 'B', 100, "AAPL    ", 1850000)
        ser.write(pkt)
        time.sleep(0.1)
    
    time.sleep(0.8)

    print("[PHASE 2] Blinking LD2 (LIF Neuromorphic Action Potential Spike) with 8 sweeps...")
    for i in range(50, 58):
        pkt = build_itch_packet(i, 'S', 5000, "AAPL    ", 1800000)
        ser.write(pkt)
        time.sleep(0.12)

    time.sleep(0.8)

    print("[PHASE 3] Triggering RGB0 RED (Fat-Finger Breach & Circuit Breaker)...")
    for i in range(90, 95):
        pkt = build_itch_packet(i, 'B', 200, "AAPL    ", 2500000)
        ser.write(pkt)
        time.sleep(0.15)

    ser.close()
    print("=" * 80)
    print("   AUTOMATED FPGA LED SHOW COMPLETED SUCCESSFULLY!")
    print("=" * 80)

if __name__ == "__main__":
    p = sys.argv[1] if len(sys.argv) > 1 else "COM9"
    b = int(sys.argv[2]) if len(sys.argv) > 2 else 921600
    run_auto_show(p, b)
