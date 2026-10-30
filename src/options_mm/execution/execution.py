from dataclasses import dataclass
import math
from typing import Optional


@dataclass(frozen=True)
class Order:
    side: str
    size: float
    limit_price: Optional[float] = None


@dataclass(frozen=True)
class Fill:
    price: float
    size: float


class ExecutionEngine:
    """Top-of-book execution baseline with no queue or partial-fill model.

    Market buys execute at the ask and market sells at the bid. Marketable
    limit orders execute at the touch price when that price respects the
    order's limit. Inputs are validated, but liquidity and displayed size are
    not modeled.
    """

    def execute(self, order: Order, bid: float, ask: float) -> Optional[Fill]:
        side = order.side.lower() if isinstance(order.side, str) else ""
        if side not in {"buy", "sell"}:
            raise ValueError("side must be 'buy' or 'sell'")
        if not math.isfinite(order.size) or order.size <= 0:
            raise ValueError("order size must be finite and positive")
        if not math.isfinite(bid) or not math.isfinite(ask) or bid < 0 or ask < bid:
            raise ValueError("quotes must be finite, non-negative, and non-crossed")
        if order.limit_price is not None and (
            not math.isfinite(order.limit_price) or order.limit_price < 0
        ):
            raise ValueError("limit_price must be finite and non-negative")

        if order.limit_price is None:
            price = ask if side == "buy" else bid
            return Fill(price=price, size=order.size)

        if side == "buy" and order.limit_price >= ask:
            return Fill(price=ask, size=order.size)
        if side == "sell" and order.limit_price <= bid:
            return Fill(price=bid, size=order.size)
        return None
