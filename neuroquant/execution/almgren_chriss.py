"""
Almgren-Chriss Optimal Execution Engine
=======================================
Implements the institutional Almgren & Chriss (2000) optimal liquidation framework:
  1. Discrete Euler-Lagrange optimization for optimal liquidation trajectory:
       x_j = X_0 * sinh(kappa * (T - j * tau)) / sinh(kappa * T)
       n_j = 2 * X_0 * sinh(0.5 * kappa * tau) / sinh(kappa * T) * cosh(kappa * (T - (j - 0.5) * tau))
  2. Exact discrete and continuous urgency decay parameter:
       kappa = (1 / tau) * arccosh(1 + 0.5 * lambda * sigma^2 * tau^2 / eta_tilde)
  3. Half-life of liquidation: t_half = ln(2) / kappa
  4. Expected Shortfall E[x], Variance V[x], and Utility U(x) = E[x] + lambda * V[x]
  5. Non-Linear Market Impact Trajectory Optimization (Euler-Lagrange / SLSQP with alpha = 0.5)
  6. Standard Benchmarks: TWAP (Time-Weighted) and VWAP (Volume-Weighted) schedules

References:
  - Almgren, R., & Chriss, N. (2000). Optimal execution of portfolio transactions.
    Journal of Risk, 3(2), 5-40.
  - Almgren, R. (2003). Optimal execution with nonlinear impact functions and trading-enhanced risk.
    Applied Mathematical Finance, 10(1), 1-18.
"""

import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from scipy.optimize import minimize

@dataclass
class AlmgrenChrissConfig:
    total_shares: float = 10_000.0   # Total inventory to liquidate (X_0)
    time_horizon_sec: float = 60.0   # Total execution time horizon (T)
    num_intervals: int = 20          # Number of discrete trading periods (N)
    risk_aversion_lambda: float = 1e-4 # Trader risk aversion coefficient (lambda)
    volatility_sigma: float = 0.20   # Price volatility ($ / sqrt(sec) or annual converted)
    gamma: float = 2.5e-7            # Permanent price impact parameter
    eta: float = 5.0e-5              # Temporary price impact parameter
    alpha: float = 0.5               # Temporary impact exponent (0.5 for square-root law)
    spread: float = 0.25             # Prevailing bid-ask spread ($)

@dataclass
class LiquidationSchedule:
    time_points: np.ndarray          # [t_0, t_1, ..., t_N]
    holdings: np.ndarray             # [x_0, x_1, ..., x_N]
    trades: np.ndarray               # [n_1, n_2, ..., n_N]
    trade_rates: np.ndarray          # [v_1, v_2, ..., v_N] (shares/sec)
    kappa: float                     # Urgency parameter (1/sec)
    half_life_sec: float             # Time in seconds to liquidate 50% of position
    expected_shortfall: float        # Expected total execution cost ($)
    variance_shortfall: float        # Variance of execution cost ($^2)
    utility: float                   # Objective function E[x] + lambda * V[x]

class AlmgrenChrissOptimizer:
    """
    Computes closed-form and non-linear numerical optimal execution schedules.
    """
    def __init__(self, config: Optional[AlmgrenChrissConfig] = None):
        self.config = config or AlmgrenChrissConfig()

    def compute_kappa(self, lambda_val: Optional[float] = None) -> Tuple[float, float]:
        """
        Calculates the discrete urgency parameter kappa (1/sec) and adjusted eta.
        
        Discrete Euler-Lagrange condition:
          cosh(kappa * tau) = 1 + 0.5 * lambda * sigma^2 * tau^2 / eta_tilde
        """
        cfg = self.config
        lam = lambda_val if lambda_val is not None else cfg.risk_aversion_lambda
        N = cfg.num_intervals
        T = cfg.time_horizon_sec
        tau = T / N

        # Effective temporary impact adjusted for permanent impact during interval
        eta_tilde = cfg.eta * (1.0 - 0.5 * (cfg.gamma * tau / cfg.eta))
        if eta_tilde <= 0 or not np.isfinite(eta_tilde):
            eta_tilde = cfg.eta

        if lam <= 0 or cfg.volatility_sigma <= 0:
            return 0.0, eta_tilde

        # Argument for arccosh: 1 + 0.5 * lambda * sigma^2 * tau^2 / eta_tilde
        arg = 1.0 + 0.5 * lam * (cfg.volatility_sigma ** 2) * (tau ** 2) / eta_tilde
        
        # When arg is very close to 1, use continuous approximation sqrt(lambda * sigma^2 / eta)
        if arg <= 1.0 + 1e-12:
            kappa = np.sqrt(lam * (cfg.volatility_sigma ** 2) / eta_tilde)
        else:
            kappa = (1.0 / tau) * np.arccosh(arg)

        return float(kappa), float(eta_tilde)

    def calculate_optimal_schedule(self, 
                                   initial_shares: Optional[float] = None,
                                   lambda_val: Optional[float] = None) -> LiquidationSchedule:
        """
        Computes the exact discrete Almgren-Chriss optimal liquidation schedule.
        
        Holdings:
          x_j = X_0 * sinh(kappa * (T - j * tau)) / sinh(kappa * T)
          
        Trade size in interval j:
          n_j = 2 * X_0 * sinh(0.5 * kappa * tau) / sinh(kappa * T) * cosh(kappa * (T - (j - 0.5) * tau))
        """
        cfg = self.config
        X_0 = initial_shares if initial_shares is not None else cfg.total_shares
        lam = lambda_val if lambda_val is not None else cfg.risk_aversion_lambda
        N = cfg.num_intervals
        T = cfg.time_horizon_sec
        tau = T / N

        time_points = np.linspace(0.0, T, N + 1)
        kappa, eta_tilde = self.compute_kappa(lam)

        # Handle risk-neutral limit (kappa -> 0): linear TWAP
        if kappa < 1e-9:
            holdings = np.array([X_0 * (1.0 - (j / N)) for j in range(N + 1)])
            trades = np.full(N, X_0 / N)
            half_life = T * 0.5
        else:
            sinh_kappa_T = np.sinh(kappa * T)
            # Avoid numerical overflow for large kappa * T
            if not np.isfinite(sinh_kappa_T) or sinh_kappa_T == 0:
                # Asymptotic exponential decay
                holdings = X_0 * np.exp(-kappa * time_points)
                holdings[-1] = 0.0
                trades = holdings[:-1] - holdings[1:]
            else:
                holdings = np.zeros(N + 1)
                for j in range(N + 1):
                    holdings[j] = X_0 * np.sinh(kappa * (T - j * tau)) / sinh_kappa_T
                holdings[-1] = 0.0  # Boundary condition x_N = 0 strictly enforced

                trades = np.zeros(N)
                for j in range(1, N + 1):
                    # Exact discrete formula from Step 5.1
                    term_sinh = np.sinh(0.5 * kappa * tau)
                    term_cosh = np.cosh(kappa * (T - (j - 0.5) * tau))
                    trades[j - 1] = 2.0 * X_0 * (term_sinh / sinh_kappa_T) * term_cosh

            half_life = np.log(2.0) / kappa if kappa > 0 else (T * 0.5)

        # Normalize trades to guarantee strict conservation of initial shares
        total_trade_sum = np.sum(trades)
        if total_trade_sum > 0:
            trades = trades * (X_0 / total_trade_sum)
            # Recompute exact holdings from trades to guarantee bit-level consistency
            holdings = np.zeros(N + 1)
            holdings[0] = X_0
            for j in range(1, N + 1):
                holdings[j] = holdings[j - 1] - trades[j - 1]
            holdings[-1] = 0.0

        trade_rates = trades / tau

        # Compute Expected Shortfall E[x] and Variance V[x]
        half_spread = 0.5 * cfg.spread
        perm_cost = 0.5 * cfg.gamma * (X_0 ** 2)
        spread_cost = half_spread * X_0
        temp_cost = eta_tilde * np.sum((trades ** 2) / tau)
        expected_shortfall = perm_cost + spread_cost + temp_cost

        # Variance of shortfall: sigma^2 * tau * sum(x_j^2)
        variance_shortfall = (cfg.volatility_sigma ** 2) * tau * np.sum(holdings[1:] ** 2)
        utility = expected_shortfall + lam * variance_shortfall

        return LiquidationSchedule(
            time_points=time_points,
            holdings=holdings,
            trades=trades,
            trade_rates=trade_rates,
            kappa=float(kappa),
            half_life_sec=float(half_life),
            expected_shortfall=float(expected_shortfall),
            variance_shortfall=float(variance_shortfall),
            utility=float(utility)
        )

    def calculate_twap_schedule(self, initial_shares: Optional[float] = None) -> LiquidationSchedule:
        """
        Time-Weighted Average Price (TWAP): Constant trade sizes n_j = X_0 / N.
        """
        cfg = self.config
        X_0 = initial_shares if initial_shares is not None else cfg.total_shares
        N = cfg.num_intervals
        T = cfg.time_horizon_sec
        tau = T / N

        time_points = np.linspace(0.0, T, N + 1)
        trades = np.full(N, X_0 / N)
        holdings = np.zeros(N + 1)
        holdings[0] = X_0
        for j in range(1, N + 1):
            holdings[j] = holdings[j - 1] - trades[j - 1]
        holdings[-1] = 0.0

        trade_rates = trades / tau
        half_spread = 0.5 * cfg.spread
        perm_cost = 0.5 * cfg.gamma * (X_0 ** 2)
        spread_cost = half_spread * X_0
        temp_cost = cfg.eta * np.sum((trades ** 2) / tau)
        expected_shortfall = perm_cost + spread_cost + temp_cost
        variance_shortfall = (cfg.volatility_sigma ** 2) * tau * np.sum(holdings[1:] ** 2)
        utility = expected_shortfall + cfg.risk_aversion_lambda * variance_shortfall

        return LiquidationSchedule(
            time_points=time_points,
            holdings=holdings,
            trades=trades,
            trade_rates=trade_rates,
            kappa=0.0,
            half_life_sec=float(T * 0.5),
            expected_shortfall=float(expected_shortfall),
            variance_shortfall=float(variance_shortfall),
            utility=float(utility)
        )

    def calculate_vwap_schedule(self, 
                                initial_shares: Optional[float] = None, 
                                volume_weights: Optional[np.ndarray] = None) -> LiquidationSchedule:
        """
        Volume-Weighted Average Price (VWAP): Trades proportioned to market volume profile.
        Defaults to empirical institutional U-shaped intraday volume smile.
        """
        cfg = self.config
        X_0 = initial_shares if initial_shares is not None else cfg.total_shares
        N = cfg.num_intervals
        T = cfg.time_horizon_sec
        tau = T / N

        time_points = np.linspace(0.0, T, N + 1)

        if volume_weights is None:
            # Generate institutional U-shaped smile: higher at open & close, lower at midpoint
            norm_t = np.linspace(-1.0, 1.0, N)
            u_curve = 1.0 + 1.8 * (norm_t ** 2)
            volume_weights = u_curve / np.sum(u_curve)
        else:
            volume_weights = np.asarray(volume_weights) / np.sum(volume_weights)

        trades = X_0 * volume_weights
        holdings = np.zeros(N + 1)
        holdings[0] = X_0
        for j in range(1, N + 1):
            holdings[j] = holdings[j - 1] - trades[j - 1]
        holdings[-1] = 0.0

        trade_rates = trades / tau
        half_spread = 0.5 * cfg.spread
        perm_cost = 0.5 * cfg.gamma * (X_0 ** 2)
        spread_cost = half_spread * X_0
        temp_cost = cfg.eta * np.sum((trades ** 2) / tau)
        expected_shortfall = perm_cost + spread_cost + temp_cost
        variance_shortfall = (cfg.volatility_sigma ** 2) * tau * np.sum(holdings[1:] ** 2)
        utility = expected_shortfall + cfg.risk_aversion_lambda * variance_shortfall

        # Effective half-life (when holdings cross 50%)
        idx_half = np.where(holdings <= 0.5 * X_0)[0]
        half_life = float(time_points[idx_half[0]]) if len(idx_half) > 0 else (T * 0.5)

        return LiquidationSchedule(
            time_points=time_points,
            holdings=holdings,
            trades=trades,
            trade_rates=trade_rates,
            kappa=0.0,
            half_life_sec=float(half_life),
            expected_shortfall=float(expected_shortfall),
            variance_shortfall=float(variance_shortfall),
            utility=float(utility)
        )

    def calculate_nonlinear_schedule(self, 
                                     initial_shares: Optional[float] = None,
                                     alpha: Optional[float] = None,
                                     lambda_val: Optional[float] = None) -> LiquidationSchedule:
        """
        Solves for the optimal liquidation schedule under non-linear square-root market impact:
          Cost_temp = eta * sum( n_j * (n_j / tau)^alpha ) = (eta / tau^alpha) * sum( n_j^(1+alpha) )
        
        Solved numerically via constrained optimization (SLSQP), initialized with linear AC schedule.
        """
        cfg = self.config
        X_0 = initial_shares if initial_shares is not None else cfg.total_shares
        lam = lambda_val if lambda_val is not None else cfg.risk_aversion_lambda
        impact_power = alpha if alpha is not None else cfg.alpha
        N = cfg.num_intervals
        T = cfg.time_horizon_sec
        tau = T / N
        time_points = np.linspace(0.0, T, N + 1)

        # Initial guess: linear Almgren-Chriss schedule
        init_ac = self.calculate_optimal_schedule(X_0, lam)
        x0_guess = init_ac.trades

        # Objective function: Total Expected Shortfall + lambda * Variance
        def objective(n_vec):
            # Holdings
            h = np.zeros(N + 1)
            h[0] = X_0
            for j in range(1, N + 1):
                h[j] = h[j - 1] - n_vec[j - 1]
            h[-1] = 0.0

            # Permanent cost
            perm = 0.5 * cfg.gamma * (X_0 ** 2)
            # Spread cost
            spread = 0.5 * cfg.spread * X_0
            # Non-linear temporary cost: (eta / tau^alpha) * sum(n^(1+alpha))
            # Protect against negative entries with abs
            temp = (cfg.eta / (tau ** impact_power)) * np.sum(np.abs(n_vec) ** (1.0 + impact_power))
            e_shortfall = perm + spread + temp
            # Variance
            var_shortfall = (cfg.volatility_sigma ** 2) * tau * np.sum(h[1:] ** 2)
            return e_shortfall + lam * var_shortfall

        # Constraints & bounds: sum(n_j) == X_0 and n_j >= 0
        constraints = ({'type': 'eq', 'fun': lambda n: np.sum(n) - X_0})
        bounds = [(0.0, X_0) for _ in range(N)]

        res = minimize(objective, x0_guess, method='SLSQP', bounds=bounds, constraints=constraints,
                       options={'maxiter': 300, 'ftol': 1e-9})
        
        trades = res.x if res.success else x0_guess
        # Strict normalization
        trades = trades * (X_0 / np.sum(trades))
        
        holdings = np.zeros(N + 1)
        holdings[0] = X_0
        for j in range(1, N + 1):
            holdings[j] = holdings[j - 1] - trades[j - 1]
        holdings[-1] = 0.0

        trade_rates = trades / tau
        half_spread = 0.5 * cfg.spread
        perm_cost = 0.5 * cfg.gamma * (X_0 ** 2)
        spread_cost = half_spread * X_0
        temp_cost = (cfg.eta / (tau ** impact_power)) * np.sum(np.abs(trades) ** (1.0 + impact_power))
        expected_shortfall = perm_cost + spread_cost + temp_cost
        variance_shortfall = (cfg.volatility_sigma ** 2) * tau * np.sum(holdings[1:] ** 2)
        utility = expected_shortfall + lam * variance_shortfall

        idx_half = np.where(holdings <= 0.5 * X_0)[0]
        half_life = float(time_points[idx_half[0]]) if len(idx_half) > 0 else (T * 0.5)

        return LiquidationSchedule(
            time_points=time_points,
            holdings=holdings,
            trades=trades,
            trade_rates=trade_rates,
            kappa=init_ac.kappa,
            half_life_sec=float(half_life),
            expected_shortfall=float(expected_shortfall),
            variance_shortfall=float(variance_shortfall),
            utility=float(utility)
        )
