"""Black-Scholes pricing and Greeks for European options."""
from dataclasses import dataclass
import math

from scipy.stats import norm


@dataclass(frozen=True)
class OptionGreeks:
    price: float
    delta: float
    gamma: float
    vega: float
    theta: float


def _validate_inputs(S: float, K: float, r: float, sigma: float, T: float):
    values = {"S": S, "K": K, "r": r, "sigma": sigma, "T": T}
    converted = {}
    for name, value in values.items():
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be a finite number") from exc
        if not math.isfinite(number):
            raise ValueError(f"{name} must be a finite number")
        converted[name] = number

    S, K, r, sigma, T = (
        converted["S"],
        converted["K"],
        converted["r"],
        converted["sigma"],
        converted["T"],
    )
    if S <= 0.0:
        raise ValueError("S must be strictly positive")
    if K <= 0.0:
        raise ValueError("K must be strictly positive")
    if sigma < 0.0:
        raise ValueError("sigma must be non-negative")
    if T < 0.0:
        raise ValueError("T must be non-negative")
    return S, K, r, sigma, T


def _discount_factor(r: float, T: float) -> float:
    try:
        discount = math.exp(-r * T)
    except OverflowError as exc:
        raise ValueError(
            "rate and maturity produce an unstable discount factor"
        ) from exc
    if not math.isfinite(discount):
        raise ValueError("rate and maturity produce a non-finite discount factor")
    return discount


def _result(
    price: float, delta: float, gamma: float, vega: float, theta: float
) -> OptionGreeks:
    values = (price, delta, gamma, vega, theta)
    if not all(math.isfinite(value) for value in values):
        raise ValueError("inputs produce non-finite Black-Scholes output")
    return OptionGreeks(
        price=float(price),
        delta=float(delta),
        gamma=float(gamma),
        vega=float(vega),
        theta=float(theta),
    )


def _deterministic_greeks(
    S: float, K: float, r: float, T: float, option_type: str
) -> OptionGreeks:
    """Exact zero-volatility or expiry value, with midpoint ATM delta."""
    discounted_strike = K * _discount_factor(r, T) if T > 0.0 else K
    if option_type == "call":
        intrinsic = max(S - discounted_strike, 0.0)
        delta = 1.0 if S > discounted_strike else 0.0
        if S == discounted_strike:
            delta = 0.5
    else:
        intrinsic = max(discounted_strike - S, 0.0)
        delta = -1.0 if S < discounted_strike else 0.0
        if S == discounted_strike:
            delta = -0.5
    return _result(intrinsic, delta, 0.0, 0.0, 0.0)


def _d1(S: float, K: float, r: float, sigma: float, T: float) -> float:
    numerator = math.log(S) - math.log(K) + (r + 0.5 * sigma**2) * T
    return numerator / (sigma * math.sqrt(T))


def _d2(d1: float, sigma: float, T: float) -> float:
    return d1 - sigma * math.sqrt(T)


def call_price_greeks(
    S: float, K: float, r: float, sigma: float, T: float
) -> OptionGreeks:
    S, K, r, sigma, T = _validate_inputs(S, K, r, sigma, T)
    if T == 0.0 or sigma == 0.0:
        return _deterministic_greeks(S, K, r, T, "call")

    d1 = _d1(S, K, r, sigma, T)
    d2 = _d2(d1, sigma, T)
    discount = _discount_factor(r, T)
    density = norm.pdf(d1)
    price = S * norm.cdf(d1) - K * discount * norm.cdf(d2)
    delta = norm.cdf(d1)
    gamma = density / (S * sigma * math.sqrt(T))
    vega = S * density * math.sqrt(T)
    theta = (
        -(S * density * sigma) / (2.0 * math.sqrt(T))
        - r * K * discount * norm.cdf(d2)
    )
    return _result(price, delta, gamma, vega, theta)


def put_price_greeks(
    S: float, K: float, r: float, sigma: float, T: float
) -> OptionGreeks:
    S, K, r, sigma, T = _validate_inputs(S, K, r, sigma, T)
    if T == 0.0 or sigma == 0.0:
        return _deterministic_greeks(S, K, r, T, "put")

    d1 = _d1(S, K, r, sigma, T)
    d2 = _d2(d1, sigma, T)
    discount = _discount_factor(r, T)
    density = norm.pdf(d1)
    price = K * discount * norm.cdf(-d2) - S * norm.cdf(-d1)
    delta = -norm.cdf(-d1)
    gamma = density / (S * sigma * math.sqrt(T))
    vega = S * density * math.sqrt(T)
    theta = (
        -(S * density * sigma) / (2.0 * math.sqrt(T))
        + r * K * discount * norm.cdf(-d2)
    )
    return _result(price, delta, gamma, vega, theta)
