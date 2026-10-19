"""
Unit Tests for Purged & Embargoed Walk-Forward Backtest & Deflated Sharpe Ratio
=============================================================================
Tests strict compliance with Marcos López de Prado's Purged & Embargoed
Cross-Validation methodology and Bailey & López de Prado (2014) Deflated Sharpe Ratio.

Author: Arunjyoti Sarma (Research Scholar, IIT (BHU), Varanasi)
"""

import unittest
import numpy as np
import math

from neuroquant.backtesting.walk_forward import (
    PurgedKFold,
    WalkForwardBacktester,
    BacktestResult,
    compute_probabilistic_sharpe_ratio,
    compute_deflated_sharpe_ratio
)


class TestPurgedWalkForwardBacktest(unittest.TestCase):

    def test_purged_kfold_no_leakage_and_embargo(self):
        """Test that train and test indices have zero overlap and respect purge and embargo zones."""
        n_samples = 1000
        horizon = 20
        embargo_pct = 0.05  # 50 samples
        embargo_size = int(math.ceil(n_samples * embargo_pct))

        cv = PurgedKFold(n_splits=5, horizon_ticks=horizon, embargo_pct=embargo_pct)
        all_test_indices = []

        for fold, (train_idx, test_idx) in enumerate(cv.split(n_samples)):
            test_start = int(test_idx[0])
            test_end = int(test_idx[-1]) + 1

            # 1. Zero intersection between train and test
            overlap = set(train_idx).intersection(set(test_idx))
            self.assertEqual(len(overlap), 0, f"Fold {fold} has train-test overlap!")

            # 2. Verify purging: no train index should be in [test_start - horizon, test_start)
            purge_zone = set(range(max(0, test_start - horizon), test_start))
            purge_overlap = set(train_idx).intersection(purge_zone)
            self.assertEqual(len(purge_overlap), 0, f"Fold {fold} violates purging zone!")

            # 3. Verify embargoing: no train index should be in [test_end, test_end + embargo_size)
            embargo_zone = set(range(test_end, min(n_samples, test_end + embargo_size)))
            embargo_overlap = set(train_idx).intersection(embargo_zone)
            self.assertEqual(len(embargo_overlap), 0, f"Fold {fold} violates embargo zone!")

            all_test_indices.extend(test_idx.tolist())

        # All test indices should partition the entire dataset
        self.assertEqual(sorted(all_test_indices), list(range(n_samples)))

    def test_psr_and_dsr_analytical_bounds(self):
        """Test analytical properties of Probabilistic and Deflated Sharpe Ratios."""
        # 1. When Sharpe equals benchmark, PSR must equal 0.50 exactly
        psr_neutral = compute_probabilistic_sharpe_ratio(
            sharpe=0.0,
            sr_benchmark=0.0,
            n_samples=500,
            skew=0.0,
            kurt=3.0
        )
        self.assertAlmostEqual(psr_neutral, 0.50, places=4)

        # 2. High positive Sharpe must give PSR near 1.0
        psr_high = compute_probabilistic_sharpe_ratio(
            sharpe=2.5,
            sr_benchmark=0.0,
            n_samples=1000,
            skew=-0.2,
            kurt=3.5
        )
        self.assertGreater(psr_high, 0.99)

        # 3. Deflated Sharpe Ratio must be <= Probabilistic Sharpe Ratio (selection bias haircut)
        dsr_val = compute_deflated_sharpe_ratio(
            sharpe=2.5,
            n_samples=1000,
            skew=-0.2,
            kurt=3.5,
            n_trials=100
        )
        self.assertLessEqual(dsr_val, psr_high)
        self.assertGreater(dsr_val, 0.0)
        self.assertLessEqual(dsr_val, 1.0)

    def test_walk_forward_execution_on_market_ticks(self):
        """Test full out-of-sample walk forward execution and performance reporting."""
        np.random.seed(42)
        n_ticks = 2000
        # Generate synthetic price series
        dt_walk = np.random.normal(0, 0.5, size=n_ticks)
        mid_prices = 100.0 + np.cumsum(dt_walk)
        spreads = np.full(n_ticks, 0.05)
        # Generate predictable alpha signals + occasional toxic spikes
        signals = np.random.uniform(-0.8, 0.8, size=n_ticks)
        toxic_events = (np.random.random(size=n_ticks) < 0.05).astype(bool)

        backtester = WalkForwardBacktester(n_splits=4, horizon_ticks=20, embargo_pct=0.02)
        result = backtester.run_backtest(
            mid_prices=mid_prices,
            spreads=spreads,
            signals=signals,
            toxic_events=toxic_events,
            strategy_name="NeuroQuant-RSNN",
            is_neuro=True
        )

        self.assertIsInstance(result, BacktestResult)
        self.assertEqual(result.n_folds, 4)
        self.assertEqual(result.total_ticks, n_ticks)
        self.assertGreater(result.total_trades, 0)
        self.assertFalse(math.isnan(result.annualized_sharpe))
        self.assertFalse(math.isinf(result.annualized_sharpe))
        self.assertFalse(math.isnan(result.deflated_sharpe_ratio))
        self.assertGreaterEqual(result.deflated_sharpe_ratio, 0.0)
        self.assertLessEqual(result.deflated_sharpe_ratio, 1.0)
        self.assertEqual(len(result.fold_performances), 4)
        self.assertGreaterEqual(len(result.equity_curve), 1)


if __name__ == "__main__":
    unittest.main()
