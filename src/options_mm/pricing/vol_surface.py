"""Raw-SVI implied-volatility slices and a causal EWMA volatility estimator.

The SVI fit is a practical interpolation baseline, not an arbitrage-free
surface construction. Calendar and butterfly arbitrage diagnostics are
reported but not fully constrained by the optimizer.
"""
from dataclasses import dataclass
import math

import numpy as np
from scipy.optimize import least_squares


@dataclass(frozen=True)
class SVISlice:
    expiry: float
    a: float
    b: float
    rho: float
    m: float
    sigma: float
    rmse_total_variance: float

    def total_variance(self, log_moneyness: np.ndarray | float):
        k = np.asarray(log_moneyness, dtype=float)
        return self.a + self.b * (
            self.rho * (k - self.m)
            + np.sqrt((k - self.m) ** 2 + self.sigma**2)
        )


class SVIVolatilitySurface:
    """Fit one raw-SVI slice per expiry and interpolate total variance."""

    def __init__(self, slices: list[SVISlice]):
        if len(slices) < 1:
            raise ValueError("at least one SVI slice is required")
        self.slices = tuple(sorted(slices, key=lambda item: item.expiry))
        expiries = [item.expiry for item in self.slices]
        if any(not math.isfinite(t) or t <= 0.0 for t in expiries):
            raise ValueError("slice expiries must be finite and positive")
        if len(set(expiries)) != len(expiries):
            raise ValueError("slice expiries must be unique")

    @staticmethod
    def _raw_svi(params, k):
        a, b, rho, m, sigma = params
        return a + b * (rho * (k - m) + np.sqrt((k - m) ** 2 + sigma**2))

    @classmethod
    def fit(
        cls,
        expiry_years,
        forward,
        strike,
        implied_volatility,
        min_points: int = 5,
    ):
        expiry = np.asarray(expiry_years, dtype=float)
        forward = np.asarray(forward, dtype=float)
        strike = np.asarray(strike, dtype=float)
        iv = np.asarray(implied_volatility, dtype=float)
        if not (expiry.shape == forward.shape == strike.shape == iv.shape):
            raise ValueError("surface input arrays must have identical shapes")
        valid = (
            np.isfinite(expiry) & np.isfinite(forward) & np.isfinite(strike)
            & np.isfinite(iv) & (expiry > 0) & (forward > 0)
            & (strike > 0) & (iv > 0)
        )
        expiry, forward, strike, iv = (
            array[valid] for array in (expiry, forward, strike, iv)
        )
        if len(expiry) == 0:
            raise ValueError("no valid implied-volatility observations")
        slices = []
        for maturity in np.unique(expiry):
            mask = np.isclose(expiry, maturity, rtol=0.0, atol=1e-10)
            if int(mask.sum()) < min_points:
                continue
            k = np.log(strike[mask] / forward[mask])
            w = iv[mask] ** 2 * maturity
            if np.ptp(k) < 1e-5:
                continue
            initial = np.array([
                max(float(np.min(w)) * 0.5, 1e-8),
                max(float(np.ptp(w)), 1e-4),
                0.0,
                float(np.median(k)),
                0.15,
            ])
            lower = np.array([0.0, 1e-8, -0.999, -5.0, 1e-4])
            upper = np.array([10.0, 10.0, 0.999, 5.0, 5.0])

            def residual(params):
                model = cls._raw_svi(params, k)
                return (model - w) / np.maximum(w, 1e-6)

            result = least_squares(
                residual, initial, bounds=(lower, upper), loss="soft_l1"
            )
            if not result.success:
                continue
            a, b, rho, m, sigma = map(float, result.x)
            # Raw-SVI minimum total variance must be non-negative.
            minimum = a + b * sigma * math.sqrt(max(0.0, 1.0 - rho**2))
            if minimum < -1e-8:
                continue
            fitted = cls._raw_svi(result.x, k)
            rmse = float(np.sqrt(np.mean((fitted - w) ** 2)))
            slices.append(SVISlice(float(maturity), a, b, rho, m, sigma, rmse))
        if not slices:
            raise ValueError("no expiry had enough valid points for an SVI fit")
        return cls(slices)

    def implied_volatility(self, forward: float, strike: float, expiry_years: float):
        if not all(math.isfinite(x) for x in (forward, strike, expiry_years)):
            raise ValueError("surface query inputs must be finite")
        if forward <= 0.0 or strike <= 0.0 or expiry_years <= 0.0:
            raise ValueError("forward, strike, and expiry must be positive")
        target_k = math.log(strike / forward)
        expiries = np.array([item.expiry for item in self.slices])
        total_vars = np.array([
            max(float(item.total_variance(target_k)), 0.0)
            for item in self.slices
        ])
        # Interpolate total variance, not volatility, across maturity.
        total_variance = float(np.interp(expiry_years, expiries, total_vars))
        return math.sqrt(max(total_variance, 0.0) / expiry_years)

    def diagnostics(self) -> dict[str, float | int | bool]:
        return {
            "slice_count": len(self.slices),
            "max_slice_rmse": max(item.rmse_total_variance for item in self.slices),
            "minimum_svi_variance": min(
                item.a + item.b * item.sigma * math.sqrt(1.0 - item.rho**2)
                for item in self.slices
            ),
            "arbitrage_free_guarantee": False,
        }


class EWMAVolatility:
    """Causal annualized volatility forecast from observed log returns."""

    def __init__(self, decay: float = 0. is not None, periods_per_year: float = 252.0):
        if not 0.0 < decay < 1.0:
            raise ValueError("decay must be between zero and one")
        if not math.isfinite(periods_per_year) or periods_per_year <= 0.0:
            raise ValueError("periods_per_year must be positive and finite")
        self.decay = float(decay)
        self.periods_per_year = float(periods_per_year)
        self.variance = None
        self.previous_price = None

    def update(self, price: float) -> float:
        price = float(price)
        if not math.isfinite(price) or price <= 0.0:
            raise ValueError("price must be positive and finite")
        if self.previous_price is not None:
            ret = math.log(price / self.previous_price)
            squared = ret * ret
            self.variance = squared if self.variance is None else (
                self.decay * self.variance + (1.0 - self.decay) * squared
            )
        self.previous_price = price
        if self.variance is None:
            return float("nan")
        return math.sqrt(self.variance * self.periods_per_year)
