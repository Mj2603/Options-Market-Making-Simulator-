"""Black-Scholes fair-value quoting with a fixed-spread benchmark."""
from dataclasses import dataclass
import math
from typing import Literal

from options_mm.pricing.black_scholes import call_price_greeks, put_price_greeks


@dataclass(frozen=True)
class Quote:
    bid: float
    ask: float
    mid: float


class QuoteEngine:
    """Simple theoretical quote engine using a configurable fixed half-spread."""

    def __init__(self, half_spread: float = 0.05):
        try:
            spread = float(half_spread)
        except (TypeError, ValueError) as exc:
            raise ValueError("half_spread must be a finite non-negative number") from exc
        if not math.isfinite(spread) or spread < 0.0:
            raise ValueError("half_spread must be a finite non-negative number")
        self.half_spread = spread

    def theoretical_price(
        self,
        S: float,
        K: float,
        r: float,
        sigma: float,
        T: float,
        option_type: Literal["call", "put"] = "call",
    ) -> float:
        if option_type == "call":
            return call_price_greeks(S, K, r, sigma, T).price
        if option_type == "put":
            return put_price_greeks(S, K, r, sigma, T).price
        raise ValueError("option_type must be either 'call' or 'put'")

    def quote(
        self,
        S: float,
        K: float,
        r: float,
        sigma: float,
        T: float,
        option_type: Literal["call", "put"] = "call",
    ) -> Quote:
        mid = float(self.theoretical_price(S, K, r, sigma, T, option_type))
        bid = max(0.0, mid - self.half_spread)
        ask = mid + self.half_spread
        return Quote(bid=bid, ask=ask, mid=mid)
