"""Options market making simulator package."""

from .market.quote_engine import QuoteEngine, Quote
from .execution.execution import ExecutionEngine, Order, Fill
from .pricing.black_scholes import call_price_greeks, put_price_greeks
from .risk.inventory import InventoryManager
from .metrics.pnl import PnLManager
from .hedge.delta import compute_net_delta, hedge_quantity_for_underlying
from .experiments.regime import RegimeDetector

__all__ = [
    "QuoteEngine",
    "Quote",
    "ExecutionEngine",
    "Order",
    "Fill",
    "call_price_greeks",
    "put_price_greeks",
    "InventoryManager",
    "PnLManager",
    "compute_net_delta",
    "hedge_quantity_for_underlying",
    "RegimeDetector",
]
