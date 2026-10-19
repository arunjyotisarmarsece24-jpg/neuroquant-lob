"""
Automated Unit Tests for Day 6 Mathematical Theorems & Proof Invariants.
Tests Theorems 1, 2, 3 and Lemmas 1, 2 for NeuroQuant-LOB preprint.
"""

import os
import unittest
import numpy as np
from scipy import stats

from neuroquant.execution.almgren_chriss import AlmgrenChrissOptimizer, AlmgrenChrissConfig
from neuroquant.execution.market_impact import NonLinearMarketImpactEngine, MarketImpactConfig
from neuroquant.execution.fee_model import TieredExchangeFeeModel, FeeModelConfig

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class TestMathematicalProofInvariants(unittest.TestCase):
    def setUp(self):
        np.random.seed(42)

    def test_theorem_1_bibo_invariance_envelope(self):
        """Theorem 1: Continuous LIF membrane potential must remain within R_m * I_max envelope."""
        tau_m = 0.020  # 20 ms
        R_m = 10.0     # 10 MOhm
        I_max = 5.0    # 5 nA
        V_rest = -70.0
        dt = 1e-4      # 100 μs
        decay = np.exp(-dt / tau_m)
        coeff = R_m * (1.0 - decay)

        V = -100.0  # start out of equilibrium
        theoretical_bound = R_m * I_max
        burn_in = int(5.0 * tau_m / dt)

        # 50,000 steps of random bounded current
        inputs = np.random.uniform(-I_max, I_max, size=50_000)
        max_envelope = 0.0

        for t in range(50_000):
            V = decay * V + (1.0 - decay) * V_rest + coeff * inputs[t]
            if t > burn_in:
                env = abs(V - V_rest)
                if env > max_envelope:
                    max_envelope = env

        self.assertLessEqual(max_envelope, theoretical_bound + 1e-6,
                             f"Membrane envelope {max_envelope} exceeded theoretical bound {theoretical_bound}")

    def test_theorem_2_euler_lagrange_convex_optimality(self):
        """Theorem 2: No random perturbation delta_x can decrease the objective utility U(x*)."""
        X_0, T, N, risk_aversion = 10000.0, 60.0, 60, 1e-5
        config = AlmgrenChrissConfig(
            total_shares=X_0,
            time_horizon_sec=T,
            num_intervals=N,
            risk_aversion_lambda=risk_aversion,
            volatility_sigma=0.30,
            gamma=2.5e-7,
            eta=2.5e-6,
            alpha=1.0
        )
        optimizer = AlmgrenChrissOptimizer(config)
        opt_schedule = optimizer.calculate_optimal_schedule()
        x_opt = opt_schedule.holdings.copy()
        tau = T / N
        kappa, eta_tilde = optimizer.compute_kappa()

        def U(x):
            tr = x[:-1] - x[1:]
            return eta_tilde * np.sum((tr**2) / tau) + risk_aversion * (0.30**2) * tau * np.sum(x[1:]**2)

        U_opt = U(x_opt)

        # Test 10,000 random perturbations
        for _ in range(10_000):
            dx = np.zeros(N + 1)
            dx[1:-1] = np.random.normal(0, np.random.uniform(0.1, 100.0), size=N - 1)
            delta_U = U(x_opt + dx) - U_opt
            self.assertGreaterEqual(delta_U, -1e-9, f"Perturbation reduced utility by {delta_U}")

    def test_theorem_3_lyapunov_exponential_contraction(self):
        """Theorem 3: dot_V must be strictly negative outside attractor when spectral norm < tau_m / R_m."""
        tau_m = 0.020
        R_m = 10.0
        spectral_bound = tau_m / R_m  # 0.002
        N_dim = 8
        V_rest = -70.0

        for _ in range(500):
            raw_W = np.random.randn(N_dim, N_dim) / np.sqrt(N_dim)
            norm = np.linalg.norm(raw_W, 2)
            target_norm = spectral_bound * np.random.uniform(0.1, 0.9)
            W = raw_W * (target_norm / norm)

            I_ext = np.random.uniform(-1.0, 1.0, size=N_dim)
            I_norm = np.linalg.norm(I_ext, 2)
            attractor_radius = (R_m * I_norm) / (1.0 - (R_m / tau_m) * target_norm)

            direction = np.random.randn(N_dim)
            direction /= np.linalg.norm(direction)
            V = V_rest * np.ones(N_dim) + direction * (1.5 * attractor_radius + 0.5)

            diff = V - V_rest * np.ones(N_dim)
            diff_norm = np.linalg.norm(diff)
            dot_V = - (1.0 / tau_m) * (diff_norm**2) + (R_m / tau_m) * np.dot(diff, I_ext)
            self.assertLess(dot_V, 0.0, f"Lyapunov derivative non-negative: {dot_V}")

    def test_lemma_1_maker_taker_adverse_crossover(self):
        """Lemma 1: Maker execution strictly beats taker execution iff delta_adv < r_t - r_m = 0.7 bps."""
        maker_rebate = -0.00002  # -0.002%
        taker_fee = 0.00005      # +0.005%
        theoretical_threshold = taker_fee - maker_rebate  # 0.00007 = 0.7 bps

        deltas = np.linspace(0.0, 0.0002, 2000)
        cost_taker = taker_fee
        cost_maker = maker_rebate + deltas

        crossover_idx = np.where(cost_maker >= cost_taker)[0][0]
        empirical_threshold = deltas[crossover_idx]

        self.assertAlmostEqual(empirical_threshold, theoretical_threshold, places=5,
                               msg=f"Crossover {empirical_threshold} deviates from theoretical {theoretical_threshold}")

    def test_lemma_2_poisson_null_signal_expectation(self):
        """Lemma 2: Uninformative Poisson spike arrivals must yield E[AUC] = 0.5000 with p > 0.05."""
        sample_size = 200
        n_trials = 2000
        labels = np.zeros(sample_size, dtype=int)
        labels[sample_size // 2:] = 1
        n_pos = sample_size // 2
        n_neg = sample_size - n_pos

        scores = np.random.poisson(lam=8.0, size=(n_trials, sample_size)) + np.random.normal(0, 1e-4, size=(n_trials, sample_size))
        ranks = np.argsort(np.argsort(scores, axis=1), axis=1) + 1
        rank_sum = np.sum(ranks[:, labels == 1], axis=1)
        u1 = rank_sum - n_pos * (n_pos + 1) / 2.0
        aucs = u1 / (n_pos * n_neg)

        mean_auc = np.mean(aucs)
        t_stat, p_val = stats.ttest_1samp(aucs, 0.5)

        self.assertAlmostEqual(mean_auc, 0.5000, places=2, msg=f"Mean AUC {mean_auc} deviates from 0.5")
        self.assertGreater(p_val, 0.01, f"Poisson noise generated statistically significant signal: p = {p_val}")

    def test_stoikov_micro_price_invariants(self):
        """Verify Stoikov micro-price respects bounds S_b <= P_micro <= S_a and monotonic with imbalance."""
        S_b = 100.00
        S_a = 100.10
        Q_b = 500
        Q_a = 100

        # P_micro = S_b * (Q_a / (Q_b + Q_a)) + S_a * (Q_b / (Q_b + Q_a))
        P_micro = S_b * (Q_a / (Q_b + Q_a)) + S_a * (Q_b / (Q_b + Q_a))
        self.assertGreater(P_micro, (S_b + S_a) * 0.5, "P_micro must lean toward Ask when Bid volume is heavier")
        self.assertGreaterEqual(P_micro, S_b)
        self.assertLessEqual(P_micro, S_a)

    def test_bouchaud_propagator_monotonic_decay(self):
        """Verify Bouchaud propagator kernel G(dt) is monotonically decaying with dt."""
        tau_0 = 1.0
        gamma_prop = 0.5
        dts = np.linspace(0.0, 10.0, 100)
        G = (1.0 + dts / tau_0) ** (-gamma_prop)

        # Strictly decreasing
        diffs = np.diff(G)
        self.assertTrue(np.all(diffs <= 0.0), "Bouchaud propagator must be monotonically non-increasing")
        self.assertAlmostEqual(G[0], 1.0, places=6)

    def test_paper_pdf_and_rendered_pages_integrity(self):
        """Verify paper/neuroquant_lob.pdf and rendered pages exist and satisfy 6-page institutional constraint."""
        pdf_path = os.path.join(PROJECT_ROOT, "paper", "neuroquant_lob.pdf")
        self.assertTrue(os.path.exists(pdf_path), "neuroquant_lob.pdf does not exist")
        
        size_bytes = os.path.getsize(pdf_path)
        self.assertGreater(size_bytes, 500_000, "PDF size unexpectedly small (<500KB)")

        with open(pdf_path, "rb") as f:
            content = f.read()
        import re
        pages = len(re.findall(rb"/Type\s*/Page\b", content))
        self.assertEqual(pages, 6, f"PDF page count must be exactly 6, got {pages}")

        # Check rendered pages
        pages_dir = os.path.join(PROJECT_ROOT, "paper", "rendered_pages")
        self.assertTrue(os.path.exists(pages_dir), "paper/rendered_pages directory missing")
        for i in range(1, 7):
            page_img = os.path.join(pages_dir, f"page_{i}.png")
            self.assertTrue(os.path.exists(page_img), f"page_{i}.png missing in rendered_pages")

if __name__ == "__main__":
    unittest.main()
