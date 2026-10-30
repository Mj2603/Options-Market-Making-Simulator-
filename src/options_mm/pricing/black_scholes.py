"""Black-Scholes pricing and Greeks for European options with continuous yield."""
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


def _validate_inputs(
    S: float, K: float, r: float, sigma: float, T: float, q: float = 0.0
):
    values = {"S": S, "K": K, "r": r, "sigma": sigma, "T": T, "q": q}
    converted = {}
    for name, value in values.items():
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be a finite number") from exc
        if not math.isfinite(number):
            raise ValueError(f"{name} must be a finite number")
        converted[name] = number

    S, K, r, sigma, T, q = (
        converted["S"], converted["K"], converted["r"],
        converted["sigma"], converted["T"], converted["q"],
    )
    if S <= 0.0:
        raise ValueError("S must be strictly positive")
    if K <= 0.0:
        raise ValueError("K must be strictly positive")
    if sigma < 0.0:
        raise ValueError("sigma must be non-negative")
    if T < 0.0:
        raise ValueError("T must be non-negative")
    return S, K, r, sigma, T, q


def _discount_factor(rate: float, T: float) -> float:
    try:
        discount = math.exp(-rate * T)
    except OverflowError as exc:
        raise ValueError("rate and maturity produce an unstable discount factor") from exc
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
        price=float(price), delta=float(delta), gamma=float(gamma),
        vega=float(vega), theta=float(theta),
    )


def _deterministic_greeks(
    S: float, K: float, r: float, T: float, q: float, option_type: str
) -> OptionGreeks:
    """Zero-volatility/expiry value; ATM delta uses a midpoint convention."""
    discounted_spot = S * _discount_factor(q, T) if T > 0.0 else S
    discounted_strike = K * _discount_factor(r, T) if T > 0.0 else K
    discounted_delta = _discount_factor(q, T) if T > 0.0 else 1.0
    if option_type == "call":
        intrinsic = max(discounted_spot - discounted_strike, 0.0)
        delta = discounted_delta if discounted_spot > discounted_strike else 0.0
        if discounted_spot == discounted_strike:
            delta = 0.5 * discounted_delta
    else:
        intrinsic = max(discounted_strike - discounted_spot, 0.0)
        delta = -discounted_delta if discounted_spot < discounted_strike else 0.0
        if discounted_spot == discounted_strike:
            delta = -0.5 * discounted_delta
    return _result(intrinsic, delta, 0.0, 0.0, 0.0)


def _d1(S: float, K: float, r: float, sigma: float, T: float, q: float) -> float:
    try:
        numerator = math.log(S) - math.log(K) + (r - q + 0.5 * sigma**2) * T
        value = numerator / (sigma * math.sqrt(T))
    except (OverflowError, ZeroDivisionError) as exc:
        raise ValueError("inputs produce an unstable d1 value") from exc
    if not math.isfinite(value):
        raise ValueError("inputs produce a non-finite d1 value")
    return value


def _d2(d1: float, sigma: float, T: float) -> float:
    return d1 - sigma * math.sqrt(T)


def call_price_greeks(
    S: float, K: float, r: float, sigma: float, T: float, q: float = 0.0
) -> OptionGreeks:
    S, K, r, sigma, T, q = _validate_inputs(S, K, r, sigma, T, q)
    if T == 0.0 or sigma == 0.0:
        return _deterministic_greeks(S, K, r, T, q, "call")

    d1 = _d1(S, K, r, sigma, T, q)
    d2 = _d2(d1, sigma, T)
    discount_r = _discount_factor(r, T)
    discount_q = _discount_factor(q, T)
    density = norm.pdf(d1)
    price = S * discount_q * norm.cdf(d1) - K * discount_r * norm.cdf(d2)
    delta = discount_q * norm.cdf(d1)
    gamma = discount_q * density / (S * sigma * math.sqrt(T))
    vega = S * discount_q * density * math.sqrt(T)
    theta = (
        -(S * discount_q * density * sigma) / (2.0 * math.sqrt(T))
        + q * S * discount_q * norm.cdf(d1)
        - r * K * discount_r * norm.cdf(d2)
    )
    return _result(price, delta, gamma, vega, theta)


def put_price_greeks(
    S: float, K: float, r: float, sigma: float, T: float, q: float = 0.0
) -> OptionGreeks:
    S, K, r, sigma, T, q = _validate_inputs(S, K, r, sigma, T, q)
    if T == 0.0 or sigma == 0.0:
        return _deterministic_greeks(S, K, r, T, q, "put")

    d1 = _d1(S, K, r, sigma, T, q)
    d2 = _d2(d1, sigma, T)
    discount_r = _discount_factor(r, T)
    discount_q = _discount_factor(q, T)
    density = norm.pdf(d1)
    price = K * discount_r * norm.cdf(-d2) - S * discount_q * norm.cdf(-d1)
    delta = discount_q * (norm.cdf(d1) - 1.0)
    gamma = discount_q * density / (S * sigma * math.sqrt(T))
    vega = S * discount_q * density * math.sqrt(T)
    theta = (
        -(S * discount_q * density * sigma) / (2.0 * math.sqrt(T))
        - q * S * discount_q * norm.cdf(-d1)
        + r * K * discount_r * norm.cdf(-d2)
    )
    return _result(price, delta, gamma, vega, theta)
