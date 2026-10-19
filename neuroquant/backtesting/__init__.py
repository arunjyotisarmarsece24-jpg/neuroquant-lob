"""
NeuroQuant-LOB Backtesting Subsystem
===================================
Institutional Purged & Embargoed Cross-Validation (PE-CV) and
Deflated Sharpe Ratio (DSR) analytics for microsecond LOB execution.

Author: Arunjyoti Sarma (Research Scholar, IIT (BHU), Varanasi)
"""

from neuroquant.backtesting.walk_forward import (
    PurgedKFold,
    WalkForwardBacktester,
    BacktestResult,
    FoldPerformance,
    compute_deflated_sharpe_ratio,
    compute_probabilistic_sharpe_ratio
)

__all__ = [
    "PurgedKFold",
    "WalkForwardBacktester",
    "BacktestResult",
    "FoldPerformance",
    "compute_deflated_sharpe_ratio",
    "compute_probabilistic_sharpe_ratio"
]
