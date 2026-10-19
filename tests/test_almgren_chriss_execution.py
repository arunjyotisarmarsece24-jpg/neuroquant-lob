"""
Unit Tests: Almgren-Chriss Optimal Execution & Non-Linear Market Impact
======================================================================
Verifies mathematical formulations, non-linear square-root market impact,
tiered maker rebate / taker fee accounting, and neuromorphic adaptive urgency.
"""

import unittest
import numpy as np
from config import AlmgrenChrissExecutionConfig, CONFIG_AC
from neuroquant.execution import (
    NonLinearMarketImpactEngine,
    MarketImpactConfig,
    TieredExchangeFeeModel,
    FeeModelConfig,
    AlmgrenChrissOptimizer,
    AlmgrenChrissConfig,
    NeuromorphicAdaptiveExecutionEngine,
    AdaptiveUrgencyConfig
)

class TestAlmgrenChrissExecution(unittest.TestCase):
    def setUp(self):
        self.ac_cfg = AlmgrenChrissConfig(
            total_shares=10_000.0,
            time_horizon_sec=60.0,
            num_intervals=20,
            risk_aversion_lambda=1e-4,
            volatility_sigma=0.20,
            gamma=2.5e-7,
            eta=5.0e-5,
            alpha=0.5,
            spread=0.25
        )
        self.optimizer = AlmgrenChrissOptimizer(self.ac_cfg)
        self.impact_engine = NonLinearMarketImpactEngine()
        self.fee_model = TieredExchangeFeeModel()

    def test_almgren_chriss_trajectory_monotonicity(self):
        """Verifies holdings monotonically decrease to zero and trades sum to total shares."""
        sched = self.optimizer.calculate_optimal_schedule()
        
        # 1. Boundary conditions
        self.assertAlmostEqual(sched.holdings[0], 10_000.0, places=4)
        self.assertAlmostEqual(sched.holdings[-1], 0.0, places=4)
        
        # 2. Strict monotonicity
        for j in range(len(sched.holdings) - 1):
            self.assertGreater(sched.holdings[j], sched.holdings[j + 1],
                               f"Holdings must strictly decrease at step {j}")
            
        # 3. All individual trade slices are positive
        for j, trade in enumerate(sched.trades):
            self.assertGreater(trade, 0.0, f"Trade at step {j} must be strictly positive")
            
        # 4. Conservation of shares
        self.assertAlmostEqual(float(np.sum(sched.trades)), 10_000.0, places=4)

    def test_discrete_euler_lagrange_formula_equivalence(self):
        """Verifies discrete trade size formula matches step-wise inventory differences."""
        sched = self.optimizer.calculate_optimal_schedule()
        for j in range(len(sched.trades)):
            diff = sched.holdings[j] - sched.holdings[j + 1]
            self.assertAlmostEqual(sched.trades[j], diff, places=4)

    def test_risk_aversion_monotonic_half_life(self):
        """Verifies that higher risk aversion increases kappa and accelerates liquidation half-life."""
        sched_low = self.optimizer.calculate_optimal_schedule(lambda_val=1e-6)
        sched_med = self.optimizer.calculate_optimal_schedule(lambda_val=1e-4)
        sched_high = self.optimizer.calculate_optimal_schedule(lambda_val=5e-3)

        # Kappa strictly increases with lambda
        self.assertLess(sched_low.kappa, sched_med.kappa)
        self.assertLess(sched_med.kappa, sched_high.kappa)

        # Half-life strictly decreases with lambda (front-loading)
        self.assertGreater(sched_low.half_life_sec, sched_med.half_life_sec)
        self.assertGreater(sched_med.half_life_sec, sched_high.half_life_sec)

        # Variance of shortfall strictly decreases with lambda
        self.assertGreater(sched_low.variance_shortfall, sched_med.variance_shortfall)
        self.assertGreater(sched_med.variance_shortfall, sched_high.variance_shortfall)

    def test_non_linear_square_root_market_impact(self):
        """Verifies that non-linear temporary impact scales as eta * v^0.5 (sublinear)."""
        rate_1 = 100.0
        rate_4 = 400.0  # 4x increase in trading rate
        
        impact_1 = self.impact_engine.temporary_impact(rate_1)
        impact_4 = self.impact_engine.temporary_impact(rate_4)

        # For square-root scaling (v^0.5), a 4x increase in rate results in exactly 2x increase in impact
        ratio = impact_4 / impact_1
        self.assertAlmostEqual(ratio, 2.0, places=4)

        # Check execution price concession for sell taker
        res = self.impact_engine.calculate_execution(
            mid_price=100.0,
            order_qty=500.0,
            dt=3.0,
            is_selling=True,
            is_taker=True,
            current_spread=0.25
        )
        self.assertLess(res["exec_price"], 100.0, "Taker sell execution price must be below mid")
        self.assertGreater(res["half_spread_cost"], 0.0)
        self.assertGreater(res["temp_impact_per_share"], 0.0)
        self.assertGreater(res["perm_impact_per_share"], 0.0)

        # Check passive maker order: earns spread, zero temporary impact
        res_maker = self.impact_engine.calculate_execution(
            mid_price=100.0,
            order_qty=500.0,
            dt=3.0,
            is_selling=True,
            is_taker=False,
            current_spread=0.25
        )
        self.assertGreater(res_maker["exec_price"], 100.0, "Maker sell execution captures spread")
        self.assertEqual(res_maker["temp_impact_per_share"], 0.0, "Maker order has zero temporary impact")

    def test_tiered_exchange_fee_and_maker_rebate(self):
        """Verifies -0.002% maker rebate credit vs +0.005% taker fee debit."""
        notional = 1_000_000.0  # $1 Million notional

        # Maker: rate = -0.00002 -> -$20.00 cash impact (rebate credit)
        m_rate, m_impact = self.fee_model.calculate_trade_fee(notional, is_maker=True)
        self.assertAlmostEqual(m_rate, -0.00002, places=7)
        self.assertAlmostEqual(m_impact, -20.00, places=4)

        # Taker: rate = +0.00005 -> +$50.00 cash impact (fee debit)
        t_rate, t_impact = self.fee_model.calculate_trade_fee(notional, is_maker=False)
        self.assertAlmostEqual(t_rate, 0.00005, places=7)
        self.assertAlmostEqual(t_impact, 50.00, places=4)

        # Net swing is 7 bps = $70.00
        self.assertAlmostEqual(t_impact - m_impact, 70.00, places=4)

    def test_implementation_shortfall_tca_accounting(self):
        """Verifies institutional Implementation Shortfall Transaction Cost Analysis."""
        fee_model = TieredExchangeFeeModel()
        arrival_price = 100.00
        target_qty = 1000.0

        # Fill 1: 500 shares taker at 99.80 (20 cents slippage)
        fee_model.record_fill(1.0, 1, 500.0, 99.80, is_selling=True, is_maker=False)
        # Fill 2: 500 shares maker at 100.10 (-10 cents slippage / gain)
        fee_model.record_fill(2.0, 2, 500.0, 100.10, is_selling=True, is_maker=True)

        tca = fee_model.compute_implementation_shortfall(arrival_price, target_qty, is_selling=True)

        # Benchmark: 1000 * 100 = 100,000
        self.assertAlmostEqual(tca["benchmark_notional"], 100_000.0)
        # Realized: 500*99.80 + 500*100.10 = 49,900 + 50,050 = 99,950
        self.assertAlmostEqual(tca["realized_notional"], 99_950.0)
        # Gross slippage: 100,000 - 99,950 = $50.00
        self.assertAlmostEqual(tca["gross_slippage_dollars"], 50.00)

        # Net fees: Taker fee on 49,900 is $2.495; Maker rebate on 50,050 is $1.001
        expected_taker_fee = 49_900.0 * 0.00005
        expected_maker_rebate = 50_050.0 * 0.00002
        expected_net_fee = expected_taker_fee - expected_maker_rebate
        self.assertAlmostEqual(tca["total_taker_fees_dollars"], expected_taker_fee, places=4)
        self.assertAlmostEqual(tca["total_maker_rebates_dollars"], expected_maker_rebate, places=4)

        # Net shortfall = Gross slippage + Net fees
        expected_net_shortfall = 50.00 + expected_net_fee
        self.assertAlmostEqual(tca["net_shortfall_dollars"], expected_net_shortfall, places=4)

    def test_neuromorphic_adaptive_urgency_acceleration(self):
        """Verifies that RSNN toxicity alert accelerates liquidation urgency and front-loads trades."""
        cfg = AdaptiveUrgencyConfig(total_shares=1000.0, num_intervals=10, time_horizon_sec=30.0)
        engine = NeuromorphicAdaptiveExecutionEngine(cfg)

        # Step 1: Normal calm market
        step_calm = engine.compute_adaptive_trade_slice(
            remaining_shares=1000.0,
            intervals_left=10,
            neuro_signals={"toxicity_prob": 0.0, "volatility_pulse": 0.0, "upward_prob": 0.0, "downward_prob": 0.0}
        )
        slice_calm, is_maker_calm, kappa_calm = step_calm

        # Step 2: Severe toxic institutional cascade
        step_toxic = engine.compute_adaptive_trade_slice(
            remaining_shares=1000.0,
            intervals_left=10,
            neuro_signals={"toxicity_prob": 0.85, "volatility_pulse": 0.0, "upward_prob": 0.0, "downward_prob": 0.0}
        )
        slice_toxic, is_maker_toxic, kappa_toxic = step_toxic

        # High toxicity must strictly increase urgency and initial liquidation size
        self.assertGreater(kappa_toxic, kappa_calm, "Toxicity must increase effective kappa")
        self.assertGreater(slice_toxic, slice_calm, "Toxicity must increase trade slice size")
        self.assertFalse(is_maker_toxic, "Toxicity forces aggressive taker order")

    def test_twap_vwap_and_ac_conservation_invariants(self):
        """Verifies all execution benchmarks strictly preserve share conservation and zero residual."""
        twap = self.optimizer.calculate_twap_schedule()
        vwap = self.optimizer.calculate_vwap_schedule()
        ac_linear = self.optimizer.calculate_optimal_schedule()
        ac_nonlinear = self.optimizer.calculate_nonlinear_schedule()

        for name, sched in [("TWAP", twap), ("VWAP", vwap), ("AC_Linear", ac_linear), ("AC_Nonlinear", ac_nonlinear)]:
            self.assertAlmostEqual(float(np.sum(sched.trades)), 10_000.0, places=2,
                                   msg=f"{name} trades must sum to initial shares")
            self.assertAlmostEqual(sched.holdings[-1], 0.0, places=2,
                                   msg=f"{name} final holdings must be 0")
            self.assertGreater(sched.expected_shortfall, 0.0,
                               msg=f"{name} expected shortfall must be positive")

if __name__ == "__main__":
    unittest.main()
