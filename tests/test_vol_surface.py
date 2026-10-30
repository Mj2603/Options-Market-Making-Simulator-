import numpy as np
import pytest

from options_mm.pricing.vol_surface import (
    EWMAVolatility,
    SVIVolatilitySurface,
    price_with_surface,
)


def test_svi_surface_fits_and_interpolates_synthetic_smile():
    strikes = np.array([70, 80, 90, 95, 100, 105, 110, 120, 130], dtype=float)
    forwards = np.full_like(strikes, 100.0)
    expiry = np.full_like(strikes, 0.5)
    k = np.log(strikes / forwards)
    true_w = 0.02 + 0.12 * (
        -0.25 * (k - 0.02) + np.sqrt((k - 0.02) ** 2 + 0.15**2)
    )
    iv = np.sqrt(true_w / 0.5)
    surface = SVIVolatilitySurface.fit(expiry, forwards, strikes, iv, min_points=7)
    atm_iv = surface.implied_volatility(100.0, 100.0, 0.5)
    assert atm_iv > 0.0
    assert surface.diagnostics()["slice_count"] == 1
    assert surface.diagnostics()["arbitrage_free_guarantee"] is False


def test_svi_rejects_bad_surface_inputs():
    with pytest.raises(ValueError):
        SVIVolatilitySurface.fit([0.0], [100.0], [100.0], [0.2])


def test_ewma_volatility_is_causal_and_positive():
    model = EWMAVolatility(decay=0.9, periods_per_year=252 * 390)
    assert np.isnan(model.update(100.0))
    vol1 = model.update(101.0)
    vol2 = model.update(99.0)
    assert vol1 > 0.0
    assert vol2 > 0.0
    assert model.previous_price == 99.0


def test_ewma_rejects_invalid_price():
    model = EWMAVolatility()
    with pytest.raises(ValueError):
        model.update(0.0)


def test_surface_volatility_flows_into_black_scholes_pricing():
    strikes = np.array([80, 90, 95, 100, 105, 110, 120], dtype=float)
    forwards = np.full_like(strikes, 100.0)
    expiry = np.full_like(strikes, 0.5)
    iv = np.full_like(strikes, 0.25)
    surface = SVIVolatilitySurface.fit(expiry, forwards, strikes, iv, min_points=5)
    greeks, used_iv = price_with_surface(
        surface, spot=100.0, forward=100.0, strike=100.0,
        rate=0.02, expiry_years=0.5, option_type="call",
    )
    assert used_iv > 0.0
    assert greeks.price > 0.0
