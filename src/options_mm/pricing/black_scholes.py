from dataclasses import dataclass
import numpy as np
from scipy.stats import norm


@dataclass
class OptionGreeks:
    price: float
    delta: float
    gamma: float
    vega: float
    theta: float


def _d1(S, K, r, sigma, T):
    return (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))


def _d2(d1, sigma, T):
    return d1 - sigma * np.sqrt(T)


def call_price_greeks(S: float, K: float, r: float, sigma: float, T: float) -> OptionGreeks:
    if T <= 0 or sigma <= 0:
        price = max(S - K, 0.0)
        delta = 1.0 if S > K else 0.0
        return OptionGreeks(price=price, delta=delta, gamma=0.0, vega=0.0, theta=0.0)
    d1 = _d1(S, K, r, sigma, T)
    d2 = _d2(d1, sigma, T)
    price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
    delta = norm.cdf(d1)
    gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
    vega = S * norm.pdf(d1) * np.sqrt(T)
    theta = - (S * norm.pdf(d1) * sigma) / (2 * np.sqrt(T)) - r * K * np.exp(-r * T) * norm.cdf(d2)
    return OptionGreeks(price=float(price), delta=float(delta), gamma=float(gamma), vega=float(vega), theta=float(theta))


def put_price_greeks(S: float, K: float, r: float, sigma: float, T: float) -> OptionGreeks:
    if T <= 0 or sigma <= 0:
        price = max(K - S, 0.0)
        delta = -1.0 if S < K else 0.0
        return OptionGreeks(price=price, delta=delta, gamma=0.0, vega=0.0, theta=0.0)
    d1 = _d1(S, K, r, sigma, T)
    d2 = _d2(d1, sigma, T)
    price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
    delta = -norm.cdf(-d1)
    gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
    vega = S * norm.pdf(d1) * np.sqrt(T)
    theta = - (S * norm.pdf(d1) * sigma) / (2 * np.sqrt(T)) + r * K * np.exp(-r * T) * norm.cdf(-d2)
    return OptionGreeks(price=float(price), delta=float(delta), gamma=float(gamma), vega=float(vega), theta=float(theta))
