from dataclasses import dataclass, field
from typing import Dict


@dataclass
class PnLManager:
    """Simple PnL tracker: realized PnL and mark-to-market for open positions.

    Records fills and maintains per-instrument position/average price.
    """

    positions: Dict[str, Dict[str, float]] = field(default_factory=dict)
    realized: float = 0.0

    def record_fill(self, ticker: str, price: float, size: float) -> None:
        state = self.positions.setdefault(ticker, {"qty": 0.0, "avg": 0.0})
        qty = float(state["qty"])
        avg = float(state["avg"])
        size = float(size)

        if qty == 0.0:
            state["qty"] = size
            state["avg"] = price
            return

        if qty * size > 0:
            new_qty = qty + size
            new_avg = (qty * avg + size * price) / new_qty
            state["qty"] = new_qty
            state["avg"] = new_avg
            return

        if abs(size) <= abs(qty):
            closed = abs(size)
            self.realized += closed * (price - avg) * (1.0 if qty > 0 else -1.0)
            state["qty"] = qty + size
            if state["qty"] == 0:
                state["avg"] = 0.0
            return

        closed = abs(qty)
        self.realized += closed * (price - avg) * (1.0 if qty > 0 else -1.0)
        remaining = size + qty
        state["qty"] = remaining
        state["avg"] = price

    def mark_to_market(self, price_map: Dict[str, float]) -> float:
        mtm = 0.0
        for ticker, state in self.positions.items():
            qty = state.get("qty", 0.0)
            avg = state.get("avg", 0.0)
            if qty == 0.0:
                continue
            market_price = price_map.get(ticker)
            if market_price is None:
                continue
            mtm += qty * (market_price - avg)
        return mtm

    def total_unrealized_plus_realized(self, price_map: Dict[str, float]) -> float:
        return self.realized + self.mark_to_market(price_map)
