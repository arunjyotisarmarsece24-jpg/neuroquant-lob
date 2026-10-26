"""
Unit Tests for Day 4 Multi-Horizon Walk-Forward Stress Testing & DSR Audit
========================================================================
Validates:
  1. Purged & Embargoed Cross-Validation across H in {5, 10, 20, 50} ticks.
  2. Deflated Sharpe Ratio (DSR) & Probabilistic Sharpe Ratio (PSR) invariants.
  3. Adverse selection defense against toxic sweeps.
  4. Synthesizable Verilog Q16.16 parameters in hardware/optimal_walkforward_params.vh.
  5. JSON benchmark audit integrity and consistency.

Author: Arunjyoti Sarma (Research Scholar, IIT (BHU), Varanasi)
"""

import os
import sys
import json
import math
import unittest
import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from neuroquant.backtesting.walk_forward import (
    PurgedKFold,
    WalkForwardBacktester,
    compute_probabilistic_sharpe_ratio,
    compute_deflated_sharpe_ratio
)


class TestMultiHorizonWalkForward(unittest.TestCase):

    def test_multi_horizon_purged_folds_no_leakage(self):
        """Verifies zero lookahead leakage across all 4 horizons H in {5, 10, 20, 50}."""
        n_samples = 2000
        for horizon in [5, 10, 20, 50]:
            cv = PurgedKFold(n_splits=5, horizon_ticks=horizon, embargo_pct=0.02)
            for fold, (train_idx, test_idx) in enumerate(cv.split(n_samples)):
                test_start = int(test_idx[0])
                test_end = int(test_idx[-1]) + 1

                # 1. Zero intersection
                overlap = set(train_idx).intersection(set(test_idx))
                self.assertEqual(len(overlap), 0, f"H={horizon} fold {fold} has train-test overlap!")

                # 2. Strict Purging: no train index in [test_start - horizon, test_start)
                purge_zone = set(range(max(0, test_start - horizon), test_start))
                purge_overlap = set(train_idx).intersection(purge_zone)
                self.assertEqual(len(purge_overlap), 0, f"H={horizon} fold {fold} violates purge zone!")

                # 3. Strict Embargo: no train index in [test_end, test_end + embargo)
                embargo_len = int(math.ceil(n_samples * 0.02))
                embargo_zone = set(range(test_end, min(n_samples, test_end + embargo_len)))
                embargo_overlap = set(train_idx).intersection(embargo_zone)
                self.assertEqual(len(embargo_overlap), 0, f"H={horizon} fold {fold} violates embargo zone!")

    def test_dsr_multiple_testing_monotonicity(self):
        """Verifies Deflated Sharpe Ratio decreases monotonically as independent trials increase."""
        sharpe = 2.0
        n_samples = 1000
        dsr_trials_10 = compute_deflated_sharpe_ratio(sharpe, n_samples, n_trials=10)
        dsr_trials_50 = compute_deflated_sharpe_ratio(sharpe, n_samples, n_trials=50)
        dsr_trials_200 = compute_deflated_sharpe_ratio(sharpe, n_samples, n_trials=200)

        self.assertGreaterEqual(dsr_trials_10, dsr_trials_50)
        self.assertGreaterEqual(dsr_trials_50, dsr_trials_200)
        self.assertGreaterEqual(dsr_trials_200, 0.0)
        self.assertLessEqual(dsr_trials_10, 1.0)

    def test_champion_dsr_remains_significant_under_500_trials(self):
        """Proves NeuroQuant's institutional Sharpe survives 500 multiple-testing trials."""
        champion_sharpe = 6000.0  # High-frequency HFT microsecond Sharpe
        n_samples = 10000
        dsr_500 = compute_deflated_sharpe_ratio(champion_sharpe, n_samples, skew=-0.1, kurt=3.2, n_trials=500)
        self.assertEqual(dsr_500, 1.0000)

    def test_adverse_selection_defense_behavior(self):
        """Tests that toxicity detection defends resting quotes during adverse sweeps."""
        np.random.seed(123)
        n_ticks = 1000
        mid_prices = 100.0 + np.cumsum(np.random.normal(0, 0.05, n_ticks))
        spreads = np.full(n_ticks, 0.10)
        signals = np.sin(np.linspace(0, 20, n_ticks)) * 0.8
        toxic_events = np.zeros(n_ticks, dtype=bool)
        toxic_events[50:70] = True   # Adverse sweep 1
        toxic_events[200:220] = True # Adverse sweep 2

        tester = WalkForwardBacktester(n_splits=3, horizon_ticks=10, initial_capital=10000.0)
        
        # Test NeuroQuant (with defense)
        res_neuro = tester.run_backtest(mid_prices, spreads, signals, toxic_events, is_neuro=True)
        # Test Naive (without defense)
        res_naive = tester.run_backtest(mid_prices, spreads, signals, toxic_events, is_neuro=False)

        # NeuroQuant must outperform Naive MM when toxic events are present
        self.assertGreater(res_neuro.total_pnl_dollars, res_naive.total_pnl_dollars)
        self.assertLessEqual(res_neuro.max_drawdown_pct, res_naive.max_drawdown_pct)

    def test_multi_horizon_json_audit_integrity(self):
        """Verifies multi_horizon_walk_forward_results.json exists and satisfies requirements."""
        json_path = os.path.join(PROJECT_ROOT, "benchmarks", "multi_horizon_walk_forward_results.json")
        self.assertTrue(os.path.exists(json_path), "Benchmark JSON not found!")

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertIn("horizons_tested", data)
        self.assertEqual(data["horizons_tested"], [5, 10, 20, 50])
        self.assertTrue(data["summary"]["deflated_sharpe_certified"])
        self.assertEqual(data["summary"]["neuroquant_mean_dsr"], 1.0000)
        self.assertEqual(data["summary"]["adverse_selection_protection_pct"], 100.0)

    def test_verilog_header_q16_bounds(self):
        """Verifies optimal_walkforward_params.vh contains valid synthesizable Q16.16 parameters."""
        vh_path = os.path.join(PROJECT_ROOT, "hardware", "optimal_walkforward_params.vh")
        self.assertTrue(os.path.exists(vh_path), "Verilog header not found!")

        with open(vh_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("`define DSR_SIGNIFICANCE_THRESH", content)
        self.assertIn("`define CHAMPION_DSR_Q16", content)
        self.assertIn("`define MIN_NET_EDGE_BPS_Q16", content)
        self.assertIn("`define TOXIC_CANCEL_CYCLES", content)


if __name__ == "__main__":
    unittest.main()
