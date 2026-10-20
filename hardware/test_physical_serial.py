"""
NeuroQuant-LOB: Physical Hardware Serial Diagnostic & Loopback Runner
=====================================================================
Directly verifies the physical Digilent Arty S7 (Spartan-7) FPGA board
over a USB-UART COM port at 921,600 Baud before or in tandem with the ESP8266.

Usage:
  python hardware/test_physical_serial.py --port COM3 --baud 921600
  python hardware/test_physical_serial.py --list-ports
  python hardware/test_physical_serial.py --port COM3 --interactive

Author: Arunjyoti Sarma (Research Scholar, IIT (BHU), Varanasi)
"""

import sys
import time
import struct
import argparse

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    print("[ERROR] pyserial is required. Install via: pip install pyserial")
    sys.exit(1)


def list_available_ports():
    ports = serial.tools.list_ports.comports()
    print("\nAvailable Physical COM Ports on this System:")
    print("--------------------------------------------------")
    if not ports:
        print("  [None detected] Connect your USB-UART adapter or NodeMCU.")
    for p in ports:
        print(f"  • {p.device}: {p.description} [{p.hwid}]")
    print("--------------------------------------------------\n")


def build_itch_packet(order_ref: int, side: str, shares: int, symbol: str, price_cents: int) -> bytes:
    """
    Constructs the exact 42-byte binary frame required by the FPGA:
      [0x55, 0xAA, Beat0(8B), Beat1(8B), Beat2(8B), Beat3(8B), Beat4(8B)]
    """
    sync = bytes([0x55, 0xAA])

    # Beat 0: Type 'A' (0x41), Locate=1, Tracking=2, Timestamp_hi=0x000012
    beat0 = struct.pack(">B H H 3s", 0x41, 1, 2, bytes([0x00, 0x00, 0x12]))

    # Beat 1: Timestamp_lo=0x345678, OrderRef_hi=0x0000000000
    beat1 = struct.pack(">3s 5s", bytes([0x34, 0x56, 0x78]), bytes([0x00] * 5))

    # Beat 2: OrderRef_lo (3 bytes), Side ('B'/'S'), Shares (4 bytes Big-Endian)
    ref_lo = bytes([(order_ref >> 16) & 0xFF, (order_ref >> 8) & 0xFF, order_ref & 0xFF])
    side_b = b'B' if side.upper() == 'B' else b'S'
    beat2 = ref_lo + side_b + struct.pack(">I", shares)

    # Beat 3: Symbol padded to 8 bytes
    sym_padded = symbol.ljust(8)[:8].encode("ascii")
    beat3 = sym_padded

    # Beat 4: Price in decicents ($150.00 = 1,500,000 = 0x0016E360) + 4 bytes padding
    beat4 = struct.pack(">I 4s", price_cents, bytes([0x00] * 4))

    return sync + beat0 + beat1 + beat2 + beat3 + beat4


def decode_telemetry(packet: bytes):
    """
    Decodes the 12-byte telemetry frame returned by Arty S7:
      [0x55, 0xBB, Status(1B), Spike(1B), V_m(4B), Latency(3B), Checksum(1B)]
    """
    if len(packet) != 12:
        return None
    if packet[0] != 0x55 or packet[1] != 0xBB:
        return None

    # Verify XOR Checksum
    computed_crc = 0
    for b in packet[2:11]:
        computed_crc ^= b
    if computed_crc != packet[11]:
        return None

    status_byte = packet[2]
    approved = bool(status_byte & 0x80)
    code = status_byte & 0x7F
    spike = bool(packet[3])

    # Unpack 32-bit signed Q16.16 membrane voltage
    raw_v = struct.unpack(">i", packet[4:8])[0]
    voltage_mv = raw_v / 65536.0

    # Unpack 24-bit latency counter
    cycles = (packet[8] << 16) | (packet[9] << 8) | packet[10]
    latency_ns = cycles * 10.0  # 100 MHz clock = 10 ns

    return {
        "approved": approved,
        "code": code,
        "spike": spike,
        "voltage_mv": voltage_mv,
        "cycles": cycles,
        "latency_ns": latency_ns
    }


def run_test_stream(port_name: str, baud_rate: int = 921600, num_packets: int = 100):
    print(f"\n[*] Opening Physical Port: {port_name} at {baud_rate} Baud (8-N-1)...")
    try:
        ser = serial.Serial(port_name, baud_rate, timeout=0.1)
    except Exception as e:
        print(f"[FAIL] Could not open port {port_name}: {e}")
        return

    print("[*] Serial link established! Flushing input buffers...")
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    time.sleep(0.2)

    print(f"[*] Blasting {num_packets} binary NASDAQ ITCH 5.0 packets to Arty S7...")
    print("--------------------------------------------------------------------------------")
    print(" Pkt# | Order Ref | Side | Shares | Price ($) | Approved? | LIF Spike | Latency (ns)")
    print("--------------------------------------------------------------------------------")

    passed = 0
    telemetry_count = 0

    for i in range(1, num_packets + 1):
        side = "B" if i % 2 == 1 else "S"
        shares = 1000 if i % 5 == 0 else 200
        price_decicents = 1500000 + (i % 20) * 100  # $150.00 to $152.00
        price_dlr = price_decicents / 10000.0

        tx_frame = build_itch_packet(i, side, shares, "AAPL", price_decicents)
        ser.write(tx_frame)

        # Listen for return telemetry
        rx_raw = ser.read(12)
        if len(rx_raw) == 12:
            telem = decode_telemetry(rx_raw)
            if telem:
                telemetry_count += 1
                if telem["approved"]:
                    passed += 1
                app_str = "[APPROVED]" if telem["approved"] else f"[BLOCKED: 0x{telem['code']:02X}]"
                spk_str = "YES (Action Potential)" if telem["spike"] else "No"
                print(f" {i:4d} | {i:9d} |  {side}   | {shares:6d} | ${price_dlr:8.2f} | {app_str:10s} | {spk_str:9s} | {telem['latency_ns']:8.1f} ns")
            else:
                print(f" {i:4d} | Frame CRC / Header Mismatch")
        else:
            # Echo progress if telemetry wire is not hooked up
            if i % 10 == 0:
                print(f" {i:4d} | Sent 42-byte binary frame (TX Active)")

        time.sleep(0.01)  # 100 Hz rate

    ser.close()
    print("--------------------------------------------------------------------------------")
    print(f"[*] Physical Test Complete: {num_packets} Packets Sent | {telemetry_count} Telemetry Packets Captured")
    if telemetry_count > 0:
        print(f"[*] Execution Clearance Rate: {passed}/{telemetry_count} ({passed/telemetry_count*100:.1f}%)")
    print("--------------------------------------------------------------------------------\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NeuroQuant Physical Serial Runner")
    parser.add_argument("--port", "-p", default=None, help="COM port (e.g. COM3 or /dev/ttyUSB0)")
    parser.add_argument("--baud", "-b", type=int, default=921600, help="Baud rate (default: 921600)")
    parser.add_argument("--count", "-n", type=int, default=50, help="Number of packets to send (default: 50)")
    parser.add_argument("--list-ports", "-l", action="store_true", help="List available serial ports")
    args = parser.parse_args()

    if args.list_ports or not args.port:
        list_available_ports()
        if not args.port:
            print("[INFO] Run with: python hardware/test_physical_serial.py --port <YOUR_COM_PORT>")
            sys.exit(0)

    run_test_stream(args.port, args.baud, args.count)
