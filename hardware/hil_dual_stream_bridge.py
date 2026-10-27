"""
NeuroQuant-LOB: Hardware-in-the-Loop (HIL) Dual-Stream Co-Processor Bridge (Day 6)
==================================================================================
Manages real-time concurrent serial streams between:
  1. Microcontroller Sidecar: Arduino Nano (ATmega328P on COM5 @ 115,200 baud)
     - Streams 42-byte synthetic NASDAQ ITCH 5.0 binary order frames.
  2. Institutional FPGA Accelerator: Digilent Arty S7-25 (Spartan-7 on COM9 @ 115,200 baud)
     - Parses ITCH frames, computes neuromorphic LIF membrane influx, executes
       single-cycle pre-trade risk checks, and streams back 12-byte telemetry packets.
  3. Python Web & SIMD Host Bridge:
     - Merges live physical telemetry into Web Dashboard, REST APIs, and C++ SIMD venue.

Author: Arunjyoti Sarma (Research Scholar, IIT (BHU), Varanasi)
"""

from __future__ import annotations
import os
import sys
import time
import struct
import threading
from collections import deque
from typing import Dict, Any, Optional, List

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    serial = None

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def build_itch_packet(order_ref: int, side: str, shares: int, symbol: str = "AAPL    ", price_cents: int = 1850000) -> bytes:
    """Builds a cycle-accurate 42-byte NASDAQ ITCH 5.0 binary Type 'A' Add Order packet."""
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


class HILDualStreamBridge:
    """
    Thread-safe Hardware-in-the-Loop Bridge connecting Arduino Nano (COM5)
    and Spartan-7 FPGA (COM9) with asynchronous forwarding and telemetry parsing.
    """

    def __init__(self, fpga_port: str = "COM9", nano_port: str = "COM5", baud_rate: int = 115200):
        self.fpga_port = fpga_port
        self.nano_port = nano_port
        self.baud_rate = baud_rate

        # Auto-detect physical hardware serial ports if available
        if serial is not None:
            try:
                for p in serial.tools.list_ports.comports():
                    if "0403:6010" in p.hwid or "FTDI" in p.description:
                        self.fpga_port = p.device
                    elif "1A86:7523" in p.hwid or "CH340" in p.description or "Arduino" in p.description:
                        self.nano_port = p.device
            except Exception:
                pass

        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None

        self.ser_fpga: Optional[Any] = None
        self.ser_nano: Optional[Any] = None

        self.fpga_connected = False
        self.nano_connected = False

        # Live Telemetry State
        self.total_orders_forwarded = 0
        self.total_telemetry_received = 0
        self.last_voltage_mv = -75.0
        self.last_latency_cycles = 1230
        self.last_latency_us = 12.30
        self.last_status_flags = 0x8000
        self.spike_detected = False
        self.killswitch_tripped = False
        self.itch_valid_pulse = False
        self.recent_telemetry: deque = deque(maxlen=50)

        self._last_tick_time = time.perf_counter()
        self.throughput_ops = 0.0

    def connect(self) -> Dict[str, bool]:
        """Attempts connection to physical FPGA and Arduino Nano."""
        if serial is None:
            return {"fpga": False, "nano": False, "error": "pyserial not installed"}

        with self._lock:
            # Connect FPGA
            try:
                if self.ser_fpga is None or not self.ser_fpga.is_open:
                    self.ser_fpga = serial.Serial(self.fpga_port, self.baud_rate, timeout=0.05)
                    self.ser_fpga.reset_input_buffer()
                    self.ser_fpga.reset_output_buffer()
                self.fpga_connected = True
            except Exception as e:
                self.fpga_connected = False
                self.ser_fpga = None

            # Connect Arduino Nano
            try:
                if self.ser_nano is None or not self.ser_nano.is_open:
                    self.ser_nano = serial.Serial(self.nano_port, self.baud_rate, timeout=0.05)
                    self.ser_nano.reset_input_buffer()
                    self.ser_nano.reset_output_buffer()
                self.nano_connected = True
            except Exception as e:
                self.nano_connected = False
                self.ser_nano = None

            return {"fpga": self.fpga_connected, "nano": self.nano_connected}

    def start_background_forwarder(self):
        """Starts asynchronous background worker thread for continuous HIL stream forwarding."""
        if self._running:
            return
        self.connect()
        self._running = True
        self._thread = threading.Thread(target=self._forwarding_loop, daemon=True)
        self._thread.start()

    def stop_background_forwarder(self):
        """Stops asynchronous background forwarding."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self.disconnect()

    def disconnect(self):
        with self._lock:
            if self.ser_fpga and self.ser_fpga.is_open:
                try:
                    self.ser_fpga.close()
                except Exception:
                    pass
            if self.ser_nano and self.ser_nano.is_open:
                try:
                    self.ser_nano.close()
                except Exception:
                    pass
            self.ser_fpga = None
            self.ser_nano = None
            self.fpga_connected = False
            self.nano_connected = False

    def inject_order(self, shares: int = 100, price_cents: int = 1850000, side: str = "B", order_ref: Optional[int] = None) -> bool:
        """Injects a custom synthetic ITCH packet into the physical FPGA on COM9."""
        if not self.fpga_connected or self.ser_fpga is None:
            self.connect()
        if not self.fpga_connected:
            return False

        if order_ref is None:
            order_ref = (self.total_orders_forwarded + 1) & 0xFFFFFF

        pkt = build_itch_packet(order_ref=order_ref, side=side, shares=shares, price_cents=price_cents)
        with self._lock:
            try:
                self.ser_fpga.write(pkt)
                self.total_orders_forwarded += 1
                time.sleep(0.04)
                self._poll_fpga_telemetry_locked()
                return True
            except Exception:
                return False

    def _poll_fpga_telemetry_locked(self):
        """Polls available telemetry bytes from COM9 and decodes 12-byte telemetry frames."""
        if not self.ser_fpga or not self.ser_fpga.is_open:
            return

        in_wait = self.ser_fpga.in_waiting
        if in_wait >= 12:
            raw = self.ser_fpga.read(in_wait)
            # Scan for 0x55 0xBB frame header
            for i in range(len(raw) - 11):
                if raw[i] == 0x55 and raw[i + 1] == 0xBB:
                    frame = raw[i:i + 12]
                    self._decode_telemetry_frame(frame)

    def _decode_telemetry_frame(self, frame: bytes):
        """Decodes 12-byte Verilog hardware telemetry packet from Spartan-7."""
        if len(frame) < 12:
            return

        status_flags = (frame[2] << 8) | frame[3]
        # Signed 16-bit membrane voltage
        v_raw = struct.unpack(">h", frame[4:6])[0]
        v_mv = float(v_raw)
        cycles = struct.unpack(">I", frame[6:10])[0]

        self.last_status_flags = status_flags
        self.last_voltage_mv = v_mv
        self.last_latency_cycles = cycles
        self.last_latency_us = round(cycles / 100.0, 3)

        self.spike_detected = bool(status_flags & 0x2000)
        self.itch_valid_pulse = bool(status_flags & 0x1000)
        self.killswitch_tripped = bool(status_flags & 0x0400)
        self.total_telemetry_received += 1

        t_now = time.perf_counter()
        dt = t_now - self._last_tick_time
        if dt > 0:
            self.throughput_ops = round(1.0 / dt, 1)
        self._last_tick_time = t_now

        snap = {
            "timestamp": time.strftime("%H:%M:%S"),
            "voltage_mv": self.last_voltage_mv,
            "cycles": self.last_latency_cycles,
            "latency_us": self.last_latency_us,
            "status_flags_hex": f"0x{self.last_status_flags:04X}",
            "spike": self.spike_detected,
            "itch_valid": self.itch_valid_pulse,
            "killswitch": self.killswitch_tripped
        }
        self.recent_telemetry.append(snap)

    def _forwarding_loop(self):
        """Continuously reads frames from COM5 (Nano) and forwards them to COM9 (FPGA)."""
        buf = bytearray()
        while self._running:
            try:
                # 1. Read from Arduino Nano (COM5)
                if self.ser_nano and self.ser_nano.is_open:
                    n_avail = self.ser_nano.in_waiting
                    if n_avail > 0:
                        chunk = self.ser_nano.read(n_avail)
                        buf.extend(chunk)

                        # Look for 42-byte packets starting with 0x55 0xAA
                        while len(buf) >= 42:
                            idx = buf.find(b"\x55\xAA")
                            if idx == -1:
                                buf.clear()
                                break
                            if idx > 0:
                                del buf[:idx]

                            if len(buf) >= 42:
                                pkt = bytes(buf[:42])
                                del buf[:42]

                                # Forward directly to Spartan-7 FPGA (COM9)
                                with self._lock:
                                    if self.ser_fpga and self.ser_fpga.is_open:
                                        self.ser_fpga.write(pkt)
                                        self.total_orders_forwarded += 1

                # 2. Poll FPGA telemetry response
                with self._lock:
                    self._poll_fpga_telemetry_locked()

                time.sleep(0.01)
            except Exception:
                time.sleep(0.05)

    def get_status_dict(self) -> Dict[str, Any]:
        """Returns instantaneous physical hardware telemetry snapshot."""
        # Derive hardware LED illumination states
        led_state = {
            "ld0_rgb": "blue" if self.fpga_connected else "off",
            "ld1_rgb": "red" if self.killswitch_tripped else ("yellow" if self.spike_detected else "cyan"),
            "ld2_yellow": "on" if (self.last_status_flags & 0x8000) else "off",
            "ld3_yellow": "blinking",
            "ld4_yellow": "pulse" if self.itch_valid_pulse else "off",
            "ld5_yellow": "pulse" if (not self.killswitch_tripped) else "off"
        }

        return {
            "hil_active": self._running,
            "fpga_connected": self.fpga_connected,
            "nano_connected": self.nano_connected,
            "fpga_port": self.fpga_port,
            "nano_port": self.nano_port,
            "baud_rate": self.baud_rate,
            "total_orders_forwarded": self.total_orders_forwarded,
            "total_telemetry_received": self.total_telemetry_received,
            "last_voltage_mv": self.last_voltage_mv,
            "last_latency_cycles": self.last_latency_cycles,
            "last_latency_us": self.last_latency_us,
            "last_status_flags": f"0x{self.last_status_flags:04X}",
            "spike_detected": self.spike_detected,
            "killswitch_tripped": self.killswitch_tripped,
            "itch_valid": self.itch_valid_pulse,
            "throughput_ops": self.throughput_ops,
            "led_state": led_state,
            "recent_telemetry": list(self.recent_telemetry)
        }


# Global Singleton Bridge Instance
_GLOBAL_HIL_BRIDGE: Optional[HILDualStreamBridge] = None
_GLOBAL_HIL_LOCK = threading.Lock()


def get_hil_bridge() -> HILDualStreamBridge:
    global _GLOBAL_HIL_BRIDGE
    with _GLOBAL_HIL_LOCK:
        if _GLOBAL_HIL_BRIDGE is None:
            _GLOBAL_HIL_BRIDGE = HILDualStreamBridge(fpga_port="COM9", nano_port="COM8", baud_rate=115200)
            try:
                _GLOBAL_HIL_BRIDGE.start_background_forwarder()
            except Exception:
                pass
        return _GLOBAL_HIL_BRIDGE


def run_hil_cli_demo(ticks: int = 30):
    """Runs a standalone live Hardware-in-the-Loop CLI audit."""
    print("=" * 80)
    print("  NEUROQUANT-LOB: HARDWARE-IN-THE-LOOP (HIL) DUAL-STREAM AUDITOR (DAY 6)")
    print("  Target: Digilent Arty S7-25 (COM9) <---> Arduino Nano Sidecar (COM5)")
    print("=" * 80)

    bridge = get_hil_bridge()
    status = bridge.connect()
    print(f"[*] Port Status: FPGA (COM9)={status['fpga']} | Arduino Nano (COM5)={status['nano']}")

    print(f"\n[*] Starting Dual-Stream Forwarder for {ticks} ticks...")
    bridge.start_background_forwarder()

    for i in range(1, ticks + 1):
        # Inject alternating order sizes (100 shares normal, 800 shares spike trigger)
        shares = 800 if (i % 5 == 0) else 100
        bridge.inject_order(shares=shares, price_cents=1850000, side="B")
        time.sleep(0.08)

        st = bridge.get_status_dict()
        print(f"  [TICK {i:02d}] Sent {shares} shares -> FPGA Voltage: {st['last_voltage_mv']:>5.1f} mV | Latency: {st['last_latency_us']:>5.2f} us ({st['last_latency_cycles']} cyc) | Spike: {st['spike_detected']} | Flags: {st['last_status_flags']}")

    bridge.stop_background_forwarder()
    print("\n" + "=" * 80)
    print(f"  HIL STREAM AUDIT COMPLETE! Total Telemetry Packets: {bridge.total_telemetry_received}")
    print("=" * 80)


if __name__ == "__main__":
    ticks_to_run = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    run_hil_cli_demo(ticks=ticks_to_run)
