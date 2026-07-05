from dataclasses import dataclass
from typing import Optional


@dataclass
class Order:
    side: str
    size: float
    limit_price: Optional[float] = None


@dataclass
class Fill:
    price: float
    size: float


class ExecutionEngine:
    """Very small execution model used by tests and the demo.

    Rules (simple):
    - Market buy fills at ask, market sell fills at bid.
    - Limit buy fills if limit >= ask (fill at ask); limit sell fills if limit <= bid
      (fill at bid); otherwise no fill.
    """

    def execute(self, order: Order, bid: float, ask: float) -> Optional[Fill]:
        side = order.side.lower()
        if order.limit_price is None:
            price = ask if side == "buy" else bid
            return Fill(price=price, size=order.size)

        if side == "buy":
            if order.limit_price >= ask:
                return Fill(price=ask, size=order.size)
            return None
        else:
            if order.limit_price <= bid:
                return Fill(price=bid, size=order.size)
            return None
