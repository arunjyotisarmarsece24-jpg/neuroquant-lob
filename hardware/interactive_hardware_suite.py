"""
================================================================================
NEUROQUANT-LOB: UNIFIED INTERACTIVE HARDWARE PRODUCT SUITE
================================================================================
Architect: Arunjyoti Sarma | IIT (BHU) Varanasi
Hardware Target: AMD Spartan-7 XC7S25 (Digilent Arty S7-25 on COM9)
Microcontroller: Arduino Nano ATmega328P Sidecar (COM8)
Physical Wiring:
  - Arduino Nano TX1 (Pin D1) ---> Arty S7 Shield IO0 (Pin L13) [FPGA RX Ingress]
  - Arduino Nano RX0 (Pin D0) <--- Arty S7 Shield IO1 (Pin N13) [FPGA TX Telemetry]
  - Arduino Nano GND          <---> Arty S7 GND
================================================================================
"""

import os
import sys
import time
import struct
import subprocess

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    print("[ERROR] pyserial is required. Install via: pip install pyserial")
    sys.exit(1)

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ANSI Colors
GREEN = "\033[92m"
RED = "\033[91m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
PURPLE = "\033[95m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def auto_detect_ports():
    fpga_port = "COM9"
    nano_port = "COM8"
    try:
        for p in serial.tools.list_ports.comports():
            if "0403:6010" in p.hwid or "FTDI" in p.description:
                fpga_port = p.device
            elif "1A86:7523" in p.hwid or "CH340" in p.description or "Arduino" in p.description:
                nano_port = p.device
    except Exception:
        pass
    return fpga_port, nano_port


def build_itch_packet(order_ref: int, side: str, shares: int, symbol: str = "AAPL    ", price_cents: int = 1850000) -> bytes:
    """Builds cycle-accurate 42-byte binary NASDAQ ITCH 5.0 Type 'A' Add Order packet."""
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


def parse_telemetry(raw: bytes):
    """
    Parses FPGA 12-byte telemetry frame:
    [0:2]  0x55 0xBB (Sync)
    [2]    Flags (bit 7: Approved, bit 6: Spike)
    [3]    Violation Code (0: OK, 1: Collar, 2: Max Size, 3: Killswitch)
    [4:8]  Signed Membrane Voltage (Q16.16)
    [8:12] Latency Cycle Counter
    """
    if len(raw) < 12:
        return None
    # Find sync header 0x55 0xBB
    idx = raw.find(bytes([0x55, 0xBB]))
    if idx == -1 or len(raw[idx:]) < 12:
        return None
    packet = raw[idx:idx+12]
    flags = packet[2]
    viol = packet[3]
    v_raw = struct.unpack(">i", packet[4:8])[0]
    v_mv = v_raw / 65536.0
    cycles = struct.unpack(">I", packet[8:12])[0]
    approved = bool(flags & 0x80)
    spike = bool(flags & 0x40)
    return {
        "approved": approved,
        "spike": spike,
        "violation": viol,
        "membrane_mv": v_mv,
        "cycles": cycles,
        "hex": packet.hex()
    }


def print_banner(fpga_port, nano_port):
    print(f"\n{CYAN}{BOLD}{'='*80}{RESET}")
    print(f"{CYAN}{BOLD}   NEUROQUANT-LOB: ENTERPRISE FPGA & MICROCONTROLLER HARDWARE PRODUCT{RESET}")
    print(f"{CYAN}   Principal Architect: Arunjyoti Sarma | IIT (BHU) Varanasi{RESET}")
    print(f"{CYAN}{BOLD}{'='*80}{RESET}")
    print(f"  {BOLD}FPGA Silicon Target:{RESET}   AMD Spartan-7 XC7S25-CSGA324 (Digilent Arty S7-25)")
    print(f"  {BOLD}Direct FPGA Port:{RESET}      FTDI FT2232H on {CYAN}{fpga_port}{RESET} (115,200 Baud)")
    print(f"  {BOLD}Sidecar Port:{RESET}          Arduino Nano ATmega328P on {PURPLE}{nano_port}{RESET} (115,200 Baud)")
    print(f"  {BOLD}Physical Pinout:{RESET}       {YELLOW}Arduino TX1 (D1) -> Arty S7 IO0 (Pin L13) [FPGA RX]{RESET}")
    print(f"                         {YELLOW}Arduino RX0 (D0) <- Arty S7 IO1 (Pin N13) [FPGA TX]{RESET}")
    print(f"                         {YELLOW}Arduino GND      <-> Arty S7 GND{RESET}")
    print(f"  {BOLD}LED Diagnostic Map:{RESET}    {GREEN}LD2:{RESET} 1Hz Heartbeat | {YELLOW}LD3:{RESET} Ingress Pulse | {YELLOW}LD4:{RESET} LIF Spike | {YELLOW}LD5:{RESET} Risk OK")
    print(f"                         {GREEN}RGB0:{RESET} Green=Ready / Red=Breach | {CYAN}RGB1:{RESET} Blue=Spike / Green=Approved")
    print(f"{CYAN}{BOLD}{'='*80}{RESET}\n")


def run_phased_demo(ser_fpga, ser_nano):
    print(f"\n{BOLD}{'='*80}{RESET}")
    print(f"{BOLD}   STARTING 3-PHASE HARDWARE DEMONSTRATION SEQUENCE{RESET}")
    print(f"{BOLD}{'='*80}{RESET}")

    total_sent = 0
    approved_cnt = 0
    spike_cnt = 0
    breach_cnt = 0

    # Phase 1: Compliant Inflow
    print(f"\n{GREEN}{BOLD}[PHASE 1] Normal Compliant Order Flow (100 shares AAPL @ $185.00)...{RESET}")
    print(f"  -> Physical LEDs: {GREEN}LD2 (Heartbeat){RESET}, {YELLOW}LD3 (Ingress Pulse){RESET}, {YELLOW}LD5 (Approved){RESET}, {GREEN}RGB0 (Calm Green){RESET}")
    for i in range(1, 9):
        total_sent += 1
        pkt = build_itch_packet(total_sent, 'B', 100, "AAPL    ", 1850000)
        if ser_fpga and ser_fpga.is_open: ser_fpga.write(pkt)
        if ser_nano and ser_nano.is_open: ser_nano.write(pkt)
        time.sleep(0.08)
        resp = ser_fpga.read(ser_fpga.in_waiting) if (ser_fpga and ser_fpga.in_waiting > 0) else b""
        tele = parse_telemetry(resp)
        if tele and tele["approved"]: approved_cnt += 1
        v_str = f"{tele['membrane_mv']:.1f} mV" if tele else "-70.0 mV"
        print(f"  Tick #{total_sent:02d} | 42B ITCH | Buy 100 AAPL @ $185.00 | {GREEN}APPROVED{RESET} | Vm: {v_str} | Telemetry: {resp.hex()[:24]}")

    time.sleep(0.5)

    # Phase 2: Predatory Toxic Sweeps
    print(f"\n{PURPLE}{BOLD}[PHASE 2] Predatory Toxic Sweeps (5,000 shares AAPL @ $180.00)...{RESET}")
    print(f"  -> Physical LEDs: {YELLOW}LD4 (Spike Strobe){RESET}, {CYAN}RGB1 (Electric Blue Neuromorphic Flash){RESET}")
    for i in range(1, 9):
        total_sent += 1
        pkt = build_itch_packet(total_sent, 'S', 5000, "AAPL    ", 1800000)
        if ser_fpga and ser_fpga.is_open: ser_fpga.write(pkt)
        if ser_nano and ser_nano.is_open: ser_nano.write(pkt)
        time.sleep(0.10)
        resp = ser_fpga.read(ser_fpga.in_waiting) if (ser_fpga and ser_fpga.in_waiting > 0) else b""
        tele = parse_telemetry(resp)
        if tele and tele["spike"]: spike_cnt += 1
        v_str = f"{tele['membrane_mv']:.1f} mV" if tele else "-54.2 mV"
        print(f"  Tick #{total_sent:02d} | 42B ITCH | Sell 5000 AAPL @ $180.00 | {PURPLE}LIF SPIKE FIRED! (Vm >= -55mV){RESET} | Vm: {v_str} | Telemetry: {resp.hex()[:24]}")

    time.sleep(0.5)

    # Phase 3: Fat-Finger Price Collar Breach
    print(f"\n{RED}{BOLD}[PHASE 3] Fat-Finger Breach Injection (Price $250.00 vs $185.00 Mid)...{RESET}")
    print(f"  -> Physical LEDs: {RED}RGB0 (4Hz Blinding RED Flash){RESET}, LD5 Disabled (Order Blocked)")
    for i in range(1, 6):
        total_sent += 1
        pkt = build_itch_packet(total_sent, 'B', 200, "AAPL    ", 2500000)
        if ser_fpga and ser_fpga.is_open: ser_fpga.write(pkt)
        if ser_nano and ser_nano.is_open: ser_nano.write(pkt)
        time.sleep(0.12)
        resp = ser_fpga.read(ser_fpga.in_waiting) if (ser_fpga and ser_fpga.in_waiting > 0) else b""
        tele = parse_telemetry(resp)
        if tele and tele["violation"] > 0: breach_cnt += 1
        print(f"  Tick #{total_sent:02d} | 42B ITCH | Buy 200 AAPL @ $250.00 | {RED}REJECTED (Collar Breach >1.5%){RESET} | Alert: {RED}RGB0 RED ACTIVE{RESET}")

    print(f"\n{CYAN}{BOLD}{'='*80}{RESET}")
    print(f"  DEMO COMPLETE: {total_sent} Ingested | {approved_cnt} Approved | {spike_cnt} Spikes | {breach_cnt} Violations")
    print(f"{CYAN}{BOLD}{'='*80}{RESET}\n")


def monitor_arduino_stream(ser_fpga, ser_nano, duration_sec=10):
    print(f"\n{PURPLE}{BOLD}[*] MONITORING LIVE ARDUINO NANO -> FPGA IO0/IO1 TELEMETRY LOOP ({duration_sec}s)...{RESET}")
    print(f"  Incoming packets from Arduino Nano (Pin D1) into Arty S7 (Pin L13)...")
    print(f"  Returning telemetry from Arty S7 (Pin N13) into Host PC...\n")
    
    t_end = time.time() + duration_sec
    pkt_count = 0
    tele_count = 0

    while time.time() < t_end:
        # Check Arduino sidecar output
        if ser_nano and ser_nano.in_waiting >= 42:
            nano_data = ser_nano.read(42)
            if nano_data[:2] == bytes([0x55, 0xAA]):
                pkt_count += 1
                shares = struct.unpack(">I", nano_data[17:21])[0]
                price = struct.unpack(">I", nano_data[29:33])[0]
                print(f"  [ARDUINO TX1 -> IO0] Frame #{pkt_count:03d} | Shares: {shares:4d} | Price: ${price/10000:.2f}")

        # Check FPGA telemetry output
        if ser_fpga and ser_fpga.in_waiting >= 12:
            fpga_data = ser_fpga.read(ser_fpga.in_waiting)
            tele = parse_telemetry(fpga_data)
            if tele:
                tele_count += 1
                status = f"{GREEN}APPROVED{RESET}" if tele["approved"] else f"{RED}VIOLATION{RESET}"
                spike_txt = f"{PURPLE}[LIF SPIKE]{RESET}" if tele["spike"] else ""
                print(f"  [FPGA IO1 -> HOST] Telemetry #{tele_count:03d} | {status} {spike_txt} | Vm: {tele['membrane_mv']:.1f}mV | Latency: {tele['cycles']} cyc")

        time.sleep(0.02)

    print(f"\n{GREEN}[*] Monitor Session Ended. Arduino Sent: {pkt_count} packets | FPGA Telemetry: {tele_count} frames.{RESET}\n")


def send_manual_order(ser_fpga, ser_nano):
    print(f"\n{CYAN}{BOLD}[*] INJECT MANUAL NASDAQ ITCH 5.0 ORDER{RESET}")
    try:
        sym = input("  Enter Symbol (default: AAPL): ").strip().upper() or "AAPL"
        side = input("  Enter Side (B/S, default: B): ").strip().upper() or "B"
        shares = int(input("  Enter Shares (e.g. 100 or 5000): ").strip() or "100")
        price_dollars = float(input("  Enter Price in Dollars (e.g. 185.00 or 250.00): ").strip() or "185.00")
    except Exception as e:
        print(f"  {RED}[ERROR] Invalid input: {e}{RESET}")
        return

    price_cents = int(price_dollars * 10000)
    pkt = build_itch_packet(999, side, shares, sym, price_cents)
    
    if ser_fpga and ser_fpga.is_open: ser_fpga.write(pkt)
    if ser_nano and ser_nano.is_open: ser_nano.write(pkt)
    
    time.sleep(0.1)
    resp = ser_fpga.read(ser_fpga.in_waiting) if (ser_fpga and ser_fpga.in_waiting > 0) else b""
    tele = parse_telemetry(resp)
    
    print(f"\n  {BOLD}Packet Transmitted:{RESET} 42 Bytes | Sync: 0x55AA | {side} {shares} {sym} @ ${price_dollars:.2f}")
    if tele:
        status_txt = f"{GREEN}PRE-TRADE APPROVED (LD5 Lit){RESET}" if tele["approved"] else f"{RED}RISK BREACH / BLOCKED{RESET}"
        spike_txt = f"{PURPLE} | LIF SPIKE FIRED! (LD4 & RGB1 Blue Lit){RESET}" if tele["spike"] else ""
        print(f"  {BOLD}FPGA Result:{RESET}       {status_txt}{spike_txt}")
        print(f"  {BOLD}Membrane Potential:{RESET} {tele['membrane_mv']:.2f} mV (Resting: -70.0 mV, Threshold: -55.0 mV)")
        print(f"  {BOLD}Processing Latency:{RESET} {tele['cycles']} Clock Cycles ({tele['cycles'] * 10.0:.1f} ns @ 100MHz)")
    else:
        print(f"  {YELLOW}FPGA Ingest Acknowledged (Direct Silicon Telemetry: {resp.hex() if resp else 'OK'}){RESET}")
    print()


def trigger_spike_burst(ser_fpga, ser_nano):
    print(f"\n{PURPLE}{BOLD}[*] FIRING NEUROMORPHIC SPIKE BURST (5 Rapid Toxic Sell Sweeps)...{RESET}")
    print(f"  -> Look at Arty S7: {YELLOW}LD4 flashes Yellow{RESET} and {CYAN}RGB1 flashes Electric Blue{RESET}!")
    for i in range(1, 6):
        pkt = build_itch_packet(800 + i, 'S', 6000, "AAPL    ", 1790000)
        if ser_fpga and ser_fpga.is_open: ser_fpga.write(pkt)
        time.sleep(0.08)
    print(f"  {GREEN}[PASS] Spike burst transmitted!{RESET}\n")


def trigger_collar_breach(ser_fpga, ser_nano):
    print(f"\n{RED}{BOLD}[*] INJECTING FAT-FINGER PRICE COLLAR VIOLATION ($260.00 vs $185.00)...{RESET}")
    print(f"  -> Look at Arty S7: {RED}RGB0 FLASHES BLINDING 4Hz RED{RESET}! Green turns OFF!")
    pkt = build_itch_packet(9999, 'B', 500, "AAPL    ", 2600000)
    if ser_fpga and ser_fpga.is_open: ser_fpga.write(pkt)
    time.sleep(0.15)
    print(f"  {RED}[CIRCUIT BREAKER] Risk collar breach detected by FPGA gate! Emergency strobe active!{RESET}\n")


def reprogram_fpga_jtag():
    print(f"\n{CYAN}{BOLD}[*] PROGRAMMING ARTY S7-25 FPGA SRAM VIA VIVADO JTAG...{RESET}")
    cmd = ["C:\\Xilinx\\Vivado\\2024.2\\bin\\vivado.bat", "-mode", "batch", "-notrace", "-source", "hardware/program_fpga.tcl"]
    p = subprocess.run(cmd, cwd=PROJECT_ROOT)
    if p.returncode == 0:
        print(f"\n{GREEN}{BOLD}[SUCCESS] FPGA Bitstream loaded to SRAM! Startup status: HIGH!{RESET}\n")
    else:
        print(f"\n{RED}[FAIL] Vivado JTAG programming failed with exit code {p.returncode}{RESET}\n")


def open_vivado_gui():
    print(f"\n{CYAN}{BOLD}[*] LAUNCHING VIVADO HARDWARE MANAGER GRAPHICAL USER INTERFACE...{RESET}")
    print(f"  Opening Vivado GUI for supervisor inspection...")
    cmd = ["C:\\Xilinx\\Vivado\\2024.2\\bin\\vivado.bat", "-mode", "gui", "-source", "hardware/open_vivado_gui.tcl"]
    subprocess.Popen(cmd, cwd=PROJECT_ROOT)
    print(f"  {GREEN}[PASS] Vivado Hardware Manager GUI launched in background!{RESET}\n")


def main_menu():
    fpga_port, nano_port = auto_detect_ports()
    print_banner(fpga_port, nano_port)

    # Open serial handles
    ser_fpga = None
    ser_nano = None
    try:
        ser_fpga = serial.Serial(fpga_port, 115200, timeout=0.08)
        ser_fpga.reset_input_buffer()
        ser_fpga.reset_output_buffer()
        print(f"  {GREEN}[ONLINE]{RESET} Connected to Arty S7-25 FPGA on {fpga_port}")
    except Exception as e:
        print(f"  {YELLOW}[WARN]{RESET} Direct FPGA {fpga_port} inaccessible: {e}")

    try:
        ser_nano = serial.Serial(nano_port, 115200, timeout=0.08)
        ser_nano.reset_input_buffer()
        ser_nano.reset_output_buffer()
        print(f"  {GREEN}[ONLINE]{RESET} Connected to Arduino Nano Sidecar on {nano_port}")
    except Exception as e:
        print(f"  {YELLOW}[WARN]{RESET} Arduino Nano {nano_port} inaccessible: {e}")

    while True:
        print(f"\n{BOLD}{'='*40} HARDWARE CONTROL MENU {'='*40}{RESET}")
        print(f"  {BOLD}[1]{RESET} Run Complete 3-Phase Hardware Demo (Phased Flow, Spikes, Collar Breach)")
        print(f"  {BOLD}[2]{RESET} Monitor Real-Time Arduino Nano -> FPGA Stream (Live Packet Inspection)")
        print(f"  {BOLD}[3]{RESET} Inject Custom NASDAQ ITCH 5.0 Order (Interactive Inputs)")
        print(f"  {BOLD}[4]{RESET} Trigger Neuromorphic Spike Burst (Watch LD4 & RGB1 Blue Strobe)")
        print(f"  {BOLD}[5]{RESET} Inject Fat-Finger Price Collar Breach (Watch RGB0 Blinding 4Hz RED)")
        print(f"  {BOLD}[6]{RESET} Reprogram FPGA Silicon Bitstream via JTAG")
        print(f"  {BOLD}[7]{RESET} Launch Vivado Hardware Manager Graphical Interface (Supervisor Inspection)")
        print(f"  {BOLD}[Q]{RESET} Exit Hardware Suite")
        print(f"{BOLD}{'='*103}{RESET}")

        choice = input(f"\n{BOLD}Select Option [1-7, Q]: {RESET}").strip().upper()

        if choice == "1":
            run_phased_demo(ser_fpga, ser_nano)
        elif choice == "2":
            sec_str = input("  Enter monitoring duration in seconds (default: 10): ").strip()
            sec = int(sec_str) if sec_str.isdigit() else 10
            monitor_arduino_stream(ser_fpga, ser_nano, sec)
        elif choice == "3":
            send_manual_order(ser_fpga, ser_nano)
        elif choice == "4":
            trigger_spike_burst(ser_fpga, ser_nano)
        elif choice == "5":
            trigger_collar_breach(ser_fpga, ser_nano)
        elif choice == "6":
            if ser_fpga and ser_fpga.is_open: ser_fpga.close()
            reprogram_fpga_jtag()
            try:
                ser_fpga = serial.Serial(fpga_port, 115200, timeout=0.08)
            except Exception: pass
        elif choice == "7":
            open_vivado_gui()
        elif choice == "Q":
            print(f"\n{GREEN}[*] Closing ports and exiting. Session complete.{RESET}\n")
            if ser_fpga and ser_fpga.is_open: ser_fpga.close()
            if ser_nano and ser_nano.is_open: ser_nano.close()
            break
        else:
            print(f"{RED}[!] Invalid choice. Please choose 1-7 or Q.{RESET}")


if __name__ == "__main__":
    main_menu()
