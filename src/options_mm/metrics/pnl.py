"""Average-cost P&L with configurable contract multipliers and commissions."""
from dataclasses import dataclass, field
import math
from typing import Dict


@dataclass
class PnLManager:
    """Track gross realized/unrealized P&L and explicit transaction fees.

    Contract multipliers default to 1.0. Commission is charged per traded
    unit/contract on every fill and is kept separate from gross realized P&L.
    Net P&L is gross realized plus unrealized P&L less cumulative commissions.
    """

    positions: Dict[str, Dict[str, float]] = field(default_factory=dict)
    realized: float = 0.0
    commission_per_contract: float = 0.0
    contract_multipliers: Dict[str, float] = field(default_factory=dict)
    fees_paid: float = 0.0

    def __post_init__(self) -> None:
        self.commission_per_contract = self._finite_number(
            "commission_per_contract", self.commission_per_contract
        )
        self.fees_paid = self._finite_number("fees_paid", self.fees_paid)
        self.realized = self._finite_number("realized", self.realized)
        if self.commission_per_contract < 0.0:
            raise ValueError("commission_per_contract must be non-negative")
        if self.fees_paid < 0.0:
            raise ValueError("fees_paid must be non-negative")

        normalized_multipliers = {}
        for ticker, multiplier in self.contract_multipliers.items():
            if not isinstance(ticker, str) or not ticker.strip():
                raise ValueError("contract multiplier keys must be non-empty strings")
            multiplier = self._finite_number(
                f"contract multiplier for {ticker}", multiplier
            )
            if multiplier <= 0.0:
                raise ValueError("contract multipliers must be strictly positive")
            normalized_multipliers[ticker] = multiplier
        self.contract_multipliers = normalized_multipliers

        normalized_positions = {}
        for ticker, state in self.positions.items():
            if not isinstance(ticker, str) or not ticker.strip():
                raise ValueError("position keys must be non-empty strings")
            qty = self._finite_number("position quantity", state.get("qty", 0.0))
            avg = self._finite_number("average price", state.get("avg", 0.0))
            if avg < 0.0:
                raise ValueError("average prices must be non-negative")
            normalized_positions[ticker] = {"qty": qty, "avg": avg}
        self.positions = normalized_positions

    @staticmethod
    def _finite_number(name: str, value: float) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be finite") from exc
        if not math.isfinite(number):
            raise ValueError(f"{name} must be finite")
        return number

    def _multiplier(self, ticker: str) -> float:
        return self.contract_multipliers.get(ticker, 1.0)

    def record_fill(self, ticker: str, price: float, size: float) -> None:
        if not isinstance(ticker, str) or not ticker.strip():
            raise ValueError("ticker must be a non-empty string")
        price = self._finite_number("price", price)
        size = self._finite_number("size", size)
        if price < 0.0:
            raise ValueError("price must be non-negative")
        if size == 0.0:
            raise ValueError("fill size must be non-zero")

        multiplier = self._multiplier(ticker)
        state = self.positions.get(ticker, {"qty": 0.0, "avg": 0.0})
        qty = self._finite_number("position quantity", state["qty"])
        avg = self._finite_number("average price", state["avg"])
        fee_increment = abs(size) * self.commission_per_contract
        updated_fees = self.fees_paid + fee_increment
        if not math.isfinite(updated_fees):
            raise ValueError("fill produces non-finite cumulative fees")

        if qty == 0.0:
            self.positions[ticker] = {"qty": size, "avg": price}
            self.fees_paid = updated_fees
            return

        if qty * size > 0.0:
            new_qty = qty + size
            new_avg = (abs(qty) * avg + abs(size) * price) / abs(new_qty)
            if not math.isfinite(new_qty) or not math.isfinite(new_avg):
                raise ValueError("fill produces non-finite position state")
            self.positions[ticker] = {"qty": new_qty, "avg": new_avg}
            self.fees_paid = updated_fees
            return

        closed = min(abs(size), abs(qty))
        realized_increment = (
            closed * (price - avg) * (1.0 if qty > 0.0 else -1.0) * multiplier
        )
        updated_realized = self.realized + realized_increment
        if not math.isfinite(updated_realized):
            raise ValueError("fill produces non-finite realized P&L")

        if abs(size) <= abs(qty):
            new_qty = qty + size
            new_avg = 0.0 if new_qty == 0.0 else avg
        else:
            new_qty = qty + size
            new_avg = price
        if not math.isfinite(new_qty) or not math.isfinite(new_avg):
            raise ValueError("fill produces non-finite position state")

        self.positions[ticker] = {"qty": new_qty, "avg": new_avg}
        self.realized = updated_realized
        self.fees_paid = updated_fees

    def mark_to_market(self, price_map: Dict[str, float]) -> float:
        mtm = 0.0
        for ticker, state in self.positions.items():
            qty = self._finite_number("position quantity", state.get("qty", 0.0))
            avg = self._finite_number("average price", state.get("avg", 0.0))
            if qty == 0.0:
                continue
            market_price = price_map.get(ticker)
            if market_price is None:
                continue
            market_price = self._finite_number(
                f"mark price for {ticker}", market_price
            )
            if market_price < 0.0:
                raise ValueError("mark prices must be non-negative")
            mtm += qty * (market_price - avg) * self._multiplier(ticker)
            if not math.isfinite(mtm):
                raise ValueError("marks produce non-finite unrealized P&L")
        return mtm

    def total_unrealized_plus_realized(self, price_map: Dict[str, float]) -> float:
        """Return gross P&L before commissions."""
        return self.realized + self.mark_to_market(price_map)

    def net_total_pnl(self, price_map: Dict[str, float]) -> float:
        """Return gross P&L after subtracting cumulative commissions."""
        return self.total_unrealized_plus_realized(price_map) - self.fees_paid
