"""Event-driven backtesting with explicit quote/fill event ordering.

The engine is intentionally conservative about what its data can establish:
a trade print crossing a resting quote is treated as a potential fill, scaled
by a configurable participation fraction. This is a transparent sensitivity
model, not a queue-position or exchange-matching-engine simulation.
"""
from dataclasses import dataclass
import copy
import math
from typing import Iterable, Literal

from options_mm.execution.queue import L1QueueModel, QueuePosition
from options_mm.risk.portfolio import OptionRiskPosition

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
    market_bid: float | None = None
    market_ask: float | None = None
    market_bid_size: float = 0.0
    market_ask_size: float = 0.0
    underlying: str | None = None
    delta: float | None = None
    gamma: float | None = None
    vega: float | None = None
    theta: float | None = None
    contract_multiplier: float = 1.0

    def __post_init__(self) -> None:
        numeric = {
            "timestamp": self.timestamp,
            "fair_value": self.fair_value,
            "price_volatility": self.price_volatility,
            "time_to_horizon": self.time_to_horizon,
            "trade_size": self.trade_size,
            "market_bid_size": self.market_bid_size,
            "market_ask_size": self.market_ask_size,
            "contract_multiplier": self.contract_multiplier,
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
        if self.market_bid_size < 0.0 or self.market_ask_size < 0.0:
            raise ValueError("market quote sizes must be non-negative")
        if self.contract_multiplier <= 0.0:
            raise ValueError("contract_multiplier must be positive")
        if (self.market_bid is None) != (self.market_ask is None):
            raise ValueError("market_bid and market_ask must be supplied together")
        if self.market_bid is not None:
            for name in ("market_bid", "market_ask"):
                value = float(getattr(self, name))
                if not math.isfinite(value) or value < 0.0:
                    raise ValueError(f"{name} must be finite and non-negative")
                object.__setattr__(self, name, value)
            if self.market_ask < self.market_bid:
                raise ValueError("market quote must not be crossed")
        for name in ("delta", "gamma", "vega", "theta"):
            value = getattr(self, name)
            if value is not None:
                try:
                    number = float(value)
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"{name} must be finite") from exc
                if not math.isfinite(number):
                    raise ValueError(f"{name} must be finite")
                object.__setattr__(self, name, number)
        if self.underlying is not None and not str(self.underlying).strip():
            raise ValueError("underlying must be non-empty when supplied")

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
class EquityPoint:
    timestamp: float
    realized_pnl: float
    unrealized_pnl: float
    fees_paid: float
    net_pnl: float


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
    equity_curve: tuple[EquityPoint, ...] = ()

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
        queue_model: L1QueueModel | None = None,
        portfolio_risk_manager=None,
        initial_risk_positions: Iterable[OptionRiskPosition] = (),
    ) -> None:
        self.quote_model = quote_model or AvellanedaStoikovQuoteModel()
        self.inventory = inventory_manager or InventoryManager()
        self.pnl = pnl_manager or PnLManager()
        self.order_size = self._positive_finite("order_size", order_size)
        self.participation_rate = self._positive_finite(
            "participation_rate", participation_rate
        )
        self.quantity_step = self._positive_finite("quantity_step", quantity_step)
        self.queue_model = queue_model
        self.portfolio_risk_manager = portfolio_risk_manager
        initial_risk_positions = list(initial_risk_positions)
        self._risk_positions = {
            item.instrument: item for item in initial_risk_positions
        }
        if len(self._risk_positions) != len(initial_risk_positions):
            raise ValueError("initial risk positions must have unique instruments")
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

    def _approve_portfolio_risk(
        self, event: MarketEvent, signed_size: float
    ) -> bool:
        if self.portfolio_risk_manager is None:
            return True
        if (
            event.underlying is None
            or any(value is None for value in (event.delta, event.gamma, event.vega, event.theta))
        ):
            raise ValueError(
                "portfolio risk control requires underlying and delta/gamma/vega/theta on every fill event"
            )
        proposed = OptionRiskPosition(
            instrument=event.instrument,
            underlying=event.underlying,
            quantity=signed_size,
            multiplier=event.contract_multiplier,
            delta=event.delta,
            gamma=event.gamma,
            vega=event.vega,
            theta=event.theta,
            market_value=event.fair_value,
        )
        decision = self.portfolio_risk_manager.pre_trade_check(
            self._risk_positions.values(), proposed
        )
        if not decision.approved:
            return False
        previous = self._risk_positions.get(event.instrument)
        quantity = signed_size + (previous.quantity if previous else 0.0)
        self._risk_positions[event.instrument] = OptionRiskPosition(
            instrument=event.instrument,
            underlying=event.underlying,
            quantity=quantity,
            multiplier=event.contract_multiplier,
            delta=event.delta,
            gamma=event.gamma,
            vega=event.vega,
            theta=event.theta,
            market_value=event.fair_value,
        )
        return True

    def _match(
        self,
        event: MarketEvent,
        resting: InventoryAwareQuote,
        queue_positions: dict[str, QueuePosition] | None = None,
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

        maximum_fill = min(
            self.order_size,
            event.trade_size * self.participation_rate,
            max(0.0, inventory_headroom),
        )
        queue_trial = None
        if self.queue_model is not None:
            if queue_positions is None or our_side not in queue_positions:
                return None
            queue_trial = copy.deepcopy(queue_positions[our_side])
            queue_result = self.queue_model.process_trade(
                queue_trial,
                timestamp=event.timestamp,
                trade_price=event.trade_price,
                trade_size=event.trade_size,
                aggressor_side=event.aggressor_side,
                order_side=our_side,
                participation_rate=self.participation_rate,
                max_fill_size=max(0.0, inventory_headroom),
            )
            maximum_fill = min(maximum_fill, queue_result.filled_size)
        units = math.floor(maximum_fill / self.quantity_step + 1e-12)
        fill_size = units * self.quantity_step
        if fill_size <= 0.0:
            if queue_trial is not None:
                # Queue ahead is consumed by public volume even when no full lot fills.
                queue_positions[our_side] = queue_trial
            return None

        signed_size = fill_size if our_side == "buy" else -fill_size
        if not self._approve_portfolio_risk(event, signed_size):
            return None
        if queue_trial is not None:
            queue_trial.remaining_size += maximum_fill - fill_size
            queue_positions[our_side] = queue_trial
        existing_multiplier = self.pnl.contract_multipliers.get(event.instrument)
        if existing_multiplier is not None and not math.isclose(
            existing_multiplier, event.contract_multiplier, rel_tol=0.0, abs_tol=1e-12
        ):
            raise ValueError("event contract multiplier conflicts with PnL configuration")
        self.pnl.contract_multipliers.setdefault(
            event.instrument, event.contract_multiplier
        )
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
        queue_positions: dict[str, dict[str, QueuePosition]] = {}
        last_fair_values: dict[str, float] = {}
        fills: list[FillEvent] = []
        equity_curve: list[EquityPoint] = []
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

            if self.portfolio_risk_manager is not None:
                current_risk = self._risk_positions.get(event.instrument)
                if current_risk is not None and all(
                    value is not None
                    for value in (event.delta, event.gamma, event.vega, event.theta)
                ):
                    self._risk_positions[event.instrument] = OptionRiskPosition(
                        instrument=event.instrument,
                        underlying=event.underlying or current_risk.underlying,
                        quantity=current_risk.quantity,
                        multiplier=event.contract_multiplier,
                        delta=event.delta,
                        gamma=event.gamma,
                        vega=event.vega,
                        theta=event.theta,
                        market_value=event.fair_value,
                    )

            previous_quote = resting_quotes.get(event.instrument)
            resting = previous_quote
            if resting is not None:
                fill = self._match(
                    event,
                    resting,
                    queue_positions.get(event.instrument),
                )
                if fill is not None:
                    fills.append(fill)

            last_fair_values[event.instrument] = event.fair_value
            resting_quotes[event.instrument] = self.quote_model.quote(
                fair_value=event.fair_value,
                inventory=self.inventory.position(event.instrument),
                price_volatility=event.price_volatility,
                time_to_horizon=event.time_to_horizon,
            )
            if self.queue_model is not None and (
                previous_quote is None
                or not math.isclose(
                    previous_quote.bid, resting_quotes[event.instrument].bid,
                    rel_tol=0.0, abs_tol=1e-12
                )
                or not math.isclose(
                    previous_quote.ask, resting_quotes[event.instrument].ask,
                    rel_tol=0.0, abs_tol=1e-12
                )
            ):
                if event.market_bid is None or event.market_ask is None:
                    raise ValueError(
                        "queue-aware simulation requires market_bid and market_ask on every event"
                    )
                quote = resting_quotes[event.instrument]
                bid_queue = (
                    event.market_bid_size
                    if math.isclose(quote.bid, event.market_bid, abs_tol=1e-8)
                    else 0.0 if quote.bid > event.market_bid else 1e30
                )
                ask_queue = (
                    event.market_ask_size
                    if math.isclose(quote.ask, event.market_ask, abs_tol=1e-8)
                    else 0.0 if quote.ask < event.market_ask else 1e30
                )
                queue_positions[event.instrument] = {
                    "buy": self.queue_model.place(
                        event.timestamp, quote.bid, bid_queue, self.order_size
                    ),
                    "sell": self.queue_model.place(
                        event.timestamp, quote.ask, ask_queue, self.order_size
                    ),
                }
            unrealized_now = self.pnl.mark_to_market(last_fair_values)
            equity_curve.append(
                EquityPoint(
                    timestamp=event.timestamp,
                    realized_pnl=float(self.pnl.realized),
                    unrealized_pnl=float(unrealized_now),
                    fees_paid=float(self.pnl.fees_paid),
                    net_pnl=float(
                        self.pnl.realized + unrealized_now - self.pnl.fees_paid
                    ),
                )
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
            equity_curve=tuple(equity_curve),
        )
