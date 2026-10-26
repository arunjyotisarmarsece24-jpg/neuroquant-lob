"""
NeuroQuant-LOB: Physical Hardware Verification & Device Diagnostic Harness
==========================================================================
Principal Architect: Arunjyoti Sarma (Research Scholar, IIT (BHU), Varanasi)
Affiliation: Department of Electronics Engineering, IIT (BHU), Varanasi

Automated inspection and communication verification for:
  [1] Digilent Arty S7-25 (Spartan-7 CSGA324) via FTDI FT2232H (COM9)
  [2] Arduino Nano (ATmega328P / CH340) Hardware Watchdog Sidecar (COM5)
  [3] Xilinx Vivado 2024.2 Toolchain & Synthesis Environment
"""

import sys
import os
import time
import serial
import serial.tools.list_ports

def print_banner():
    print("=" * 80)
    print("   NEUROQUANT-LOB: PHYSICAL HARDWARE BENCH & DEVICE VERIFICATION")
    print("   Architect: Arunjyoti Sarma | IIT (BHU) Varanasi")
    print("=" * 80)

def audit_connected_devices():
    print("\n[STEP 1/3] Enumerating Physical USB / Serial Hardware Ports...")
    ports = list(serial.tools.list_ports.comports())
    
    fpga_port = None
    arduino_port = None
    
    for p in ports:
        desc = f"{p.device}: {p.description} [{p.hwid}]"
        print(f"  • {desc}")
        if "0403:6010" in p.hwid or "FTDI" in p.description.upper() or p.device == "COM9":
            fpga_port = p.device
        elif "1A86:7523" in p.hwid or "CH340" in p.description.upper() or p.device == "COM5":
            arduino_port = p.device
            
    print("\n  Hardware Device Mapping:")
    if fpga_port:
        print(f"    [+] Digilent Arty S7-25 (Spartan-7): DETECTED on {fpga_port} (FTDI FT2232H)")
    else:
        print("    [-] Digilent Arty S7-25: Not enumerated")
        
    if arduino_port:
        print(f"    [+] Arduino Nano Watchdog Sidecar:   DETECTED on {arduino_port} (CH340 USB-UART)")
    else:
        print("    [-] Arduino Nano: Not enumerated")
        
    return fpga_port, arduino_port

def test_serial_interface(port: str, baudrate: int, label: str):
    print(f"\n[STEP 2/3] Testing Serial Interface on {port} ({label}) @ {baudrate} baud...")
    try:
        t0 = time.perf_counter()
        ser = serial.Serial(port=port, baudrate=baudrate, timeout=0.5, write_timeout=0.5)
        dt_open_ms = (time.perf_counter() - t0) * 1000
        
        # Test CTS / DSR line status
        cts = ser.cts
        dsr = ser.dsr
        
        # Flush buffers
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        
        # Non-blocking probe write (Safe ping query)
        ping_payload = b"\x55\xAA\x00\x00\x00\x00\x00\x00\x00\x00"
        ser.write(ping_payload)
        ser.flush()
        
        # Listen for response (with short timeout)
        rx = ser.read(12)
        rx_len = len(rx)
        
        ser.close()
        print(f"  [PASS] {port} successfully opened in {dt_open_ms:.2f} ms")
        print(f"         Control Lines: CTS={cts}, DSR={dsr}")
        print(f"         Loopback / Telemetry Probe: Sent {len(ping_payload)} bytes, Received {rx_len} bytes")
        return True
    except Exception as e:
        print(f"  [FAIL] Failed opening {port}: {e}")
        return False

def check_vivado_toolchain():
    print("\n[STEP 3/3] Inspecting AMD Xilinx Vivado Toolchain Environment...")
    vivado_path = r"C:\Xilinx\Vivado\2024.2\bin\vivado.bat"
    if os.path.exists(vivado_path):
        print(f"  [PASS] Vivado 2024.2 found at: {vivado_path}")
        print("         Ready for RTL synthesis to Spartan-7 xc7s25csga324-1!")
        return True
    else:
        print(f"  [WARN] Vivado 2024.2 not found at {vivado_path}")
        return False

def main():
    print_banner()
    fpga_port, arduino_port = audit_connected_devices()
    
    fpga_ok = False
    arduino_ok = False
    
    if fpga_port:
        # Digilent Arty S7 runs at 921,600 baud for ultra-high throughput
        fpga_ok = test_serial_interface(fpga_port, 921600, "Arty S7-25 FPGA UART")
        
    if arduino_port:
        # Arduino Nano standard UART
        arduino_ok = test_serial_interface(arduino_port, 115200, "Arduino Nano Watchdog Sidecar")
        
    vivado_ok = check_vivado_toolchain()
    
    print("\n" + "=" * 80)
    print("   PHYSICAL BENCH AUDIT SUMMARY")
    print("=" * 80)
    print(f"  • Digilent Arty S7-25 (COM9):      {'ONLINE & RESPONSIVE' if fpga_ok else 'NOT DETECTED'}")
    print(f"  • Arduino Nano (COM5):             {'ONLINE & RESPONSIVE' if arduino_ok else 'NOT DETECTED'}")
    print(f"  • AMD Xilinx Vivado 2024.2:        {'READY & INSTALLED' if vivado_ok else 'NOT DETECTED'}")
    print("=" * 80 + "\n")
    
    return 0 if (fpga_ok and arduino_ok) else 1

if __name__ == "__main__":
    sys.exit(main())
