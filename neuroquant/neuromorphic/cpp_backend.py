"""
C++20 AVX2 Vectorized Neuromorphic Backend Interface
=====================================================
Zero-overhead Python ctypes bindings to high-performance C++20 AVX2/AVX-512
shared library (csrc/lif_core.dll / liblif_core.so).
Enables single-digit microsecond / sub-microsecond execution of Leaky
Integrate-and-Fire neurons and RSNN recurrent reservoir dynamics.
"""

import os
import sys
import ctypes
import numpy as np
from typing import Optional, Tuple, Dict, Any
from config import NeuromorphicConfig

class BenchmarkStats(ctypes.Structure):
    _pack_ = 8
    _fields_ = [
        ("total_steps", ctypes.c_uint64),
        ("total_cycles", ctypes.c_uint64),
        ("min_cycles", ctypes.c_uint64),
        ("max_cycles", ctypes.c_uint64),
        ("p50_cycles", ctypes.c_double),
        ("p90_cycles", ctypes.c_double),
        ("p99_cycles", ctypes.c_double),
        ("p999_cycles", ctypes.c_double),
        ("avg_nanoseconds", ctypes.c_double),
        ("steps_per_second", ctypes.c_double),
    ]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_steps": int(self.total_steps),
            "total_cycles": int(self.total_cycles),
            "min_cycles": int(self.min_cycles),
            "max_cycles": int(self.max_cycles),
            "p50_cycles": float(self.p50_cycles),
            "p90_cycles": float(self.p90_cycles),
            "p99_cycles": float(self.p99_cycles),
            "p999_cycles": float(self.p999_cycles),
            "avg_nanoseconds": float(self.avg_nanoseconds),
            "steps_per_second": float(self.steps_per_second),
        }

_DLL_HANDLE: Optional[ctypes.CDLL] = None
_DLL_LOAD_ERROR: Optional[str] = None

def _find_and_load_dll() -> Optional[ctypes.CDLL]:
    global _DLL_HANDLE, _DLL_LOAD_ERROR
    if _DLL_HANDLE is not None:
        return _DLL_HANDLE

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    candidates = [
        os.path.join(base_dir, "csrc", "lif_core.dll"),
        os.path.join(base_dir, "csrc", "build", "lif_core.dll"),
        os.path.join(base_dir, "csrc", "liblif_core.so"),
        os.path.join(base_dir, "csrc", "lif_core.so"),
        os.path.join(base_dir, "csrc", "build", "liblif_core.so"),
        os.path.join(base_dir, "csrc", "build", "lif_core.so"),
        os.path.join(base_dir, "csrc", "liblif_core.dylib"),
        os.path.join(base_dir, "csrc", "lif_core.dylib"),
    ]

    # Windows PATH / DLL directory registration
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
                # Configure function prototypes
                lib.get_hardware_cycles.restype = ctypes.c_uint64
                lib.get_hardware_cycles.argtypes = []

                # LIF API
                lib.lif_create.restype = ctypes.c_void_p
                lib.lif_create.argtypes = [
                    ctypes.c_size_t,
                    ctypes.c_float, ctypes.c_float,
                    ctypes.c_float, ctypes.c_float,
                    ctypes.c_float, ctypes.c_float
                ]

                lib.lif_reset.restype = None
                lib.lif_reset.argtypes = [ctypes.c_void_p]

                lib.lif_destroy.restype = None
                lib.lif_destroy.argtypes = [ctypes.c_void_p]

                lib.lif_step.restype = None
                lib.lif_step.argtypes = [
                    ctypes.c_void_p,
                    ctypes.POINTER(ctypes.c_float),
                    ctypes.POINTER(ctypes.c_uint8)
                ]

                lib.lif_get_state.restype = None
                lib.lif_get_state.argtypes = [
                    ctypes.c_void_p,
                    ctypes.POINTER(ctypes.c_float),
                    ctypes.POINTER(ctypes.c_int32),
                    ctypes.POINTER(ctypes.c_uint64)
                ]

                lib.lif_set_state.restype = None
                lib.lif_set_state.argtypes = [
                    ctypes.c_void_p,
                    ctypes.POINTER(ctypes.c_float),
                    ctypes.POINTER(ctypes.c_float),
                    ctypes.POINTER(ctypes.c_int32)
                ]

                # RSNN API
                lib.rsnn_create.restype = ctypes.c_void_p
                lib.rsnn_create.argtypes = [
                    ctypes.c_size_t, ctypes.c_size_t, ctypes.c_size_t,
                    ctypes.c_float, ctypes.c_float,
                    ctypes.c_float, ctypes.c_float,
                    ctypes.c_float, ctypes.c_float
                ]

                lib.rsnn_destroy.restype = None
                lib.rsnn_destroy.argtypes = [ctypes.c_void_p]

                lib.rsnn_reset.restype = None
                lib.rsnn_reset.argtypes = [ctypes.c_void_p]

                lib.rsnn_set_weights.restype = None
                lib.rsnn_set_weights.argtypes = [
                    ctypes.c_void_p,
                    ctypes.POINTER(ctypes.c_float),
                    ctypes.POINTER(ctypes.c_float),
                    ctypes.POINTER(ctypes.c_float)
                ]

                lib.rsnn_step.restype = None
                lib.rsnn_step.argtypes = [
                    ctypes.c_void_p,
                    ctypes.POINTER(ctypes.c_uint8),
                    ctypes.POINTER(ctypes.c_uint8),
                    ctypes.POINTER(ctypes.c_uint8),
                    ctypes.POINTER(ctypes.c_uint8)
                ]

                lib.rsnn_get_motor_voltage.restype = None
                lib.rsnn_get_motor_voltage.argtypes = [
                    ctypes.c_void_p,
                    ctypes.POINTER(ctypes.c_float)
                ]

                # Benchmark API
                lib.run_lif_benchmark.restype = None
                lib.run_lif_benchmark.argtypes = [
                    ctypes.c_size_t, ctypes.c_size_t,
                    ctypes.POINTER(BenchmarkStats)
                ]

                lib.run_rsnn_benchmark.restype = None
                lib.run_rsnn_benchmark.argtypes = [
                    ctypes.c_size_t,
                    ctypes.POINTER(BenchmarkStats)
                ]

                _DLL_HANDLE = lib
                return _DLL_HANDLE
            except Exception as e:
                _DLL_LOAD_ERROR = str(e)

    return None

def is_cpp_backend_available() -> bool:
    return _find_and_load_dll() is not None

def get_hardware_cycles() -> int:
    lib = _find_and_load_dll()
    if lib:
        return int(lib.get_hardware_cycles())
    return 0

def run_cpp_lif_benchmark(num_neurons: int = 64, iterations: int = 100000) -> Dict[str, Any]:
    lib = _find_and_load_dll()
    if not lib:
        raise RuntimeError(f"C++ backend not available: {_DLL_LOAD_ERROR}")
    stats = BenchmarkStats()
    lib.run_lif_benchmark(num_neurons, iterations, ctypes.byref(stats))
    return stats.to_dict()

def run_cpp_rsnn_benchmark(iterations: int = 100000) -> Dict[str, Any]:
    lib = _find_and_load_dll()
    if not lib:
        raise RuntimeError(f"C++ backend not available: {_DLL_LOAD_ERROR}")
    stats = BenchmarkStats()
    lib.run_rsnn_benchmark(iterations, ctypes.byref(stats))
    return stats.to_dict()


class CPULIFPopulation:
    """
    Python wrapper managing a high-performance C++20 AVX2 LIF Population instance.
    """
    def __init__(self, size: int, config: NeuromorphicConfig, name: str = "LIF_CPP"):
        self.size = size
        self.cfg = config
        self.name = name
        self.lib = _find_and_load_dll()
        if not self.lib:
            raise RuntimeError(f"Failed to load C++ lif_core library: {_DLL_LOAD_ERROR}")

        self.handle = self.lib.lif_create(
            size,
            config.time_step_ms,
            config.tau_m,
            config.v_rest,
            config.v_reset,
            config.v_thresh,
            config.refractory_period_ms
        )

        self.spikes = np.zeros(self.size, dtype=np.bool_)
        self.voltage = np.full(self.size, config.v_rest, dtype=np.float32)
        self.refractory_timer = np.zeros(self.size, dtype=np.int32)
        self.spike_counts = np.zeros(self.size, dtype=np.uint64)
        self.total_steps = 0
        self.recent_voltage_history = []
        self.history_capacity = 200

        # Preallocated buffers for zero-copy ctypes calls
        self._c_out_spikes = (ctypes.c_uint8 * self.size)()
        self._c_voltage = (ctypes.c_float * self.size)()
        self._c_refr = (ctypes.c_int32 * self.size)()
        self._c_counts = (ctypes.c_uint64 * self.size)()

    def __del__(self):
        if hasattr(self, "handle") and self.handle and hasattr(self, "lib") and self.lib:
            self.lib.lif_destroy(self.handle)
            self.handle = None

    def reset(self):
        self.lib.lif_reset(self.handle)
        self.spikes.fill(False)
        self.voltage.fill(self.cfg.v_rest)
        self.refractory_timer.fill(0)
        self.spike_counts.fill(0)
        self.total_steps = 0
        self.recent_voltage_history.clear()

    def step(self, synaptic_current: np.ndarray) -> np.ndarray:
        if not synaptic_current.flags['C_CONTIGUOUS']:
            synaptic_current = np.ascontiguousarray(synaptic_current, dtype=np.float32)
        elif synaptic_current.dtype != np.float32:
            synaptic_current = synaptic_current.astype(np.float32)

        cur_ptr = synaptic_current.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
        self.lib.lif_step(self.handle, cur_ptr, self._c_out_spikes)

        # Update local numpy mirrors
        self.spikes = np.ctypeslib.as_array(self._c_out_spikes).astype(np.bool_)
        self.total_steps += 1
        return self.spikes

    def sync_state_from_cpp(self):
        self.lib.lif_get_state(self.handle, self._c_voltage, self._c_refr, self._c_counts)
        self.voltage = np.ctypeslib.as_array(self._c_voltage).copy()
        self.refractory_timer = np.ctypeslib.as_array(self._c_refr).copy()
        self.spike_counts = np.ctypeslib.as_array(self._c_counts).copy()

    def set_state(self, voltage: Optional[np.ndarray] = None, threshold: Optional[np.ndarray] = None, refractory_timer: Optional[np.ndarray] = None):
        p_v = None
        p_t = None
        p_r = None
        if voltage is not None:
            v_c = np.ascontiguousarray(voltage, dtype=np.float32)
            p_v = v_c.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
            self.voltage = v_c.copy()
        if threshold is not None:
            t_c = np.ascontiguousarray(threshold, dtype=np.float32)
            p_t = t_c.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
            self.threshold = t_c.copy()
        if refractory_timer is not None:
            r_c = np.ascontiguousarray(refractory_timer, dtype=np.int32)
            p_r = r_c.ctypes.data_as(ctypes.POINTER(ctypes.c_int32))
            self.refractory_timer = r_c.copy()
        self.lib.lif_set_state(self.handle, p_v, p_t, p_r)


class CPURSNNCore:
    """
    Python wrapper managing a high-performance C++20 AVX2 RSNN Core instance.
    Runs sensory -> hidden reservoir -> motor readout completely in C++ registers.
    """
    def __init__(self, config: NeuromorphicConfig):
        self.cfg = config
        self.num_sensory = config.num_sensory_neurons
        self.num_hidden = config.num_hidden_neurons
        self.num_motor = config.num_motor_neurons
        self.lib = _find_and_load_dll()
        if not self.lib:
            raise RuntimeError(f"Failed to load C++ lif_core library: {_DLL_LOAD_ERROR}")

        self.handle = self.lib.rsnn_create(
            self.num_sensory,
            self.num_hidden,
            self.num_motor,
            config.time_step_ms,
            config.tau_m,
            config.v_rest,
            config.v_reset,
            config.v_thresh,
            config.refractory_period_ms
        )

        # Buffers
        self._c_s_in = (ctypes.c_uint8 * self.num_sensory)()
        self._c_s_out = (ctypes.c_uint8 * self.num_sensory)()
        self._c_h_out = (ctypes.c_uint8 * self.num_hidden)()
        self._c_m_out = (ctypes.c_uint8 * self.num_motor)()
        self._c_v_motor = (ctypes.c_float * self.num_motor)()

        self.sensory_spikes = np.zeros(self.num_sensory, dtype=np.bool_)
        self.hidden_spikes = np.zeros(self.num_hidden, dtype=np.bool_)
        self.motor_spikes = np.zeros(self.num_motor, dtype=np.bool_)
        self.motor_voltage = np.zeros(self.num_motor, dtype=np.float32)
        self.step_count = 0

    def __del__(self):
        if hasattr(self, "handle") and self.handle and hasattr(self, "lib") and self.lib:
            self.lib.rsnn_destroy(self.handle)
            self.handle = None

    def set_weights(self, w_in: np.ndarray, w_rec: np.ndarray, w_motor: np.ndarray):
        w_in_c = np.ascontiguousarray(w_in, dtype=np.float32)
        w_rec_c = np.ascontiguousarray(w_rec, dtype=np.float32)
        w_motor_c = np.ascontiguousarray(w_motor, dtype=np.float32)

        p_in = w_in_c.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
        p_rec = w_rec_c.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
        p_motor = w_motor_c.ctypes.data_as(ctypes.POINTER(ctypes.c_float))

        self.lib.rsnn_set_weights(self.handle, p_in, p_rec, p_motor)

    def reset(self):
        self.lib.rsnn_reset(self.handle)
        self.sensory_spikes.fill(False)
        self.hidden_spikes.fill(False)
        self.motor_spikes.fill(False)
        self.step_count = 0

    def step(self, sensory_spikes_in: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        if sensory_spikes_in.dtype == np.bool_:
            s_in = sensory_spikes_in.astype(np.uint8)
        else:
            s_in = np.ascontiguousarray(sensory_spikes_in, dtype=np.uint8)

        # Copy into C buffer
        ctypes.memmove(self._c_s_in, s_in.ctypes.data, self.num_sensory)
        self.lib.rsnn_step(self.handle, self._c_s_in, self._c_s_out, self._c_h_out, self._c_m_out)

        self.sensory_spikes = np.ctypeslib.as_array(self._c_s_out).astype(np.bool_)
        self.hidden_spikes = np.ctypeslib.as_array(self._c_h_out).astype(np.bool_)
        self.motor_spikes = np.ctypeslib.as_array(self._c_m_out).astype(np.bool_)
        self.step_count += 1
        return self.sensory_spikes, self.hidden_spikes, self.motor_spikes

    def get_motor_readout_signals(self) -> Dict[str, float]:
        self.lib.rsnn_get_motor_voltage(self.handle, self._c_v_motor)
        self.motor_voltage = np.ctypeslib.as_array(self._c_v_motor).copy()

        # Motor Channel Mapping:
        # 0: Upward Skew, 1: Downward Skew, 2: Toxicity Alert, 3: Volatility Burst
        # Normalized membrane activation above resting potential in [0.0, 1.0]
        v_diff = self.cfg.v_thresh - self.cfg.v_rest
        activation = np.clip((self.motor_voltage - self.cfg.v_rest) / (v_diff + 1e-5), 0.0, 1.0)
        
        # Action potential spike pulse (adds immediate discrete boost on firing ticks)
        spike_pulse = self.motor_spikes.astype(np.float32) * 0.75
        effective_signal = np.clip(activation + spike_pulse, 0.0, 2.0)

        # [0]: Upward Skew, [1]: Downward Skew
        net_skew = float(effective_signal[0] - effective_signal[1])
        # [2]: Toxicity Probability in [0.0, 1.0]
        toxicity_prob = float(np.clip(effective_signal[2] * 0.65, 0.0, 1.0))
        # [3]: Volatility Multiplier >= 1.0
        volatility_boost = 1.0 + float(effective_signal[3] * 0.5)

        return {
            "skew": float(net_skew),
            "toxicity_prob": float(toxicity_prob),
            "volatility_multiplier": float(volatility_boost),
            "motor_spikes": self.motor_spikes.copy(),
            "motor_voltages": self.motor_voltage.copy(),
        }
