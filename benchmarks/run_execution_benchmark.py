"""
Almgren-Chriss Optimal Execution & Non-Linear Market Impact Benchmark
====================================================================
Institutional Comparative Benchmark:
  1. Static TWAP (Time-Weighted Average Price)
  2. Static VWAP (Volume-Weighted Average Price)
  3. Static Almgren-Chriss (Euler-Lagrange Closed-Form Optimal)
  4. Neuromorphic Adaptive Almgren-Chriss (RSNN-guided with Maker Rebate Capture & Toxicity Avoidance)

Features:
  - Non-linear square-root market impact: h(v) = eta * sign(v) * |v|^0.5
  - Permanent price impact: g(v) = gamma * v
  - Tiered Exchange Fee Accounting: -0.002% maker rebate vs +0.005% taker fee
  - Institutional Flash Crash / Toxic Liquidity Cascade Injection
  - Value at Risk (VaR 95% and 99%) & Implementation Shortfall (TCA)
  - Ultra-HD 6-Panel Visual Diagnostic Poster & JSON Result Export
"""

import os
import sys
import json
from typing import Optional, List, Dict, Any, Tuple
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

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

def simulate_market_scenario(num_intervals: int = 30, 
                             tau: float = 2.0, 
                             p0: float = 18500.0, 
                             sigma: float = 0.25,
                             seed: int = 42):
    """
    Simulates a realistic microstructural market path with an institutional
    toxic sweep / flash cascade occurring midway through the liquidation window.
    """
    np.random.seed(seed)
    time_points = np.linspace(0.0, num_intervals * tau, num_intervals + 1)
    
    # Base random walk increments (calm volatility)
    dt = tau
    dW = np.random.normal(0.0, np.sqrt(dt), size=num_intervals)
    price_innovations = sigma * dW
    
    # Injected Institutional Toxic Cascade / Flash Crash regime (intervals 10 to 18)
    # Price plummets sharply by ~20 points due to aggressive outside sell sweeps
    crash_start = 10
    crash_end = 18
    for i in range(crash_start, crash_end):
        price_innovations[i] -= np.random.uniform(1.8, 3.2)
        
    # Calm recovery / upward bounce regime (intervals 19 to 25)
    bounce_start = 19
    bounce_end = 25
    for i in range(bounce_start, bounce_end):
        price_innovations[i] += np.random.uniform(0.6, 1.4)
        
    # Cumulative unperturbed exogenous mid-price path
    base_mid = np.zeros(num_intervals + 1)
    base_mid[0] = p0
    for i in range(num_intervals):
        base_mid[i + 1] = base_mid[i] + price_innovations[i]
        
    # Microstructure RSNN Motor Signals per interval:
    # [upward_prob, downward_prob, toxicity_prob, volatility_pulse]
    neuro_signals = []
    for i in range(num_intervals):
        if crash_start <= i < crash_end:
            # Toxic cascade: severe toxicity alert and volatility burst
            neuro_signals.append({
                "upward_prob": float(np.random.uniform(0.02, 0.08)),
                "downward_prob": float(np.random.uniform(0.70, 0.95)),
                "toxicity_prob": float(np.random.uniform(0.75, 0.96)),
                "volatility_pulse": float(np.random.uniform(0.65, 0.90))
            })
        elif bounce_start <= i < bounce_end:
            # Upward recovery: bullish drift, low toxicity
            neuro_signals.append({
                "upward_prob": float(np.random.uniform(0.65, 0.88)),
                "downward_prob": float(np.random.uniform(0.05, 0.15)),
                "toxicity_prob": float(np.random.uniform(0.02, 0.10)),
                "volatility_pulse": float(np.random.uniform(0.10, 0.25))
            })
        else:
            # Calm two-sided balanced regime with natural micro-flow fluctuations
            neuro_signals.append({
                "upward_prob": float(np.random.uniform(0.15, 0.48)),
                "downward_prob": float(np.random.uniform(0.15, 0.40)),
                "toxicity_prob": float(np.random.uniform(0.02, 0.14)),
                "volatility_pulse": float(np.random.uniform(0.05, 0.22))
            })
            
    return time_points, base_mid, price_innovations, neuro_signals

def run_simulation_strategy(strategy_name: str,
                            trades_schedule: Optional[np.ndarray],
                            base_mid: np.ndarray,
                            price_innovations: np.ndarray,
                            neuro_signals: list,
                            total_shares: float = 10000.0,
                            tau: float = 2.0,
                            ac_cfg: Optional[AlmgrenChrissConfig] = None):
    """
    Executes a liquidation strategy step-by-step through the market scenario,
    accounting for endogenous permanent & non-linear temporary market impact,
    spread costs, and tiered maker/taker exchange fees.
    """
    num_intervals = len(neuro_signals)
    impact_engine = NonLinearMarketImpactEngine(MarketImpactConfig(
        gamma=ac_cfg.gamma, eta=ac_cfg.eta, alpha=ac_cfg.alpha, default_spread=ac_cfg.spread
    ))
    fee_model = TieredExchangeFeeModel(FeeModelConfig(
        maker_fee_rate=-0.00002, taker_fee_rate=0.00005
    ))
    
    adaptive_engine = None
    if strategy_name == "NeuroQuant_Adaptive_AC":
        adaptive_cfg = AdaptiveUrgencyConfig(
            total_shares=total_shares,
            time_horizon_sec=num_intervals * tau,
            num_intervals=num_intervals,
            base_lambda=ac_cfg.risk_aversion_lambda,
            volatility_sigma=ac_cfg.volatility_sigma,
            gamma=ac_cfg.gamma,
            eta=ac_cfg.eta,
            alpha=ac_cfg.alpha,
            spread=ac_cfg.spread
        )
        adaptive_engine = NeuromorphicAdaptiveExecutionEngine(adaptive_cfg)
        
    current_mid = base_mid[0]
    holdings = np.zeros(num_intervals + 1)
    holdings[0] = total_shares
    
    executed_slices = []
    exec_prices = []
    mid_prices = [current_mid]
    is_maker_list = []
    step_perm_impacts = []
    step_temp_impacts = []
    step_spread_costs = []
    
    for i in range(num_intervals):
        # 1. Determine trade slice size and routing (maker vs taker)
        if strategy_name == "NeuroQuant_Adaptive_AC":
            intervals_left = num_intervals - i
            slice_qty, is_maker, eff_kappa = adaptive_engine.compute_adaptive_trade_slice(
                holdings[i], intervals_left, neuro_signals[i]
            )
        else:
            slice_qty = float(trades_schedule[i])
            is_maker = False  # Static TWAP, VWAP, AC route 100% as aggressive taker orders
            
        # Clamp slice
        slice_qty = max(0.0, min(slice_qty, holdings[i]))
        if i == num_intervals - 1:
            slice_qty = holdings[i]  # Final liquidation guarantee
            
        # 2. Compute non-linear market impact & execution price
        impact = impact_engine.calculate_execution(
            mid_price=current_mid,
            order_qty=slice_qty,
            dt=tau,
            is_selling=True,
            is_taker=not is_maker,
            current_spread=ac_cfg.spread
        )
        
        exec_price = impact["exec_price"]
        
        # 3. Record exchange fee or rebate
        fee_model.record_fill(
            timestamp=(i + 1) * tau,
            order_id=i + 1,
            quantity=slice_qty,
            exec_price=exec_price,
            is_selling=True,
            is_maker=is_maker
        )
        
        # 4. Advance holdings and mid price (endogenous permanent impact + exogenous market innovation)
        holdings[i + 1] = max(0.0, holdings[i] - slice_qty)
        current_mid = impact["new_mid_price"] + price_innovations[i]
        
        executed_slices.append(slice_qty)
        exec_prices.append(exec_price)
        mid_prices.append(current_mid)
        is_maker_list.append(is_maker)
        step_perm_impacts.append(impact["perm_impact_per_share"] * slice_qty)
        step_temp_impacts.append(impact["temp_impact_per_share"] * slice_qty)
        step_spread_costs.append(impact["half_spread_cost"] * slice_qty)
        
    holdings[-1] = 0.0  # Guarantee clean zero termination
    
    # Compute TCA metrics
    tca = fee_model.compute_implementation_shortfall(
        arrival_price=base_mid[0],
        target_quantity=total_shares,
        is_selling=True
    )
    
    # Compute Value at Risk (VaR 95% and 99%) over holdings trajectory
    holding_values = holdings[1:] * base_mid[0]
    var_95 = 1.645 * ac_cfg.volatility_sigma * np.sqrt(tau) * np.mean(holding_values)
    var_99 = 2.326 * ac_cfg.volatility_sigma * np.sqrt(tau) * np.mean(holding_values)
    
    return {
        "strategy": strategy_name,
        "holdings": holdings,
        "executed_slices": np.array(executed_slices),
        "exec_prices": np.array(exec_prices),
        "mid_prices": np.array(mid_prices),
        "is_maker_list": np.array(is_maker_list),
        "perm_impact_dollars": float(np.sum(step_perm_impacts)),
        "temp_impact_dollars": float(np.sum(step_temp_impacts)),
        "spread_cost_dollars": float(np.sum(step_spread_costs)),
        "tca": tca,
        "var_95_dollars": float(var_95),
        "var_99_dollars": float(var_99)
    }

def run_comparative_execution_benchmark():
    """
    Master runner executing TWAP, VWAP, Static AC, and Neuromorphic Adaptive AC.
    """
    total_shares = 10_000.0
    num_intervals = 30
    tau = 2.0  # 60 seconds total execution
    time_horizon = num_intervals * tau
    p0 = 18500.00
    
    ac_cfg = AlmgrenChrissConfig(
        total_shares=total_shares,
        time_horizon_sec=time_horizon,
        num_intervals=num_intervals,
        risk_aversion_lambda=1e-6,
        volatility_sigma=0.25,
        gamma=2.5e-7,
        eta=5.0e-5,
        alpha=0.5,
        spread=0.25
    )
    optimizer = AlmgrenChrissOptimizer(ac_cfg)
    
    # 1. Generate schedules
    twap_sched = optimizer.calculate_twap_schedule()
    vwap_sched = optimizer.calculate_vwap_schedule()
    ac_sched = optimizer.calculate_optimal_schedule()
    
    # 2. Simulate identical market path with toxic cascade
    time_points, base_mid, price_innovations, neuro_signals = simulate_market_scenario(
        num_intervals=num_intervals, tau=tau, p0=p0, sigma=ac_cfg.volatility_sigma, seed=42
    )
    
    # 3. Execute all 4 strategies
    results = {}
    results["TWAP"] = run_simulation_strategy(
        "Static_TWAP", twap_sched.trades, base_mid, price_innovations, neuro_signals,
        total_shares=total_shares, tau=tau, ac_cfg=ac_cfg
    )
    results["VWAP"] = run_simulation_strategy(
        "Static_VWAP", vwap_sched.trades, base_mid, price_innovations, neuro_signals,
        total_shares=total_shares, tau=tau, ac_cfg=ac_cfg
    )
    results["Static_AC"] = run_simulation_strategy(
        "Static_Almgren_Chriss", ac_sched.trades, base_mid, price_innovations, neuro_signals,
        total_shares=total_shares, tau=tau, ac_cfg=ac_cfg
    )
    results["Neuro_AC"] = run_simulation_strategy(
        "NeuroQuant_Adaptive_AC", None, base_mid, price_innovations, neuro_signals,
        total_shares=total_shares, tau=tau, ac_cfg=ac_cfg
    )
    
    # 4. Print ASCII Comparison Table
    print("\n" + "=" * 98)
    print("      NEUROQUANT-LOB: ALMGREN-CHRISS OPTIMAL EXECUTION & NON-LINEAR IMPACT BENCHMARK")
    print(f"      Initial Shares: {total_shares:,.0f} | Horizon: {time_horizon:.1f}s | Arrival Price: ${p0:,.2f}")
    print("=" * 98)
    header = f"{'Strategy':<22} | {'Avg P_exec':<11} | {'Gross Slip':<11} | {'Fees / Reb':<11} | {'Net IS ($)':<11} | {'Net IS (bps)':<12} | {'Maker %':<7}"
    print(header)
    print("-" * 98)
    
    for key, res in results.items():
        tca = res["tca"]
        strat = res["strategy"]
        avg_p = f"${tca['average_execution_price']:,.2f}"
        slip = f"${tca['gross_slippage_dollars']:,.2f}"
        fees = f"${tca['net_fees_dollars']:+,.2f}"
        net_is = f"${tca['net_shortfall_dollars']:,.2f}"
        net_bps = f"{tca['net_shortfall_bps']:.2f} bps"
        maker = f"{tca['maker_fill_ratio'] * 100:.1f}%"
        print(f"{strat:<22} | {avg_p:<11} | {slip:<11} | {fees:<11} | {net_is:<11} | {net_bps:<12} | {maker:<7}")
        
    print("=" * 98)
    
    # Print Advantage Breakdown
    twap_is = results["TWAP"]["tca"]["net_shortfall_dollars"]
    ac_is = results["Static_AC"]["tca"]["net_shortfall_dollars"]
    neuro_is = results["Neuro_AC"]["tca"]["net_shortfall_dollars"]
    
    twap_saving = twap_is - neuro_is
    twap_saving_pct = (twap_saving / twap_is) * 100.0 if twap_is > 0 else 0.0
    ac_saving = ac_is - neuro_is
    ac_saving_pct = (ac_saving / ac_is) * 100.0 if ac_is > 0 else 0.0
    
    print("\n[*] INSTITUTIONAL EXECUTION SURPLUS HIGHLIGHTS:")
    print(f"  -> NeuroQuant-AC vs Static TWAP:  Saved ${twap_saving:,.2f} ({twap_saving_pct:.1f}% Shortfall Reduction)")
    print(f"  -> NeuroQuant-AC vs Static AC:    Saved ${ac_saving:,.2f} ({ac_saving_pct:.1f}% Shortfall Reduction)")
    print(f"  -> Maker Rebate Harvested:        ${results['Neuro_AC']['tca']['total_maker_rebates_dollars']:,.2f} (-0.002% rebate credit)")
    print(f"  -> Value at Risk (95% VaR):       ${results['Neuro_AC']['var_95_dollars']:,.2f}")
    
    # 5. Generate 6-Panel Publication-Quality Diagnostic Chart (300 DPI)
    plot_path = os.path.join(PROJECT_ROOT, "benchmarks", "execution_benchmark_report.png")
    generate_comparison_chart(results, time_points, plot_path)
    print(f"\n[PASS] Publication 6-Panel Chart saved to: {plot_path}")
    
    # 6. Save JSON Results
    json_path = os.path.join(PROJECT_ROOT, "benchmarks", "execution_benchmark_results.json")
    export_json = {
        "total_shares": total_shares,
        "time_horizon_sec": time_horizon,
        "arrival_price": p0,
        "strategies": {}
    }
    for k, v in results.items():
        export_json["strategies"][k] = {
            "name": v["strategy"],
            "tca": v["tca"],
            "var_95": v["var_95_dollars"],
            "var_99": v["var_99_dollars"],
            "perm_impact": v["perm_impact_dollars"],
            "temp_impact": v["temp_impact_dollars"],
            "spread_cost": v["spread_cost_dollars"]
        }
    with open(json_path, "w") as f:
        json.dump(export_json, f, indent=2)
    print(f"[PASS] JSON benchmark summary saved to: {json_path}\n")
    return results

def generate_comparison_chart(results: dict, time_points: np.ndarray, save_path: str):
    """
    Renders an institutional 6-panel execution performance dashboard.
    """
    fig, axes = plt.subplots(3, 2, figsize=(18, 14), dpi=300)
    plt.subplots_adjust(hspace=0.35, wspace=0.25)
    
    colors = {
        "TWAP": "#e74c3c",      # Red
        "VWAP": "#e67e22",      # Orange
        "Static_AC": "#3498db", # Blue
        "Neuro_AC": "#2ecc71"   # Emerald Green
    }
    
    # Panel 1: Inventory Liquidation Trajectory x(t)
    ax1 = axes[0, 0]
    for k, res in results.items():
        ax1.plot(time_points, res["holdings"], label=res["strategy"].replace("_", " "), 
                 color=colors[k], linewidth=2.4)
    ax1.set_title("Panel 1: Inventory Liquidation Trajectory x(t)", fontsize=12, fontweight="bold")
    ax1.set_xlabel("Time (seconds)")
    ax1.set_ylabel("Remaining Contracts (Shares)")
    ax1.grid(True, linestyle="--", alpha=0.5)
    ax1.legend(loc="upper right", framealpha=0.9)
    
    # Panel 2: Market Mid-Price & Execution Fill Prices Across Flash Crash
    ax2 = axes[0, 1]
    mid_prices = results["Neuro_AC"]["mid_prices"]
    ax2.plot(time_points, mid_prices, label="Prevailing Mid-Price", color="#7f8c8d", linestyle="--", linewidth=1.8)
    for k, res in results.items():
        t_trades = time_points[1:]
        ax2.scatter(t_trades, res["exec_prices"], label=f"{k} Fills", color=colors[k], s=35, alpha=0.85)
    ax2.axvspan(20, 36, color="#e74c3c", alpha=0.15, label="Flash Crash Regime")
    ax2.set_title("Panel 2: Execution Fills & Toxic Flash Crash Window", fontsize=12, fontweight="bold")
    ax2.set_xlabel("Time (seconds)")
    ax2.set_ylabel("Execution Price ($)")
    ax2.grid(True, linestyle="--", alpha=0.5)
    ax2.legend(loc="lower left", fontsize=8, framealpha=0.9)
    
    # Panel 3: Cumulative Implementation Shortfall ($) Over Time
    ax3 = axes[1, 0]
    for k, res in results.items():
        p0 = res["tca"]["arrival_price"]
        cum_qty = np.cumsum(res["executed_slices"])
        cum_realized = np.cumsum(res["executed_slices"] * res["exec_prices"])
        cum_slip = (cum_qty * p0) - cum_realized
        ax3.plot(time_points[1:], cum_slip, label=k, color=colors[k], linewidth=2.2)
    ax3.set_title("Panel 3: Cumulative Gross Slippage ($)", fontsize=12, fontweight="bold")
    ax3.set_xlabel("Time (seconds)")
    ax3.set_ylabel("Cumulative Slippage ($)")
    ax3.grid(True, linestyle="--", alpha=0.5)
    ax3.legend(loc="upper left", framealpha=0.9)
    
    # Panel 4: Trade Size Slices & Maker Routing
    ax4 = axes[1, 1]
    t_mid = time_points[1:] - (time_points[1] - time_points[0]) * 0.5
    width = 0.4
    ax4.bar(t_mid - 0.6, results["TWAP"]["executed_slices"], width=width, label="TWAP", color=colors["TWAP"], alpha=0.6)
    ax4.bar(t_mid - 0.2, results["Static_AC"]["executed_slices"], width=width, label="Static AC", color=colors["Static_AC"], alpha=0.6)
    
    neuro_slices = results["Neuro_AC"]["executed_slices"]
    is_maker = results["Neuro_AC"]["is_maker_list"]
    maker_slices = np.where(is_maker, neuro_slices, 0.0)
    taker_slices = np.where(~is_maker, neuro_slices, 0.0)
    ax4.bar(t_mid + 0.2, taker_slices, width=width, label="Neuro-AC (Taker)", color="#27ae60", alpha=0.8)
    ax4.bar(t_mid + 0.2, maker_slices, width=width, bottom=taker_slices, label="Neuro-AC (Maker Rebate)", color="#f1c40f", alpha=0.9)
    ax4.set_title("Panel 4: Trade Slice Volume & Maker Rebate Capture", fontsize=12, fontweight="bold")
    ax4.set_xlabel("Time (seconds)")
    ax4.set_ylabel("Slice Volume (Shares)")
    ax4.grid(True, linestyle="--", alpha=0.5)
    ax4.legend(loc="upper right", fontsize=8, framealpha=0.9)
    
    # Panel 5: Non-Linear Market Impact Decomposition
    ax5 = axes[2, 0]
    categories = ["TWAP", "VWAP", "Static_AC", "Neuro_AC"]
    perm = [results[k]["perm_impact_dollars"] for k in categories]
    temp = [results[k]["temp_impact_dollars"] for k in categories]
    spread = [results[k]["spread_cost_dollars"] for k in categories]
    
    x_indices = np.arange(len(categories))
    bar_width = 0.55
    ax5.bar(x_indices, spread, width=bar_width, label="Spread Friction (0.5 * spread)", color="#95a5a6")
    ax5.bar(x_indices, perm, width=bar_width, bottom=spread, label="Permanent Impact (gamma * v)", color="#34495e")
    ax5.bar(x_indices, temp, width=bar_width, bottom=np.array(spread) + np.array(perm), 
            label="Non-Linear Temp Impact (eta * v^0.5)", color="#e74c3c")
    ax5.set_xticks(x_indices)
    ax5.set_xticklabels(categories, fontweight="bold")
    ax5.set_title("Panel 5: Market Microstructure Cost Decomposition", fontsize=12, fontweight="bold")
    ax5.set_ylabel("Dollar Friction ($)")
    ax5.grid(True, linestyle="--", alpha=0.5)
    ax5.legend(loc="upper right", framealpha=0.9)
    
    # Panel 6: Total Net Implementation Shortfall (TCA & Exchange Fees)
    ax6 = axes[2, 1]
    net_shortfalls = [results[k]["tca"]["net_shortfall_dollars"] for k in categories]
    net_bps = [results[k]["tca"]["net_shortfall_bps"] for k in categories]
    bar_colors = [colors[k] for k in categories]
    
    bars = ax6.bar(categories, net_shortfalls, width=0.5, color=bar_colors, edgecolor="black", linewidth=1.2)
    for b, bps in zip(bars, net_bps):
        h = b.get_height()
        ax6.text(b.get_x() + b.get_width() / 2.0, h + 30.0, f"${h:,.0f}\n({bps:.1f} bps)", 
                 ha="center", va="bottom", fontsize=9, fontweight="bold")
                 
    ax6.set_ylim(0, max(net_shortfalls) * 1.25)
    ax6.set_title("Panel 6: Total Net Implementation Shortfall (TCA + Fees - Rebates)", fontsize=12, fontweight="bold")
    ax6.set_ylabel("Net Shortfall ($)")
    ax6.grid(True, linestyle="--", alpha=0.5)
    
    plt.suptitle("NeuroQuant-LOB: Almgren-Chriss Optimal Liquidation Benchmark\nNon-Linear Market Impact (eta * v^0.5) & Tiered Exchange Fees (-0.002% Maker Rebate vs +0.005% Taker Fee)",
                 fontsize=14, fontweight="bold", y=0.99)
    plt.savefig(save_path, bbox_inches="tight", dpi=300)
    plt.close()

if __name__ == "__main__":
    run_comparative_execution_benchmark()
