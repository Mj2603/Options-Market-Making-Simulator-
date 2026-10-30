"""Training-only calibration utilities for exponential order-arrival models.

The fitted intensity is lambda(delta) = A * exp(-k * delta), where delta is
quote distance in currency price units, A is events/second at zero distance,
and k is inverse price units. The fitted k maps to the A-S price-sensitivity
parameter; A is retained as a diagnostic because it controls absolute fill
frequency but cancels from the simplified stationary quote-width expression.
"""
from dataclasses import dataclass
import math

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import gammaln


@dataclass(frozen=True)
class ArrivalCalibration:
    intensity_at_zero: float
    price_sensitivity: float
    observations: int
    total_arrivals: int
    log_likelihood: float
    converged: bool

    def as_dict(self) -> dict[str, float | int | bool]:
        return {
            "intensity_at_zero": self.intensity_at_zero,
            "price_sensitivity": self.price_sensitivity,
            "observations": self.observations,
            "total_arrivals": self.total_arrivals,
            "log_likelihood": self.log_likelihood,
            "converged": self.converged,
        }


def calibrate_exponential_arrivals(
    observations: pd.DataFrame,
) -> ArrivalCalibration:
    """Fit a Poisson arrival model from exposure/count observations.

    Required columns:
      quote_distance: non-negative distance from the contemporaneous mid.
      arrival_count: non-negative integer count of eligible arrivals.
      exposure_seconds: positive time exposed at that quote distance.

    The caller must build this panel from the training window only. Counts
    should represent a consistent event definition and one independent
    exposure unit per row. Do not mix trade prints, quote updates, and fills.
    """
    required = {"quote_distance", "arrival_count", "exposure_seconds"}
    missing = required.difference(observations.columns)
    if missing:
        raise ValueError(f"missing calibration columns: {', '.join(sorted(missing))}")
    frame = observations[list(required)].apply(pd.to_numeric, errors="coerce")
    values = frame.to_numpy(dtype=float)
    if values.size == 0 or not np.isfinite(values).all():
        raise ValueError("calibration panel must be non-empty and finite")
    distance = frame["quote_distance"].to_numpy(dtype=float)
    count = frame["arrival_count"].to_numpy(dtype=float)
    exposure = frame["exposure_seconds"].to_numpy(dtype=float)
    if np.any(distance < 0.0):
        raise ValueError("quote_distance must be non-negative")
    if np.any(count < 0.0) or np.any(count != np.floor(count)):
        raise ValueError("arrival_count must contain non-negative integers")
    if np.any(exposure <= 0.0):
        raise ValueError("exposure_seconds must be strictly positive")
    if int(count.sum()) == 0:
        raise ValueError("at least one arrival is required for calibration")
    if np.ptp(distance) <= 1e-12:
        raise ValueError("quote_distance must vary to identify price sensitivity")

    def negative_log_likelihood(theta: np.ndarray) -> float:
        log_a, log_k = theta
        a = math.exp(float(log_a))
        k = math.exp(float(log_k))
        log_rate = math.log(a) - k * distance
        log_mu = np.log(exposure) + log_rate
        if np.any(log_mu > 700.0):
            return 1e300
        mu = np.exp(log_mu)
        return float(np.sum(mu - count * log_mu + gammaln(count + 1.0)))

    average_rate = float(count.sum() / exposure.sum())
    initial = np.array([math.log(max(average_rate, 1e-8)), math.log(1.0)])
    fit = minimize(
        negative_log_likelihood,
        initial,
        method="L-BFGS-B",
        bounds=[(-20.0, 20.0), (-12.0, 12.0)],
    )
    if not fit.success or not np.isfinite(fit.fun):
        raise RuntimeError(f"arrival calibration failed: {fit.message}")
    a, k = np.exp(fit.x)
    return ArrivalCalibration(
        intensity_at_zero=float(a),
        price_sensitivity=float(k),
        observations=int(len(frame)),
        total_arrivals=int(count.sum()),
        log_likelihood=float(-fit.fun),
        converged=bool(fit.success),
    )
