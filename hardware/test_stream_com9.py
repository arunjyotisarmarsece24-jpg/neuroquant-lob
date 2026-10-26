import serial
import time
import struct

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

def stream_com9():
    print("=" * 70)
    print("  NEUROQUANT-LOB: ARTY S7-25 DIRECT HARDWARE TELEMETRY AUDIT (COM9)")
    print("=" * 70)
    ser = serial.Serial('COM9', 115200, timeout=0.05)
    ser.reset_input_buffer()
    ser.reset_output_buffer()

    print("[*] STEP 1: Streaming 20 normal ITCH order packets (100 shares @ $185.00)...")
    rx_bytes_total = 0
    for i in range(1, 21):
        # Every 4th packet has high shares (800) to cross LIF spike threshold
        shares = 800 if (i % 4 == 0) else 100
        pkt = build_itch_packet(i, 'B', shares, "AAPL    ", 1850000)
        ser.write(pkt)
        time.sleep(0.08) # 80ms interval
        in_waiting = ser.in_waiting
        if in_waiting > 0:
            rx_data = ser.read(in_waiting)
            rx_bytes_total += len(rx_data)
            print(f"  [TICK {i:02d}] Packet Sent ({len(pkt)}B, shares={shares}) -> FPGA Telemetry Response ({len(rx_data)}B): {rx_data.hex()}")

    print(f"\n[*] Total Telemetry Bytes Received from FPGA: {rx_bytes_total} bytes")
    ser.close()
    print("=" * 70)
    print("  COM9 VERIFICATION COMPLETE!")
    print("=" * 70)

if __name__ == "__main__":
    stream_com9()
