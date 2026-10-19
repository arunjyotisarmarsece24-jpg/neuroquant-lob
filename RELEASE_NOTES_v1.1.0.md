# 🚀 NeuroQuant-LOB v1.1.0: Release Notes

## Microsecond Neuromorphic LOB Intelligence & Optimal Execution Engine

We are proud to release **NeuroQuant-LOB v1.1.0**, the flagship release of our continuous-time vectorized neuromorphic limit order book computing architecture by **Arunjyoti Sarma**.

[![Unit Tests](https://img.shields.io/badge/Unit%20Tests-56%2F56%20Passing-10b981?style=for-the-badge&logo=pytest)](tests/)
[![SIMD Speedup](https://img.shields.io/badge/AVX2%20SIMD-262x%20Speedup-00f0ff?style=for-the-badge&logo=c%2B%2B)](csrc/)
[![Wire Throughput](https://img.shields.io/badge/ITCH%205.0-30.18M%20msgs%2Fs-a855f7?style=for-the-badge)](csrc/itch_parser.cpp)
[![Shortfall Reduction](https://img.shields.io/badge/Execution%20Surplus--61.5%25%20Shortfall-fcd34d?style=for-the-badge)](neuroquant/execution/)
[![Whitepaper PDF](https://img.shields.io/badge/Whitepaper-6%20Pages-60a5fa?style=for-the-badge)](paper/neuroquant_lob.pdf)

---

### What's New in v1.1.0

1. **Technical Architecture Whitepaper (`paper/neuroquant_lob.pdf`):**
   * Authored by Arunjyoti Sarma (Strict 6 Pages, 3.81 MB).
   * Complete mathematical proofs and closed-form derivations for all 5 theorems and lemmas.
   * High-resolution 150 DPI vector-sharp page renders in `paper/rendered_pages/`.

2. **Mobile-First Interactive Companion Web App & PWA (`run_app.py` & `web_app/`):**
   * Touch-optimized responsive mobile interface for smartphone and tablet inspection.
   * Visual Walkthrough Guide explaining microstructure, 230 ns SIMD, RSNN biology, and Almgren-Chriss execution.
   * Real-time mobile L2 order book DOM, touch oscilloscope, interactive execution trajectory calculator, live mathematical proof attack simulator, and 6-page whitepaper reader.
   * Direct Wi-Fi LAN access with console QR code for instant smartphone connection (`http://<LAN_IP>:5000`).

3. **1,000,000-Trial Adversarial Proof Falsification Harness (`benchmarks/run_adversarial_proof_attacks.py`):**
   * **Theorem 1 (BIBO Voltage Invariance):** Max envelope $6.08\text{ mV} \le 50.00\text{ mV}$ (0 violations / 1,000,000 ticks).
   * **Theorem 2 (Euler-Lagrange Convex Optimality):** Minimum $\Delta U = +1.538\times 10^{-10} \ge 0$ (0 violations / 1,000,000 perturbations).
   * **Theorem 3 (Lyapunov Attractor Stability):** Negative definite drift $\dot{\mathcal{V}} < 0$ verified across 10,000 stable matrices.
   * **Lemma 1 (Maker-Taker Dominance Crossover):** Measured crossover at $0.7007\text{ bps}$ vs theoretical $0.7000\text{ bps}$ (error: $0.0007\text{ bps}$).
   * **Lemma 2 (Zero Signal Hallucination under Null):** Mean $\text{AUC} = 0.499939$ ($t = -0.7416, p = 0.4583 > 0.05$).

4. **Expanded Automated Unit Test Suite (`tests/test_mathematical_proofs.py`):**
   * 56 / 56 tests passing cleanly in 0.99s across all subsystems.

5. **Living 60 FPS Master Terminal (`benchmarks/audit_report.html`):**
   * Auto-looping Almgren-Chriss liquidation trajectory at 60 FPS with dynamic Hawkes path regeneration.
   * Interactive 16-level DOM depth ladder and dual-trace electron-beam oscilloscope.
   * Interactive 6-page manuscript reader with zoom controls and 1-click PDF download.
   * In-browser JavaScript adversarial proof attack simulator.

6. **PyPI Distribution Package:**
   * Wheel: `dist/neuroquant_lob-1.1.0-py3-none-any.whl`
   * Source tarball: `dist/neuroquant_lob-1.1.0.tar.gz`

---

### Installation & Quick Start

```powershell
# Install via wheel:
pip install dist/neuroquant_lob-1.1.0-py3-none-any.whl

# Or clone from source:
git clone https://github.com/arunjyotisarmarsece24-jpg/neuroquant-lob.git
cd neuroquant-lob

# Run master institutional verification suite:
python verify.py

# Launch living 60 FPS institutional terminal:
python verify.py --open-only
```
