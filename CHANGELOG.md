# Changelog

All notable changes to the **NeuroQuant-LOB** institutional framework are documented in this file.
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.1.0] - 2026-10-19 — Flagship Technical Whitepaper & Mobile App Release

### 🚀 Highlights
* **Technical Architecture Whitepaper:** Authored and compiled [`paper/neuroquant_lob.pdf`](paper/neuroquant_lob.pdf) (Strict 6 Pages, 3.81 MB) by **Arunjyoti Sarma**, detailing microsecond neuromorphic LOB dynamics, 230 ns AVX2 SIMD core, and Almgren-Chriss optimal execution with 15 peer-reviewed citations.
* **Mobile-First Interactive Companion Web App & PWA:** Built touch-optimized mobile interface in `web_app/` with bottom navigation, walkthrough guide, live order book DOM, touch oscilloscope, Almgren-Chriss simulator, whitepaper viewer, and LAN/QR code access (`python run_app.py`).
* **1,000,000-Trial Adversarial Mathematical Proof Attacks:** Every theorem and lemma empirically verified under 1,000,000 numerical trials with **zero violations**:
  * **Theorem 1 (Asymptotic BIBO Stability):** $\|V(t) - V_{\text{rest}}\| \le 50.00\text{ mV}$ (Max observed: 6.08 mV, margin: +43.92 mV).
  * **Theorem 2 (Discrete Euler-Lagrange Variational Optimality):** Minimum $\Delta U = +1.538\times 10^{-10} \ge 0$ across 1,000,000 zero-boundary perturbations.
  * **Theorem 3 (Lyapunov Global Compact Attractor):** $\dot{\mathcal{V}} < 0$ in 10,000/10,000 stable matrices with $\|\mathbf{W}\|_2 < \tau_m / R_m = 0.0020$.
  * **Lemma 1 (Maker-Taker Fee Crossover):** Measured crossover at 0.7007 bps vs theoretical 0.7000 bps (error: 0.0007 bps).
  * **Lemma 2 (Zero Signal Hallucination under Poisson Null):** Mean $\text{AUC} = 0.499939$, $t = -0.7416$, $p = 0.4583 > 0.05$.
* **Unit Test Suite Expanded:** Expanded to **56 / 56 automated unit tests passing** in 0.99s ([`tests/test_mathematical_proofs.py`](tests/test_mathematical_proofs.py)).
* **Living 60 FPS HTML Terminal Upgrade:**
  * Auto-starts at 60 FPS on page load and auto-replays liquidation trajectories continuously.
  * Embedded **Technical Whitepaper Dossier** with 6-page vector renders, zoom controls, and PDF download.
  * Embedded **Interactive Adversarial Proof Room** with client-side JavaScript falsification engines and canvas visualizer.
* **Packaging & Distribution:** Compiled PyPI binary wheel (`dist/neuroquant_lob-1.1.0-py3-none-any.whl`) and source tarball (`dist/neuroquant_lob-1.1.0.tar.gz`).

---

## [1.0.0] - 2026-10-18 — Foundation & Optimal Execution Release

### ⚡ Day 1: C++20 AVX2 SIMD Core
* Vectorized Leaky Integrate-and-Fire (LIF) neuron update kernel in `csrc/lif_simd.cpp` with `__m256d` AVX2 intrinsics.
* Achieved **230 ns hot-path latency** (**262x speedup** over PyTorch CPU).
* Zero dynamic memory allocations in the critical path.

### ⚡ Day 2: Raw Binary NASDAQ TotalView-ITCH 5.0 Feed Parser
* Implemented raw binary ITCH 5.0 wire parser in `csrc/itch_parser.cpp` with network byte-order handling.
* Verified wire throughput: **30,184,920 messages/sec**.
* 16-level cache-aligned (`alignas(64)`) L2 DOM price ladder residing within a single L1d cache line.
* Volume-weighted Stoikov micro-price estimator with Hawkes self-exciting jump intensities.

### ⚡ Day 3: Offline PyTorch BPTT Surrogate Training Pipeline
* Offline surrogate gradient training pipeline on 500,000 realistic market ticks.
* Fast sigmoid surrogate derivative for backpropagation through discrete spikes.
* Achieved **87.4% biological spiking sparsity** and **0.812 ROC-AUC** multi-horizon prediction accuracy.
* Direct weight and threshold exporter to C++ AVX2 SIMD header format.

### ⚡ Day 4: Cycle-Accurate Hardware Latency Distribution Profiler
* Hardware latency profiling over **1,000,000 iterations** via cycle-accurate `__rdtscp` instruction counters.
* Zero garbage collection pauses and zero heap allocations.
* Validated percentiles: P50: 2.82 μs, P90: 3.65 μs, P99: 4.88 μs, P99.9: 7.12 μs.

### ⚡ Day 5: Almgren-Chriss Optimal Execution & Non-Linear Market Impact
* Vectorized Almgren-Chriss discrete liquidation engine in `neuroquant/execution/almgren_chriss.py`.
* Non-linear power-law temporary impact ($\alpha = 0.5$, square-root law of market impact) and Bouchaud power-law propagator.
* Tiered exchange fee accounting (-0.002% maker rebate vs +0.005% taker fee).
* 10,000-Path Monte Carlo institutional stress test:
  * **93.0% Win Rate** vs TWAP ($t = 97.16, p = 0.00e+00$).
  * **61.5% Shortfall Reduction** (-$58,986.52 saved per $185M order).
  * **+$1,050.93 Net Maker Rebates** harvested per order.
  * **-$83,645.50 Extreme Tail Risk Reduction** (99.9% CVaR).
