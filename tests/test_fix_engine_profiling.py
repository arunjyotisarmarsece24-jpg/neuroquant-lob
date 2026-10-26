"""
Unit Tests for Day 5 FIX 4.4 Engine Microsecond Latency Profiling (Sub-10 µs SLA)
=================================================================================
Validates:
  1. Compiled C++20 AVX2 SIMD Core execution speed and DLL binding integrity.
  2. Sub-10.0 microsecond P99 institutional SLA compliance.
  3. Bit-for-bit checksum parity between SIMD vector operations and Python reference.
  4. Synthesizable Verilog parameters in hardware/optimal_fix_params.vh.
  5. Publication audit JSON schema and performance thresholds.
  6. Flask REST API endpoints (/api/fix/status, /api/fix/chart, /api/fix/inject).

Author: Arunjyoti Sarma (Research Scholar, IIT (BHU), Varanasi)
"""

import os
import sys
import json
import ctypes
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from neuroquant.execution.fix.protocol import (
    FixMessage,
    FixMsgType,
    FixSide,
    FixOrdType,
    FixTag,
    FixProtocolEngine
)


class FIXLatencyBenchmarkResult(ctypes.Structure):
    _fields_ = [
        ("min_ns", ctypes.c_double),
        ("p50_ns", ctypes.c_double),
        ("p90_ns", ctypes.c_double),
        ("p99_ns", ctypes.c_double),
        ("p999_ns", ctypes.c_double),
        ("max_ns", ctypes.c_double),
        ("mean_ns", ctypes.c_double),
        ("std_ns", ctypes.c_double),
        ("throughput_orders_per_sec", ctypes.c_double),
        ("total_orders_processed", ctypes.c_int64)
    ]


class FIXParsedOrder(ctypes.Structure):
    _fields_ = [
        ("msg_type", ctypes.c_char),
        ("cl_ord_id", ctypes.c_char * 32),
        ("symbol", ctypes.c_char * 16),
        ("side", ctypes.c_int32),
        ("order_qty", ctypes.c_int64),
        ("price", ctypes.c_double),
        ("checksum", ctypes.c_int32),
        ("is_valid", ctypes.c_int32),
        ("parse_cycles", ctypes.c_uint64),
        ("parse_nanoseconds", ctypes.c_double)
    ]


class TestFixEngineProfiling(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        dll_path = os.path.join(PROJECT_ROOT, "csrc", "lif_core.dll")
        cls.has_dll = os.path.exists(dll_path)
        if cls.has_dll:
            try:
                cls.core = ctypes.CDLL(dll_path)
            except Exception:
                cls.has_dll = False

    def test_simd_dll_c_api_exports(self):
        """Verifies that lif_core.dll exports zero-allocation AVX2 SIMD FIX routines."""
        self.assertTrue(self.has_dll, "csrc/lif_core.dll must exist and load successfully")
        self.assertTrue(hasattr(self.core, "fix_simd_benchmark_loopback"), "Missing fix_simd_benchmark_loopback")
        self.assertTrue(hasattr(self.core, "fix_simd_compute_checksum"), "Missing fix_simd_compute_checksum")
        self.assertTrue(hasattr(self.core, "fix_simd_parse_order"), "Missing fix_simd_parse_order")
        self.assertTrue(hasattr(self.core, "fix_simd_format_execution_report"), "Missing fix_simd_format_execution_report")

    def test_simd_checksum_parity_with_python(self):
        """Validates that AVX2 SIMD checksum matches pure Python FIX 4.4 modulo-256."""
        if not self.has_dll:
            self.skipTest("lif_core.dll not loaded")

        self.core.fix_simd_compute_checksum.argtypes = [ctypes.c_char_p, ctypes.c_size_t]
        self.core.fix_simd_compute_checksum.restype = ctypes.c_uint32

        test_payloads = [
            b"8=FIX.4.4\x019=58\x0135=0\x0149=NEUROQUANT\x0156=CITADEL_CONNECT\x0134=1\x0152=20261026-12:00:00.000\x01",
            b"8=FIX.4.4\x019=120\x0135=D\x0149=NEUROQUANT\x0156=CITADEL_CONNECT\x0134=42\x0111=ORD_0001\x0155=NVDA\x0154=1\x0138=100.0\x0144=135.50\x0140=2\x0159=0\x01",
            b"8=FIX.4.4\x019=10\x0135=3\x0145=1\x01",
            b"A" * 64,
            b"Short",
            b""
        ]

        for payload in test_payloads:
            expected_py = sum(payload) % 256
            simd_res = self.core.fix_simd_compute_checksum(payload, len(payload))
            self.assertEqual(
                simd_res,
                expected_py,
                f"Checksum mismatch for payload {payload!r}: SIMD={simd_res} vs Python={expected_py}"
            )

    def test_cpp_simd_sub_10us_sla(self):
        """Verifies compiled C++20 AVX2 SIMD round-trip latency meets sub-10.0 µs SLA."""
        if not self.has_dll:
            self.skipTest("lif_core.dll not loaded")

        self.core.fix_simd_benchmark_loopback.argtypes = [
            ctypes.c_int,
            ctypes.POINTER(FIXLatencyBenchmarkResult)
        ]
        self.core.fix_simd_benchmark_loopback.restype = ctypes.c_int

        stats = FIXLatencyBenchmarkResult()
        res = self.core.fix_simd_benchmark_loopback(5000, ctypes.byref(stats))
        self.assertEqual(res, 0, "fix_simd_benchmark_loopback returned non-zero error")

        p50_us = stats.p50_ns / 1000.0
        p99_us = stats.p99_ns / 1000.0

        # Rigorous institutional assertions
        self.assertLess(p50_us, 5.0, f"P50 latency {p50_us:.3f} us exceeds 5.0 us")
        self.assertLess(p99_us, 10.0, f"P99 latency {p99_us:.3f} us violates Sub-10 us SLA!")
        self.assertGreater(stats.throughput_orders_per_sec, 100000.0, "Throughput must exceed 100,000 orders/sec")

    def test_optimal_fix_params_vh_integrity(self):
        """Validates synthesizable Verilog constants in hardware/optimal_fix_params.vh."""
        vh_path = os.path.join(PROJECT_ROOT, "hardware", "optimal_fix_params.vh")
        self.assertTrue(os.path.exists(vh_path), "hardware/optimal_fix_params.vh must exist")

        with open(vh_path, "r", encoding="utf-8") as f:
            content = f.read()

        required_macros = [
            "FIX_DELIM_SOH",
            "FIX_DELIM_EQUALS",
            "FIX_MSG_NEW_ORDER",
            "FIX_MSG_EXEC_REPORT",
            "FIX_TAG_MSG_TYPE",
            "FIX_TAG_CL_ORD_ID",
            "FIX_TAG_SYMBOL",
            "FIX_TAG_SIDE",
            "FIX_TAG_ORDER_QTY",
            "FIX_TAG_PRICE",
            "FIX_TAG_CHECKSUM",
            "MAX_LOOPBACK_CYCLES",
            "TARGET_P50_CYCLES"
        ]
        for macro in required_macros:
            self.assertIn(f"`define {macro}", content, f"Missing Verilog macro: {macro}")

    def test_fix_benchmark_results_json(self):
        """Audits the generated Day 5 benchmark JSON against institutional requirements."""
        json_path = os.path.join(PROJECT_ROOT, "benchmarks", "fix_latency_benchmark_results.json")
        self.assertTrue(os.path.exists(json_path), "fix_latency_benchmark_results.json must exist")

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertTrue(data.get("sla_compliance_p99"), "P99 SLA compliance must be certified True")
        self.assertEqual(data.get("sla_threshold_us"), 10.0)
        self.assertIn("simd_metrics", data)
        self.assertIn("component_breakdown_us", data)
        self.assertIn("summary", data)

        simd = data["simd_metrics"]
        self.assertLess(simd["p99_us"], 10.0, f"Recorded P99 {simd['p99_us']} us violates 10 us SLA")
        self.assertGreater(simd["throughput_ops"], 500000.0, "SIMD throughput must be institutional scale")

    def test_web_app_fix_rest_api_endpoints(self):
        """Audits the Flask web server Day 5 REST API routes."""
        from web_app.server import app
        client = app.test_client()

        # 1. GET /api/fix/status
        res_status = client.get("/api/fix/status")
        self.assertEqual(res_status.status_code, 200)
        json_data = res_status.get_json()
        self.assertTrue(json_data.get("sla_compliance_p99"))

        # 2. GET /api/fix/chart
        res_chart = client.get("/api/fix/chart")
        self.assertEqual(res_chart.status_code, 200)
        self.assertEqual(res_chart.mimetype, "image/png")
        res_chart.close()

        # 3. POST /api/fix/inject (approved trade)
        res_inject_ok = client.post(
            "/api/fix/inject",
            json={"symbol": "NVDA", "order_qty": 200.0, "price": 140.0, "side": "BUY"}
        )
        self.assertEqual(res_inject_ok.status_code, 200)
        d_ok = res_inject_ok.get_json()
        self.assertEqual(d_ok.get("status"), "APPROVED")
        self.assertTrue(d_ok.get("wire_bytes_len") > 50)
        self.assertIn("35=8", d_ok.get("exec_report_wire", ""))

        # 4. POST /api/fix/inject (risk rejected trade: qty > 1000)
        res_inject_rej = client.post(
            "/api/fix/inject",
            json={"symbol": "NVDA", "order_qty": 5000.0, "price": 140.0, "side": "BUY"}
        )
        self.assertEqual(res_inject_rej.status_code, 200)
        d_rej = res_inject_rej.get_json()
        self.assertEqual(d_rej.get("status"), "REJECTED_RISK")


if __name__ == "__main__":
    unittest.main()
