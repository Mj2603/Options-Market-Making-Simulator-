"""Black-Scholes European option prices and Greeks.

Rates are continuously compounded. Time is measured in years. Theta is the
calendar-time derivative per year; vega is the derivative per 1.00 volatility
change (not per volatility point).
"""
from dataclasses import dataclass
import math

import numpy as np
from scipy.stats import norm


@dataclass(frozen=True)
class OptionGreeks:
    price: float
    delta: float
    gamma: float
    vega: float
    theta: float


def _validate_inputs(S: float, K: float, r: float, sigma: float, T: float) -> None:
    values = np.asarray([S, K, r, sigma, T], dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("S, K, r, sigma, and T must be finite")
    if S <= 0 or K <= 0:
        raise ValueError("spot and strike must be positive")
    if sigma < 0:
        raise ValueError("volatility must be non-negative")
    if T < 0:
        raise ValueError("time to expiry must be non-negative")


def _zero_volatility_price(S: float, K: float, r: float, T: float, is_call: bool) -> OptionGreeks:
    discounted_strike = K * math.exp(-r * T)
    if is_call:
        intrinsic = S - discounted_strike
        delta = 1.0 if intrinsic > 0 else 0.0 if intrinsic < 0 else 0.5
    else:
        intrinsic = discounted_strike - S
        delta = -1.0 if intrinsic > 0 else 0.0 if intrinsic < 0 else -0.5
    return OptionGreeks(
        price=float(max(intrinsic, 0.0)),
        delta=delta,
        gamma=0.0,
        vega=0.0,
        theta=0.0,
    )


def _price_greeks(S: float, K: float, r: float, sigma: float, T: float, is_call: bool) -> OptionGreeks:
    _validate_inputs(S, K, r, sigma, T)
    if T == 0 or sigma == 0:
        return _zero_volatility_price(S, K, r, T, is_call)

    sqrt_t = math.sqrt(T)
    d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * sqrt_t)
    d2 = d1 - sigma * sqrt_t
    discount = math.exp(-r * T)
    density = norm.pdf(d1)
    gamma = density / (S * sigma * sqrt_t)
    vega = S * density * sqrt_t

    if is_call:
        price = S * norm.cdf(d1) - K * discount * norm.cdf(d2)
        delta = norm.cdf(d1)
        theta = -(S * density * sigma) / (2.0 * sqrt_t) - r * K * discount * norm.cdf(d2)
    else:
        price = K * discount * norm.cdf(-d2) - S * norm.cdf(-d1)
        delta = norm.cdf(d1) - 1.0
        theta = -(S * density * sigma) / (2.0 * sqrt_t) + r * K * discount * norm.cdf(-d2)

    result = np.asarray([price, delta, gamma, vega, theta], dtype=float)
    if not np.isfinite(result).all():
        raise ArithmeticError("Black-Scholes calculation produced a non-finite result")
    return OptionGreeks(*(float(value) for value in result))


def call_price_greeks(S: float, K: float, r: float, sigma: float, T: float) -> OptionGreeks:
    """Return European call price and Greeks."""
    return _price_greeks(S, K, r, sigma, T, is_call=True)


def put_price_greeks(S: float, K: float, r: float, sigma: float, T: float) -> OptionGreeks:
    """Return European put price and Greeks."""
    return _price_greeks(S, K, r, sigma, T, is_call=False)
