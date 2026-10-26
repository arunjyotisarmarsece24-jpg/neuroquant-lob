"""
Unit Tests for Day 6 Hardware-in-the-Loop (HIL) Dual-Stream Co-Processor Bridge
================================================================================
Validates:
  1. NASDAQ ITCH 5.0 Type 'A' 42-byte binary packet serialization.
  2. Spartan-7 FPGA 12-byte hardware telemetry frame synchronization & decoding.
  3. Status register bitflag decoding (PLL Lock, Heartbeat, LIF Spike, Killswitch).
  4. HILDualStreamBridge state machine and mock connection handling.
  5. Flask REST API endpoints (/api/hardware/hil_status, /api/hardware/hil_inject, /api/hardware/hil_control).

Author: Arunjyoti Sarma (Research Scholar, IIT (BHU), Varanasi)
"""

import os
import sys
import json
import struct
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from hardware.hil_dual_stream_bridge import (
    build_itch_packet,
    HILDualStreamBridge,
    get_hil_bridge
)


class TestHILDualStreamBridge(unittest.TestCase):

    def test_itch_packet_serialization(self):
        """Verifies 42-byte NASDAQ ITCH 5.0 binary Add Order frame construction."""
        pkt = build_itch_packet(order_ref=42, side="B", shares=250, symbol="AAPL    ", price_cents=1850000)
        self.assertEqual(len(pkt), 42, f"Expected 42 bytes, got {len(pkt)}")
        # Check sync header 0x55 0xAA
        self.assertEqual(pkt[:2], bytes([0x55, 0xAA]))
        # Check message type 'A' (0x41)
        self.assertEqual(pkt[2], 0x41)
        # Check symbol AAPL
        self.assertIn(b"AAPL", pkt)

    def test_fpga_telemetry_frame_decoding(self):
        """Validates decoding of 12-byte telemetry packet from Spartan-7 FPGA."""
        bridge = HILDualStreamBridge()
        # Synthetic 12-byte frame:
        # Sync: 0x55 0xBB
        # Flags: 0x8000 (PLL locked, no killswitch)
        # Voltage: 0xFFB5 (-75 mV signed Q16)
        # Cycles: 1230 (0x000004CE)
        # Trailer/Checksum: 0x0000
        frame = bytes([0x55, 0xBB, 0x80, 0x00, 0xFF, 0xB5, 0x00, 0x00, 0x04, 0xCE, 0x00, 0x00])
        bridge._decode_telemetry_frame(frame)

        self.assertEqual(bridge.last_voltage_mv, -75.0)
        self.assertEqual(bridge.last_latency_cycles, 1230)
        self.assertEqual(bridge.last_latency_us, 12.30)
        self.assertEqual(bridge.last_status_flags, 0x8000)
        self.assertFalse(bridge.spike_detected)
        self.assertFalse(bridge.killswitch_tripped)

        # Test frame with Spike flag set (Bit 13: 0x2000 -> Status: 0xA000)
        frame_spike = bytes([0x55, 0xBB, 0xA0, 0x00, 0xFF, 0xC9, 0x00, 0x00, 0x00, 0x2F, 0x00, 0x00])
        bridge._decode_telemetry_frame(frame_spike)
        self.assertTrue(bridge.spike_detected)
        self.assertEqual(bridge.last_latency_cycles, 47)

        # Test frame with Killswitch flag set (Bit 10: 0x0400 -> Status: 0x8400)
        frame_kill = bytes([0x55, 0xBB, 0x84, 0x00, 0xFF, 0xB5, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00])
        bridge._decode_telemetry_frame(frame_kill)
        self.assertTrue(bridge.killswitch_tripped)

    def test_status_dict_contract(self):
        """Audits the HIL status dictionary schema and physical LED states."""
        bridge = HILDualStreamBridge()
        st = bridge.get_status_dict()

        expected_keys = [
            "hil_active", "fpga_connected", "nano_connected", "fpga_port", "nano_port",
            "baud_rate", "total_orders_forwarded", "total_telemetry_received",
            "last_voltage_mv", "last_latency_cycles", "last_latency_us",
            "last_status_flags", "spike_detected", "killswitch_tripped",
            "itch_valid", "throughput_ops", "led_state", "recent_telemetry"
        ]
        for k in expected_keys:
            self.assertIn(k, st, f"Missing key in HIL status: {k}")

        self.assertIn("ld0_rgb", st["led_state"])
        self.assertIn("ld1_rgb", st["led_state"])
        self.assertIn("ld2_yellow", st["led_state"])

    def test_rest_api_hil_endpoints(self):
        """Audits the Flask web server Day 6 HIL REST API routes."""
        from web_app.server import app
        client = app.test_client()

        # 1. GET /api/hardware/hil_status
        res_st = client.get("/api/hardware/hil_status")
        self.assertEqual(res_st.status_code, 200)
        d_st = res_st.get_json()
        self.assertIn("last_voltage_mv", d_st)
        self.assertIn("led_state", d_st)

        # 2. POST /api/hardware/hil_inject (normal order)
        res_inj = client.post(
            "/api/hardware/hil_inject",
            json={"shares": 100, "side": "B", "price": 185.0}
        )
        self.assertEqual(res_inj.status_code, 200)
        d_inj = res_inj.get_json()
        self.assertIn("status", d_inj)
        self.assertEqual(d_inj["shares"], 100)

        # 3. POST /api/hardware/hil_control (reconnect)
        res_ctrl = client.post(
            "/api/hardware/hil_control",
            json={"action": "reconnect"}
        )
        self.assertEqual(res_ctrl.status_code, 200)
        d_ctrl = res_ctrl.get_json()
        self.assertEqual(d_ctrl["status"], "ok")


if __name__ == "__main__":
    unittest.main()
