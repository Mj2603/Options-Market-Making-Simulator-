"""Event-driven backtesting with explicit quote/fill event ordering.

The engine is intentionally conservative about what its data can establish:
a trade print crossing a resting quote is treated as a potential fill, scaled
by a configurable participation fraction. This is a transparent sensitivity
model, not a queue-position or exchange-matching-engine simulation.
"""
from dataclasses import dataclass
import math
from typing import Iterable, Literal

from options_mm.market.avellaneda_stoikov import (
    AvellanedaStoikovQuoteModel,
    InventoryAwareQuote,
)
from options_mm.metrics.pnl import PnLManager
from options_mm.risk.inventory import InventoryManager


@dataclass(frozen=True)
class MarketEvent:
    """One ordered market observation and, optionally, one trade print.

    timestamp is seconds since the Unix epoch. price_volatility is annualized
    instrument-price volatility in price units per square-root year.
    aggressor_side describes the incoming trade: a buy aggressor can execute
    against our resting ask; a sell aggressor can execute against our bid.
    """

    timestamp: float
    instrument: str
    fair_value: float
    price_volatility: float
    time_to_horizon: float
    trade_price: float | None = None
    trade_size: float = 0.0
    aggressor_side: Literal["buy", "sell"] | None = None

    def __post_init__(self) -> None:
        numeric = {
            "timestamp": self.timestamp,
            "fair_value": self.fair_value,
            "price_volatility": self.price_volatility,
            "time_to_horizon": self.time_to_horizon,
            "trade_size": self.trade_size,
        }
        for name, value in numeric.items():
            try:
                number = float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{name} must be a finite number") from exc
            if not math.isfinite(number):
                raise ValueError(f"{name} must be a finite number")
            object.__setattr__(self, name, number)

        if not isinstance(self.instrument, str) or not self.instrument.strip():
            raise ValueError("instrument must be a non-empty string")
        if self.fair_value < 0.0:
            raise ValueError("fair_value must be non-negative")
        if self.price_volatility < 0.0:
            raise ValueError("price_volatility must be non-negative")
        if self.time_to_horizon < 0.0:
            raise ValueError("time_to_horizon must be non-negative")
        if self.trade_size < 0.0:
            raise ValueError("trade_size must be non-negative")

        if self.trade_size == 0.0:
            if self.trade_price is not None or self.aggressor_side is not None:
                raise ValueError(
                    "trade_price and aggressor_side require positive trade_size"
                )
        else:
            if self.trade_price is None:
                raise ValueError("trade_price is required for a positive trade_size")
            try:
                trade_price = float(self.trade_price)
            except (TypeError, ValueError) as exc:
                raise ValueError("trade_price must be a finite non-negative number") from exc
            if not math.isfinite(trade_price) or trade_price < 0.0:
                raise ValueError("trade_price must be a finite non-negative number")
            object.__setattr__(self, "trade_price", trade_price)
            if self.aggressor_side not in ("buy", "sell"):
                raise ValueError("aggressor_side must be 'buy' or 'sell'")


@dataclass(frozen=True)
class FillEvent:
    timestamp: float
    instrument: str
    side: Literal["buy", "sell"]
    price: float
    size: float


@dataclass(frozen=True)
class SimulationResult:
    fills: tuple[FillEvent, ...]
    final_quotes: tuple[tuple[str, InventoryAwareQuote], ...]
    final_positions: tuple[tuple[str, float], ...]
    realized_pnl: float
    unrealized_pnl: float
    fees_paid: float
    gross_total_pnl: float
    net_total_pnl: float

    @property
    def total_pnl(self) -> float:
        """Net P&L after commissions."""
        return self.net_total_pnl


class EventDrivenBacktest:
    """Replay ordered trade prints against quotes resting from prior events.

    Event ordering is fixed:
      1. Match the current trade print against the previous resting quote.
      2. Apply the fill to inventory and average-cost P&L.
      3. Recompute and rest quotes using the updated inventory.

    Each event replaces that instrument's previous quote. The fill model
    assumes the configured fraction of displayed trade size is available to
    this simulated market maker. Queue priority, latency, and adverse
    selection are deliberately not inferred from trade prints.
    """

    def __init__(
        self,
        quote_model: AvellanedaStoikovQuoteModel | None = None,
        inventory_manager: InventoryManager | None = None,
        pnl_manager: PnLManager | None = None,
        order_size: float = 10.0,
        participation_rate: float = 0.1,
        quantity_step: float = 1.0,
    ) -> None:
        self.quote_model = quote_model or AvellanedaStoikovQuoteModel()
        self.inventory = inventory_manager or InventoryManager()
        self.pnl = pnl_manager or PnLManager()
        self.order_size = self._positive_finite("order_size", order_size)
        self.participation_rate = self._positive_finite(
            "participation_rate", participation_rate
        )
        self.quantity_step = self._positive_finite("quantity_step", quantity_step)
        if self.participation_rate > 1.0:
            raise ValueError("participation_rate must not exceed 1")
        try:
            max_position = float(self.inventory.max_position)
        except (TypeError, ValueError) as exc:
            raise ValueError("inventory max_position must be finite and positive") from exc
        if not math.isfinite(max_position) or max_position <= 0.0:
            raise ValueError("inventory max_position must be finite and positive")
        self.inventory.max_position = max_position
        for position in self.inventory.positions.values():
            position = float(position)
            if not math.isfinite(position):
                raise ValueError("initial inventory must be finite")
            if abs(position) > max_position:
                raise ValueError("initial inventory exceeds max_position")
        instruments = set(self.inventory.positions) | set(self.pnl.positions)
        for instrument in instruments:
            inventory_quantity = self.inventory.position(instrument)
            pnl_state = self.pnl.positions.get(instrument, {})
            pnl_quantity = float(pnl_state.get("qty", 0.0))
            pnl_average_price = float(pnl_state.get("avg", 0.0))
            if (
                not math.isfinite(pnl_quantity)
                or not math.isfinite(pnl_average_price)
                or not math.isclose(
                    inventory_quantity, pnl_quantity, rel_tol=0.0, abs_tol=1e-9
                )
            ):
                raise ValueError(
                    "initial inventory and PnL positions must be consistent; "
                    "seed both managers with the same fills"
                )
        self._has_run = False

    @staticmethod
    def _positive_finite(name: str, value: float) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be finite and positive") from exc
        if not math.isfinite(number) or number <= 0.0:
            raise ValueError(f"{name} must be finite and positive")
        return number

    def _match(
        self, event: MarketEvent, resting: InventoryAwareQuote
    ) -> FillEvent | None:
        if event.trade_size <= 0.0:
            return None

        if event.aggressor_side == "buy":
            if resting.ask <= 0.0 or event.trade_price < resting.ask:
                return None
            our_side: Literal["buy", "sell"] = "sell"
            fill_price = resting.ask
            inventory_headroom = (
                self.inventory.max_position + self.inventory.position(event.instrument)
            )
        else:
            if resting.bid <= 0.0 or event.trade_price > resting.bid:
                return None
            our_side = "buy"
            fill_price = resting.bid
            inventory_headroom = (
                self.inventory.max_position - self.inventory.position(event.instrument)
            )

        available_trade_size = event.trade_size * self.participation_rate
        maximum_fill = min(
            self.order_size,
            available_trade_size,
            max(0.0, inventory_headroom),
        )
        units = math.floor(maximum_fill / self.quantity_step + 1e-12)
        fill_size = units * self.quantity_step
        if fill_size <= 0.0:
            return None

        signed_size = fill_size if our_side == "buy" else -fill_size
        self.inventory.on_fill(event.instrument, signed_size)
        self.pnl.record_fill(event.instrument, fill_price, signed_size)
        return FillEvent(
            timestamp=event.timestamp,
            instrument=event.instrument,
            side=our_side,
            price=fill_price,
            size=fill_size,
        )

    def run(self, events: Iterable[MarketEvent]) -> SimulationResult:
        """Replay events once; create a fresh engine for each independent run."""
        if self._has_run:
            raise RuntimeError("an EventDrivenBacktest instance can only run once")
        self._has_run = True

        resting_quotes: dict[str, InventoryAwareQuote] = {}
        last_fair_values: dict[str, float] = {}
        fills: list[FillEvent] = []
        previous_timestamp: float | None = None

        for event in events:
            if not isinstance(event, MarketEvent):
                raise TypeError("events must contain MarketEvent instances")
            if (
                previous_timestamp is not None
                and event.timestamp < previous_timestamp
            ):
                raise ValueError("events must be sorted by non-decreasing timestamp")
            previous_timestamp = event.timestamp

            resting = resting_quotes.get(event.instrument)
            if resting is not None:
                fill = self._match(event, resting)
                if fill is not None:
                    fills.append(fill)

            last_fair_values[event.instrument] = event.fair_value
            resting_quotes[event.instrument] = self.quote_model.quote(
                fair_value=event.fair_value,
                inventory=self.inventory.position(event.instrument),
                price_volatility=event.price_volatility,
                time_to_horizon=event.time_to_horizon,
            )

        unmarked_positions = [
            instrument
            for instrument, state in self.pnl.positions.items()
            if float(state.get("qty", 0.0)) != 0.0
            and instrument not in last_fair_values
        ]
        if unmarked_positions:
            raise ValueError(
                "missing final fair value for open positions: "
                + ", ".join(sorted(unmarked_positions))
            )

        unrealized = self.pnl.mark_to_market(last_fair_values)
        return SimulationResult(
            fills=tuple(fills),
            final_quotes=tuple(sorted(resting_quotes.items())),
            final_positions=tuple(sorted(self.inventory.positions.items())),
            realized_pnl=float(self.pnl.realized),
            unrealized_pnl=float(unrealized),
            fees_paid=float(self.pnl.fees_paid),
            gross_total_pnl=float(self.pnl.realized + unrealized),
            net_total_pnl=float(self.pnl.realized + unrealized - self.pnl.fees_paid),
        )
