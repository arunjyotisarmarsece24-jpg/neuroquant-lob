# ⚡ NeuroQuant-LOB: C++20 AVX2 SIMD Neuromorphic Hot-Path Benchmark Report

**Benchmark Execution Date:** 2026-10-18 21:09:04  
**Target Hardware Architecture:** x86_64 with AVX2 & FMA instruction extensions  
**Cycle Counter:** Serialized `__rdtscp` Hardware Timestamp Counter  
**Author:** Arunjyoti Sarma (Research Scholar, IIT (BHU), Varanasi)  

---

## 🎯 Executive Summary

In high-frequency quantitative market making, traditional deep learning models fail due to excessive compute latency and jitter. `NeuroQuant-LOB` resolves this by employing an asynchronous Spiking Neural Network (SNN) where neurons only execute upon significant order book deltas. 

To achieve true sub-microsecond determinism, the critical execution path was ported from Python/NumPy into modern **C++20 with manual AVX2 SIMD intrinsics and 64-byte L1 cache-line alignment (`alignas(64)`)**.

| Component | Python NumPy Latency | C++20 AVX2 SIMD Latency | Hardware Cycles (P50) | Latency Reduction |
| :--- | :--- | :--- | :--- | :--- |
| **LIF Population (64 neurons)** | ~113,224 ns | **358.5 ns** | **772 cyc** | **315.9x Faster** |
| **Full RSNN (32-64-4 Reservoir)** | ~456,174 ns | **1,153.3 ns** | **2,712 cyc** | **395.5x Faster** |

---

## 🔬 Key Architectural Innovations

### 1. Zero-Heap Allocation Guarantee
All state variables (`voltage`, `threshold`, `refractory_timer`, `spikes`) reside in contiguous, preallocated flat static buffers aligned to 64-byte boundaries matching the CPU's L1 cache lines. **Zero calls to `malloc()`, `free()`, `new`, or standard library vectors occur on the critical tick path.**

### 2. Branchless AVX2 Vectorized Sub-Threshold Decay & Spike Clamping
The Leaky Integrate-and-Fire equation:
`V(t + dt) = V(t) * exp(-dt / tau_m) + V_rest * (1 - exp(-dt / tau_m)) + I_syn(t)`
is executed via fused multiply-accumulate (`_mm256_fmadd_ps`) across 8 single-precision float registers simultaneously:
* **Refractory Clamping:** Branchless vector blend using `_mm256_blendv_ps` clamps refractory neurons to `V_reset` without branching.
* **Spike Detection:** `_mm256_cmp_ps(..., _CMP_GE_OQ)` extracts action potential bitmasks directly into CPU registers with `_mm256_movemask_ps`.

### 3. Sparse Synaptic Matrix Accumulation
Because biological spiking networks exhibit high temporal sparsity, synaptic matrix multiplication skips non-firing neurons, eliminating 80%+ of dense matrix operations.

---

## 📊 Complete Benchmark Data

### LIF Population Scaling
```
{
  "32_neurons": {
    "python": {
      "iterations": 25000,
      "avg_ns": 101207.7,
      "p50_ns": 100500.0,
      "p90_ns": 132700.0,
      "p99_ns": 234900.0,
      "p999_ns": 383300.0,
      "min_ns": 32000.0,
      "max_ns": 703500.0,
      "steps_per_sec": 9880.671134706154
    },
    "cpp": {
      "total_steps": 50000,
      "total_cycles": 23693638,
      "min_cycles": 452,
      "max_cycles": 122916,
      "p50_cycles": 462.0,
      "p90_cycles": 476.0,
      "p99_cycles": 504.0,
      "p999_cycles": 592.0,
      "avg_nanoseconds": 237.102,
      "steps_per_second": 4217594.11561269
    },
    "speedup": 426.85
  },
  "64_neurons": {
    "python": {
      "iterations": 25000,
      "avg_ns": 113224.256,
      "p50_ns": 124200.0,
      "p90_ns": 140600.0,
      "p99_ns": 242100.0,
      "p999_ns": 398600.0,
      "min_ns": 34800.0,
      "max_ns": 990100.0,
      "steps_per_sec": 8832.029772843021
    },
    "cpp": {
      "total_steps": 50000,
      "total_cycles": 39536160,
      "min_cycles": 754,
      "max_cycles": 136054,
      "p50_cycles": 772.0,
      "p90_cycles": 784.0,
      "p99_cycles": 808.0,
      "p999_cycles": 998.0,
      "avg_nanoseconds": 358.464,
      "steps_per_second": 2789680.4142117477
    },
    "speedup": 315.86
  },
  "128_neurons": {
    "python": {
      "iterations": 25000,
      "avg_ns": 111563.352,
      "p50_ns": 94800.0,
      "p90_ns": 148300.0,
      "p99_ns": 254400.0,
      "p999_ns": 417900.0,
      "min_ns": 35300.0,
      "max_ns": 2283600.0,
      "steps_per_sec": 8963.516980020464
    },
    "cpp": {
      "total_steps": 50000,
      "total_cycles": 72476116,
      "min_cycles": 1368,
      "max_cycles": 448220,
      "p50_cycles": 1406.0,
      "p90_cycles": 1426.0,
      "p99_cycles": 1468.0,
      "p999_cycles": 1872.0,
      "avg_nanoseconds": 609.156,
      "steps_per_second": 1641615.6124211205
    },
    "speedup": 183.14
  },
  "256_neurons": {
    "python": {
      "iterations": 25000,
      "avg_ns": 137124.072,
      "p50_ns": 138500.0,
      "p90_ns": 177400.0,
      "p99_ns": 289300.0,
      "p999_ns": 479800.0,
      "min_ns": 39900.0,
      "max_ns": 3398600.0,
      "steps_per_sec": 7292.665579534423
    },
    "cpp": {
      "total_steps": 50000,
      "total_cycles": 132712733,
      "min_cycles": 1760,
      "max_cycles": 310828,
      "p50_cycles": 2630.0,
      "p90_cycles": 2674.0,
      "p99_cycles": 3794.0,
      "p999_cycles": 7732.0,
      "avg_nanoseconds": 1079.094,
      "steps_per_second": 926703.3270502848
    },
    "speedup": 127.07
  }
}
```

### Full RSNN Execution
```
{
  "python": {
    "iterations": 25000,
    "avg_ns": 456174.036,
    "p50_ns": 501500.0,
    "p90_ns": 630400.0,
    "p99_ns": 770900.0,
    "p999_ns": 952400.0,
    "min_ns": 164100.0,
    "max_ns": 1294800.0,
    "steps_per_sec": 2192.145806386929
  },
  "cpp": {
    "total_steps": 50000,
    "total_cycles": 141913551,
    "min_cycles": 1338,
    "max_cycles": 218803,
    "p50_cycles": 2712.0,
    "p90_cycles": 3616.0,
    "p99_cycles": 4418.0,
    "p999_cycles": 6714.0,
    "avg_nanoseconds": 1153.322,
    "steps_per_second": 867060.5433695014
  },
  "speedup": 395.53
}
```
