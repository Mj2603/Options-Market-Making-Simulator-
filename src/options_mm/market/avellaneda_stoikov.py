"""Inventory-aware quotes from the Avellaneda-Stoikov reservation-price model.

The implementation is deliberately generic: price_volatility is the
annualized volatility of the instrument's price (currency units / sqrt(year)),
not the underlying's percentage volatility. For an option, callers must derive
that input consistently (for example, from a local delta approximation).

This is a quote-placement baseline, not a calibrated fill-probability model.
The arrival-intensity parameter is assumed constant and does not model queue
position, adverse selection, or market impact.
"""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class InventoryAwareQuote:
    """A quote and the model quantities used to construct it."""

    fair_value: float
    reservation_price: float
    bid: float
    ask: float
    half_spread: float
    inventory: float


class AvellanedaStoikovQuoteModel:
    """Compute inventory-skewed bid/ask prices using the A-S baseline.

    Parameters
    ----------
    risk_aversion:
        Positive risk-aversion coefficient (gamma).
    order_arrival_intensity:
        Positive exponential order-arrival intensity (k). Its units are
        inverse price units under the simplified A-S parameterization.

    Notes
    -----
    For inventory q, price volatility sigma, and remaining horizon tau:

        reservation = fair_value - q * gamma * sigma**2 * tau
        half_spread = 0.5 * gamma * sigma**2 * tau
                     + log(1 + gamma / k) / gamma

    Positive inventory shifts both quotes down; negative inventory shifts
    both quotes up. This creates an incentive to trade inventory back toward
    zero. The model assumes constant volatility and arrival intensity.
    """

    def __init__(
        self,
        risk_aversion: float = 0.1,
        order_arrival_intensity: float = 1.5,
    ) -> None:
        self.risk_aversion = self._finite_float("risk_aversion", risk_aversion)
        self.order_arrival_intensity = self._finite_float(
            "order_arrival_intensity", order_arrival_intensity
        )
        if self.risk_aversion <= 0.0:
            raise ValueError("risk_aversion must be strictly positive")
        if self.order_arrival_intensity <= 0.0:
            raise ValueError("order_arrival_intensity must be strictly positive")

    @staticmethod
    def _finite_float(name: str, value: float) -> float:
        try:
            result = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be a finite number") from exc
        if not math.isfinite(result):
            raise ValueError(f"{name} must be a finite number")
        return result

    def quote(
        self,
        fair_value: float,
        inventory: float,
        price_volatility: float,
        time_to_horizon: float,
    ) -> InventoryAwareQuote:
        """Return bid/ask quotes for one instrument and one decision time.

        price_volatility is in price units per square-root year and
        time_to_horizon is in years. Inventory is signed: long is positive.
        """
        fair_value = self._finite_float("fair_value", fair_value)
        inventory = self._finite_float("inventory", inventory)
        price_volatility = self._finite_float(
            "price_volatility", price_volatility
        )
        time_to_horizon = self._finite_float(
            "time_to_horizon", time_to_horizon
        )

        if fair_value < 0.0:
            raise ValueError("fair_value must be non-negative")
        if price_volatility < 0.0:
            raise ValueError("price_volatility must be non-negative")
        if time_to_horizon < 0.0:
            raise ValueError("time_to_horizon must be non-negative")

        gamma = self.risk_aversion
        try:
            sigma_squared_horizon = price_volatility**2 * time_to_horizon
            reservation_price = (
                fair_value - inventory * gamma * sigma_squared_horizon
            )
            arrival_term = math.log1p(
                gamma / self.order_arrival_intensity
            ) / gamma
            half_spread = (
                0.5 * gamma * sigma_squared_horizon + arrival_term
            )
        except (OverflowError, ValueError) as exc:
            raise ValueError("model inputs produce an unstable quote") from exc

        if not all(
            math.isfinite(value)
            for value in (reservation_price, half_spread)
        ):
            raise ValueError("model inputs produce a non-finite quote")

        raw_bid = reservation_price - half_spread
        raw_ask = reservation_price + half_spread
        if not math.isfinite(raw_bid) or not math.isfinite(raw_ask):
            raise ValueError("model inputs produce a non-finite quote")
        bid = max(0.0, raw_bid)
        ask = max(bid, raw_ask)

        return InventoryAwareQuote(
            fair_value=fair_value,
            reservation_price=reservation_price,
            bid=bid,
            ask=ask,
            half_spread=half_spread,
            inventory=inventory,
        )
