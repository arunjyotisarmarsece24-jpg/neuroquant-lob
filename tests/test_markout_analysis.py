"""
Unit Tests for Post-Trade Markout & Adverse Selection Analysis
==============================================================
Validates that NeuroQuant SNN toxic sweep defense empirically eliminates
Winner's Curse adverse selection, transforming negative markouts into positive net edge.

Author: Arunjyoti Sarma (Research Scholar, IIT (BHU), Varanasi)
"""

import unittest
from neuroquant.analysis.markout import MarkoutAnalyzer, MarkoutReport


class TestMarkoutAnalysis(unittest.TestCase):

    def setUp(self):
        self.analyzer = MarkoutAnalyzer(maker_rebate_bps=0.20)

    def test_markout_simulation_execution(self):
        report = self.analyzer.run_markout_study(num_ticks=2000, toxic_ratio=0.20, random_seed=42)
        self.assertIsInstance(report, MarkoutReport)
        self.assertGreater(report.total_quotes_posted, 1000)
        self.assertGreater(report.naive_fills, 0)
        self.assertGreater(report.neuro_fills, 0)
        self.assertGreater(report.toxic_sweeps_defended, 100)
        self.assertGreater(report.defense_rate_pct, 75.0)

    def test_adverse_selection_elimination(self):
        """NeuroQuant SNN markout must statistically beat naive MM markout."""
        report = self.analyzer.run_markout_study(num_ticks=3000, toxic_ratio=0.20, random_seed=777)

        # 10ms horizon: immediate microstructure sweep impact
        h10 = report.horizons[0]
        self.assertEqual(h10.horizon_ms, 10)
        self.assertLess(h10.naive_mean_bps, -0.5) # Naive MM is hit hard by toxic sweeps
        self.assertGreater(h10.neuro_mean_bps, h10.naive_mean_bps)
        self.assertGreater(h10.bps_improvement, 0.5) # Clear alpha improvement
        self.assertLess(h10.p_value, 0.01) # Highly statistically significant (p < 0.01)

        # 100ms horizon: cumulative order flow impact
        h100 = report.horizons[2]
        self.assertEqual(h100.horizon_ms, 100)
        self.assertGreater(h100.neuro_mean_bps, h100.naive_mean_bps)

        # Net edge (markout + 0.2 bps rebate) is strictly superior
        self.assertGreater(report.neuro_net_edge_bps, report.naive_net_edge_bps)
        self.assertGreater(report.net_alpha_gain_bps, 0.0)


if __name__ == "__main__":
    unittest.main()
