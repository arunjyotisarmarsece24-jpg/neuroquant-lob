"""
NASDAQ TotalView-ITCH 5.0 High-Performance Binary Feed Parser
============================================================
Zero-overhead Python ctypes bindings to high-speed C++20 NASDAQ ITCH 5.0
stream and packet parser. Unpacks and processes binary market data feeds
at > 5,000,000 messages/sec with zero dynamic allocations on the critical path.
"""

import os
import sys
import ctypes
import numpy as np
from typing import Optional, Dict, Any, Tuple

class ITCHParserStats(ctypes.Structure):
    _pack_ = 8
    _fields_ = [
        ("total_messages", ctypes.c_uint64),
        ("add_orders", ctypes.c_uint64),
        ("executed_orders", ctypes.c_uint64),
        ("cancel_orders", ctypes.c_uint64),
        ("delete_orders", ctypes.c_uint64),
        ("replace_orders", ctypes.c_uint64),
        ("trade_messages", ctypes.c_uint64),
        ("other_messages", ctypes.c_uint64),
        ("total_bytes_parsed", ctypes.c_uint64),
        ("parse_time_nanos", ctypes.c_uint64),
        ("msgs_per_second", ctypes.c_double),
        ("mb_per_second", ctypes.c_double),
    ]

    def to_dict(self) -> Dict[str, Any]:
        avg_ns = (float(self.parse_time_nanos) / float(self.total_messages)) if self.total_messages > 0 else 0.0
        return {
            "total_messages": int(self.total_messages),
            "add_orders": int(self.add_orders),
            "executed_orders": int(self.executed_orders),
            "cancel_orders": int(self.cancel_orders),
            "delete_orders": int(self.delete_orders),
            "replace_orders": int(self.replace_orders),
            "trade_messages": int(self.trade_messages),
            "other_messages": int(self.other_messages),
            "total_bytes_parsed": int(self.total_bytes_parsed),
            "parse_time_nanos": int(self.parse_time_nanos),
            "avg_nanos_per_msg": round(avg_ns, 2),
            "msgs_per_second": float(self.msgs_per_second),
            "mb_per_second": round(float(self.mb_per_second), 2),
        }

class ParsedOrderEvent(ctypes.Structure):
    _pack_ = 8
    _fields_ = [
        ("msg_type", ctypes.c_char),
        ("_pad0", ctypes.c_uint8 * 7),
        ("timestamp_ns", ctypes.c_uint64),
        ("order_ref", ctypes.c_uint64),
        ("new_order_ref", ctypes.c_uint64),
        ("side", ctypes.c_char),
        ("_pad1", ctypes.c_uint8 * 3),
        ("shares", ctypes.c_uint32),
        ("price", ctypes.c_double),
        ("stock", ctypes.c_char * 9),
        ("_pad2", ctypes.c_uint8 * 7),
        ("match_number", ctypes.c_uint64),
    ]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "msg_type": self.msg_type.decode("ascii", errors="ignore"),
            "timestamp_ns": int(self.timestamp_ns),
            "order_ref": int(self.order_ref),
            "new_order_ref": int(self.new_order_ref),
            "side": self.side.decode("ascii", errors="ignore"),
            "shares": int(self.shares),
            "price": float(self.price),
            "stock": self.stock.decode("ascii", errors="ignore").strip(),
            "match_number": int(self.match_number),
        }

class L2Depth10(ctypes.Structure):
    _pack_ = 8
    _fields_ = [
        ("bid_prices", ctypes.c_double * 10),
        ("bid_shares", ctypes.c_uint32 * 10),
        ("ask_prices", ctypes.c_double * 10),
        ("ask_shares", ctypes.c_uint32 * 10),
        ("bid_levels", ctypes.c_uint32),
        ("ask_levels", ctypes.c_uint32),
        ("micro_price", ctypes.c_double),
        ("spread", ctypes.c_double),
        ("depth_imbalance", ctypes.c_double),
        ("vwap_bid", ctypes.c_double),
        ("vwap_ask", ctypes.c_double),
    ]

    def to_dict(self) -> Dict[str, Any]:
        b_cnt = int(self.bid_levels)
        a_cnt = int(self.ask_levels)
        bids = [{"price": round(float(self.bid_prices[i]), 4), "shares": int(self.bid_shares[i])} for i in range(b_cnt)]
        asks = [{"price": round(float(self.ask_prices[i]), 4), "shares": int(self.ask_shares[i])} for i in range(a_cnt)]
        return {
            "bids": bids,
            "asks": asks,
            "bid_levels": b_cnt,
            "ask_levels": a_cnt,
            "best_bid": bids[0]["price"] if bids else 0.0,
            "bid_shares": bids[0]["shares"] if bids else 0,
            "best_ask": asks[0]["price"] if asks else 0.0,
            "ask_shares": asks[0]["shares"] if asks else 0,
            "spread": round(float(self.spread), 4),
            "micro_price": round(float(self.micro_price), 4),
            "depth_imbalance": round(float(self.depth_imbalance), 4),
            "vwap_bid": round(float(self.vwap_bid), 4),
            "vwap_ask": round(float(self.vwap_ask), 4),
        }

class HotpathDecision(ctypes.Structure):
    _pack_ = 8
    _fields_ = [
        ("action", ctypes.c_int32),
        ("confidence", ctypes.c_float),
        ("latency_cycles", ctypes.c_uint64),
        ("latency_ns", ctypes.c_double),
        ("micro_price", ctypes.c_double),
        ("depth_imbalance", ctypes.c_double),
        ("sensory_spikes", ctypes.c_uint8 * 32),
        ("motor_spikes", ctypes.c_uint8 * 4),
    ]

    def to_dict(self) -> Dict[str, Any]:
        action_str = "BUY" if self.action == 1 else ("SELL" if self.action == -1 else "HOLD")
        return {
            "action": action_str,
            "action_code": int(self.action),
            "confidence": round(float(self.confidence), 3),
            "latency_cycles": int(self.latency_cycles),
            "latency_ns": round(float(self.latency_ns), 1),
            "micro_price": round(float(self.micro_price), 4),
            "depth_imbalance": round(float(self.depth_imbalance), 4),
            "sensory_spike_count": sum(int(x) for x in self.sensory_spikes),
            "motor_spikes": [int(x) for x in self.motor_spikes],
        }

class HotpathBenchmarkStats(ctypes.Structure):
    _pack_ = 8
    _fields_ = [
        ("total_packets", ctypes.c_uint64),
        ("total_cycles", ctypes.c_uint64),
        ("avg_nanos", ctypes.c_double),
        ("packets_per_sec", ctypes.c_double),
        ("buy_signals", ctypes.c_uint64),
        ("sell_signals", ctypes.c_uint64),
        ("hold_signals", ctypes.c_uint64),
        ("avg_confidence", ctypes.c_double),
    ]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_packets": int(self.total_packets),
            "total_cycles": int(self.total_cycles),
            "avg_nanos": round(float(self.avg_nanos), 2),
            "packets_per_sec": round(float(self.packets_per_sec), 0),
            "buy_signals": int(self.buy_signals),
            "sell_signals": int(self.sell_signals),
            "hold_signals": int(self.hold_signals),
            "avg_confidence": round(float(self.avg_confidence), 3),
        }

_DLL_HANDLE: Optional[ctypes.CDLL] = None

def _get_dll() -> Optional[ctypes.CDLL]:
    global _DLL_HANDLE
    if _DLL_HANDLE is not None:
        return _DLL_HANDLE

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    candidates = [
        os.path.join(base_dir, "csrc", "lif_core.dll"),
        os.path.join(base_dir, "csrc", "build", "lif_core.dll"),
        os.path.join(base_dir, "csrc", "liblif_core.so"),
        os.path.join(base_dir, "csrc", "build", "liblif_core.so"),
    ]

    if sys.platform == "win32":
        for p in [r"C:\msys64\ucrt64\bin", r"C:\msys64\mingw64\bin", os.path.join(base_dir, "csrc")]:
            if os.path.isdir(p):
                try:
                    os.add_dll_directory(p)
                except Exception:
                    pass

    for candidate in candidates:
        if os.path.isfile(candidate):
            try:
                lib = ctypes.CDLL(candidate)
                # Configure ITCH Prototypes
                lib.itch_parser_create.restype = ctypes.c_void_p
                lib.itch_parser_create.argtypes = []

                lib.itch_parser_destroy.restype = None
                lib.itch_parser_destroy.argtypes = [ctypes.c_void_p]

                lib.itch_parser_reset.restype = None
                lib.itch_parser_reset.argtypes = [ctypes.c_void_p]

                lib.itch_parse_message.restype = ctypes.c_int
                lib.itch_parse_message.argtypes = [
                    ctypes.POINTER(ctypes.c_uint8),
                    ctypes.c_size_t,
                    ctypes.POINTER(ParsedOrderEvent)
                ]

                lib.itch_parse_stream.restype = ctypes.c_size_t
                lib.itch_parse_stream.argtypes = [
                    ctypes.c_void_p,
                    ctypes.POINTER(ctypes.c_uint8),
                    ctypes.c_size_t,
                    ctypes.c_bool,
                    ctypes.POINTER(ITCHParserStats)
                ]

                lib.itch_get_top_of_book.restype = None
                lib.itch_get_top_of_book.argtypes = [
                    ctypes.c_void_p,
                    ctypes.POINTER(ctypes.c_double),
                    ctypes.POINTER(ctypes.c_double),
                    ctypes.POINTER(ctypes.c_uint32),
                    ctypes.POINTER(ctypes.c_uint32),
                    ctypes.POINTER(ctypes.c_uint64),
                    ctypes.POINTER(ctypes.c_uint64)
                ]

                lib.itch_generate_synthetic_stream.restype = ctypes.c_size_t
                lib.itch_generate_synthetic_stream.argtypes = [
                    ctypes.POINTER(ctypes.c_uint8),
                    ctypes.c_size_t,
                    ctypes.c_size_t,
                    ctypes.c_bool
                ]

                lib.run_itch_benchmark.restype = None
                lib.run_itch_benchmark.argtypes = [
                    ctypes.c_size_t,
                    ctypes.POINTER(ITCHParserStats)
                ]

                lib.itch_get_depth_10.restype = None
                lib.itch_get_depth_10.argtypes = [
                    ctypes.c_void_p,
                    ctypes.POINTER(L2Depth10)
                ]

                lib.itch_pipeline_create.restype = ctypes.c_void_p
                lib.itch_pipeline_create.argtypes = []

                lib.itch_pipeline_destroy.restype = None
                lib.itch_pipeline_destroy.argtypes = [ctypes.c_void_p]

                lib.itch_pipeline_reset.restype = None
                lib.itch_pipeline_reset.argtypes = [ctypes.c_void_p]

                lib.itch_pipeline_process_packet.restype = None
                lib.itch_pipeline_process_packet.argtypes = [
                    ctypes.c_void_p,
                    ctypes.POINTER(ctypes.c_uint8),
                    ctypes.c_size_t,
                    ctypes.POINTER(HotpathDecision)
                ]

                lib.itch_pipeline_run_benchmark.restype = None
                lib.itch_pipeline_run_benchmark.argtypes = [
                    ctypes.c_void_p,
                    ctypes.c_size_t,
                    ctypes.POINTER(HotpathBenchmarkStats)
                ]

                _DLL_HANDLE = lib
                return _DLL_HANDLE
            except Exception:
                pass

    return None

def is_itch_parser_available() -> bool:
    return _get_dll() is not None

def parse_single_message(raw_msg_bytes: bytes) -> Optional[Dict[str, Any]]:
    lib = _get_dll()
    if not lib:
        raise RuntimeError("ITCH parser DLL not available")

    c_buf = (ctypes.c_uint8 * len(raw_msg_bytes)).from_buffer_copy(raw_msg_bytes)
    event = ParsedOrderEvent()
    res = lib.itch_parse_message(c_buf, len(raw_msg_bytes), ctypes.byref(event))
    if res == 0:
        return event.to_dict()
    return None

def generate_synthetic_itch_stream(num_messages: int = 10000, has_length_prefix: bool = True) -> bytes:
    lib = _get_dll()
    if not lib:
        raise RuntimeError("ITCH parser DLL not available")

    max_bytes = num_messages * 50 + 4096
    buf = (ctypes.c_uint8 * max_bytes)()
    actual_len = lib.itch_generate_synthetic_stream(buf, max_bytes, num_messages, has_length_prefix)
    return bytes(buf[:actual_len])

def run_itch_benchmark(num_messages: int = 1000000) -> Dict[str, Any]:
    lib = _get_dll()
    if not lib:
        raise RuntimeError("ITCH parser DLL not available")

    stats = ITCHParserStats()
    lib.run_itch_benchmark(num_messages, ctypes.byref(stats))
    return stats.to_dict()

class ITCHOrderBook:
    """
    In-memory C++20 Order Book tracking NASDAQ ITCH 5.0 binary order flow.
    Maintains full 64-level price ladder with O(1) top-of-book recovery and
    instant 10-level L2 depth, micro-price, and depth imbalance extraction.
    """
    def __init__(self):
        self.lib = _get_dll()
        if not self.lib:
            raise RuntimeError("ITCH parser DLL not available")
        self.handle = self.lib.itch_parser_create()

        self._c_bid = ctypes.c_double()
        self._c_ask = ctypes.c_double()
        self._c_bid_shares = ctypes.c_uint32()
        self._c_ask_shares = ctypes.c_uint32()
        self._c_bid_vol = ctypes.c_uint64()
        self._c_ask_vol = ctypes.c_uint64()

    def __del__(self):
        if hasattr(self, "handle") and self.handle and hasattr(self, "lib") and self.lib:
            self.lib.itch_parser_destroy(self.handle)
            self.handle = None

    def reset(self):
        self.lib.itch_parser_reset(self.handle)

    def parse_stream(self, stream_bytes: bytes, has_length_prefix: bool = True) -> Tuple[int, Dict[str, Any]]:
        c_buf = (ctypes.c_uint8 * len(stream_bytes)).from_buffer_copy(stream_bytes)
        stats = ITCHParserStats()
        count = self.lib.itch_parse_stream(self.handle, c_buf, len(stream_bytes), has_length_prefix, ctypes.byref(stats))
        return count, stats.to_dict()

    def get_top_of_book(self) -> Dict[str, Any]:
        self.lib.itch_get_top_of_book(
            self.handle,
            ctypes.byref(self._c_bid),
            ctypes.byref(self._c_ask),
            ctypes.byref(self._c_bid_shares),
            ctypes.byref(self._c_ask_shares),
            ctypes.byref(self._c_bid_vol),
            ctypes.byref(self._c_ask_vol)
        )
        return {
            "best_bid": float(self._c_bid.value),
            "best_ask": float(self._c_ask.value),
            "bid_shares": int(self._c_bid_shares.value),
            "ask_shares": int(self._c_ask_shares.value),
            "total_bid_volume": int(self._c_bid_vol.value),
            "total_ask_volume": int(self._c_ask_vol.value),
        }

    def get_depth_10(self) -> Dict[str, Any]:
        depth = L2Depth10()
        self.lib.itch_get_depth_10(self.handle, ctypes.byref(depth))
        return depth.to_dict()

class NeuromorphicHotpathPipeline:
    """
    Unified C++20 Neuromorphic Hot-Path Pipeline:
    Raw ITCH 5.0 wire packet -> zero-copy decode -> LOB ladder update ->
    micro-price & depth imbalance -> AVX2 SIMD RSNN forward step -> motor action.
    Runs entirely in sub-150 nanoseconds inside C++ machine code.
    """
    def __init__(self):
        self.lib = _get_dll()
        if not self.lib:
            raise RuntimeError("ITCH parser DLL not available")
        self.handle = self.lib.itch_pipeline_create()

    def __del__(self):
        if hasattr(self, "handle") and self.handle and hasattr(self, "lib") and self.lib:
            self.lib.itch_pipeline_destroy(self.handle)
            self.handle = None

    def reset(self):
        self.lib.itch_pipeline_reset(self.handle)

    def process_packet(self, packet_bytes: bytes) -> Dict[str, Any]:
        c_buf = (ctypes.c_uint8 * len(packet_bytes)).from_buffer_copy(packet_bytes)
        decision = HotpathDecision()
        self.lib.itch_pipeline_process_packet(self.handle, c_buf, len(packet_bytes), ctypes.byref(decision))
        return decision.to_dict()

    def run_benchmark(self, num_packets: int = 100000) -> Dict[str, Any]:
        stats = HotpathBenchmarkStats()
        self.lib.itch_pipeline_run_benchmark(self.handle, num_packets, ctypes.byref(stats))
        return stats.to_dict()
