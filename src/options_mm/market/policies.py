"""Quote policies with a common interface for controlled comparisons."""
from dataclasses import dataclass
import math

from options_mm.market.avellaneda_stoikov import InventoryAwareQuote


@dataclass(frozen=True)
class FixedSpreadQuoteModel:
    half_spread: float = 0.05

    def __post_init__(self):
        spread = float(self.half_spread)
        if not math.isfinite(spread) or spread < 0.0:
            raise ValueError("half_spread must be finite and non-negative")
        object.__setattr__(self, "half_spread", spread)

    def quote(
        self,
        fair_value: float,
        inventory: float,
        price_volatility: float,
        time_to_horizon: float,
    ) -> InventoryAwareQuote:
        values = (fair_value, inventory, price_volatility, time_to_horizon)
        if not all(math.isfinite(float(value)) for value in values):
            raise ValueError("quote inputs must be finite")
        if fair_value < 0.0 or price_volatility < 0.0 or time_to_horizon < 0.0:
            raise ValueError("fair value, volatility, and horizon must be non-negative")
        bid = max(0.0, fair_value - self.half_spread)
        ask = max(bid, fair_value + self.half_spread)
        return InventoryAwareQuote(
            fair_value=float(fair_value),
            reservation_price=float(fair_value),
            bid=bid,
            ask=ask,
            half_spread=self.half_spread,
            inventory=float(inventory),
        )


class InstrumentAwareASQuoteModel:
    """Apply instrument-specific arrival price sensitivity with shared gamma."""

    def __init__(
        self,
        risk_aversion: float,
        price_sensitivity_by_instrument: dict[str, float],
        default_price_sensitivity: float,
    ):
        from options_mm.market.avellaneda_stoikov import AvellanedaStoikovQuoteModel

        self.default_model = AvellanedaStoikovQuoteModel(
            risk_aversion=risk_aversion,
            order_arrival_intensity=default_price_sensitivity,
        )
        self.models = {
            instrument: AvellanedaStoikovQuoteModel(
                risk_aversion=risk_aversion,
                order_arrival_intensity=sensitivity,
            )
            for instrument, sensitivity in price_sensitivity_by_instrument.items()
        }

    def quote_for_instrument(
        self,
        instrument: str,
        fair_value: float,
        inventory: float,
        price_volatility: float,
        time_to_horizon: float,
    ) -> InventoryAwareQuote:
        model = self.models.get(instrument, self.default_model)
        return model.quote(
            fair_value, inventory, price_volatility, time_to_horizon
        )

    def quote(
        self,
        fair_value: float,
        inventory: float,
        price_volatility: float,
        time_to_horizon: float,
    ) -> InventoryAwareQuote:
        return self.default_model.quote(
            fair_value, inventory, price_volatility, time_to_horizon
        )
