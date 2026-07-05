from dataclasses import dataclass
from typing import Literal

import numpy as np

from options_mm.pricing.black_scholes import call_price_greeks, put_price_greeks


@dataclass
class Quote:
    bid: float
    ask: float
    mid: float


class QuoteEngine:
    """Simple theoretical quote engine.

    It uses Black-Scholes to compute a theoretical mid and then applies a
    fixed half-spread to produce bid/ask.
    """

    def __init__(self, half_spread: float = 0.05):
        self.half_spread = float(half_spread)

    def theoretical_price(self, S: float, K: float, r: float, sigma: float, T: float, option_type: Literal['call', 'put']='call') -> float:
        if option_type == 'call':
            return call_price_greeks(S, K, r, sigma, T).price
        return put_price_greeks(S, K, r, sigma, T).price

    def quote(self, S: float, K: float, r: float, sigma: float, T: float, option_type: Literal['call', 'put']='call') -> Quote:
        mid = float(self.theoretical_price(S, K, r, sigma, T, option_type))
        bid = max(0.0, mid - self.half_spread)
        ask = mid + self.half_spread
        return Quote(bid=bid, ask=ask, mid=mid)
