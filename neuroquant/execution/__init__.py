"""
NeuroQuant Execution Package
============================
Optimal execution algorithms, non-linear market impact modeling,
tiered exchange fee accounting, and neuromorphic adaptive urgency controllers.
"""

from .market_impact import (
    NonLinearMarketImpactEngine,
    MarketImpactConfig
)
from .fee_model import (
    TieredExchangeFeeModel,
    FeeModelConfig,
    ExecutionFillRecord
)
from .almgren_chriss import (
    AlmgrenChrissOptimizer,
    AlmgrenChrissConfig,
    LiquidationSchedule
)
from .adaptive_execution import (
    NeuromorphicAdaptiveExecutionEngine,
    AdaptiveUrgencyConfig
)

__all__ = [
    "NonLinearMarketImpactEngine",
    "MarketImpactConfig",
    "TieredExchangeFeeModel",
    "FeeModelConfig",
    "ExecutionFillRecord",
    "AlmgrenChrissOptimizer",
    "AlmgrenChrissConfig",
    "LiquidationSchedule",
    "NeuromorphicAdaptiveExecutionEngine",
    "AdaptiveUrgencyConfig",
]
