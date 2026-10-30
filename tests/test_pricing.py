import math

import pytest

from options_mm.pricing.black_scholes import call_price_greeks, put_price_greeks


def test_call_put_parity():
    S = 100.0
    K = 100.0
    r = 0.01
    sigma = 0.2
    T = 30 / 365.25
    call = call_price_greeks(S, K, r, sigma, T)
    put = put_price_greeks(S, K, r, sigma, T)
    assert call.price - put.price == pytest.approx(
        S - K * math.exp(-r * T), abs=1e-10
    )


def test_reference_black_scholes_prices():
    call = call_price_greeks(100.0, 100.0, 0.05, 0.2, 1.0)
    put = put_price_greeks(100.0, 100.0, 0.05, 0.2, 1.0)
    assert call.price == pytest.approx(10.450583572185565, abs=1e-10)
    assert put.price == pytest.approx(5.573526022256971, abs=1e-10)


def test_delta_monotonic():
    S0 = 90.0
    S1 = 100.0
    S2 = 110.0
    K = 100.0
    r = 0.01
    sigma = 0.2
    T = 60 / 365.25
    d0 = call_price_greeks(S0, K, r, sigma, T).delta
    d1 = call_price_greeks(S1, K, r, sigma, T).delta
    d2 = call_price_greeks(S2, K, r, sigma, T).delta
    assert d0 < d1 < d2


def test_zero_volatility_uses_discounted_strike():
    S, K, r, T = 100.0, 105.0, 0.05, 1.0
    call = call_price_greeks(S, K, r, 0.0, T)
    put = put_price_greeks(S, K, r, 0.0, T)
    discounted_strike = K * math.exp(-r * T)
    assert call.price == pytest.approx(max(S - discounted_strike, 0.0))
    assert put.price == pytest.approx(max(discounted_strike - S, 0.0))
    assert call.gamma == call.vega == call.theta == 0.0
    assert put.gamma == put.vega == put.theta == 0.0


def test_expiry_prices_equal_intrinsic_value():
    call = call_price_greeks(110.0, 100.0, 0.05, 0.2, 0.0)
    put = put_price_greeks(90.0, 100.0, 0.05, 0.2, 0.0)
    assert call.price == 10.0
    assert put.price == 10.0
    assert call.delta == 1.0
    assert put.delta == -1.0


@pytest.mark.parametrize(
    "args",
    [
        (0.0, 100.0, 0.01, 0.2, 1.0),
        (-1.0, 100.0, 0.01, 0.2, 1.0),
        (100.0, 0.0, 0.01, 0.2, 1.0),
        (100.0, -1.0, 0.01, 0.2, 1.0),
        (100.0, 100.0, 0.01, -0.2, 1.0),
        (100.0, 100.0, 0.01, 0.2, -1.0),
        (float("nan"), 100.0, 0.01, 0.2, 1.0),
        (100.0, 100.0, float("inf"), 0.2, 1.0),
    ],
)
def test_invalid_inputs_are_rejected(args):
    with pytest.raises(ValueError):
        call_price_greeks(*args)
    with pytest.raises(ValueError):
        put_price_greeks(*args)


def test_put_call_parity_with_continuous_dividend_yield():
    S, K, r, q, sigma, T = 100.0, 105.0, 0.04, 0.015, 0.25, 0.75
    call = call_price_greeks(S, K, r, sigma, T, q)
    put = put_price_greeks(S, K, r, sigma, T, q)
    expected = S * math.exp(-q * T) - K * math.exp(-r * T)
    assert call.price - put.price == pytest.approx(expected, abs=1e-10)


def test_zero_volatility_discounted_spot_and_strike():
    S, K, r, q, T = 100.0, 100.0, 0.05, 0.02, 1.0
    call = call_price_greeks(S, K, r, 0.0, T, q)
    put = put_price_greeks(S, K, r, 0.0, T, q)
    discounted_spot = S * math.exp(-q * T)
    discounted_strike = K * math.exp(-r * T)
    assert call.price == pytest.approx(max(discounted_spot - discounted_strike, 0.0))
    assert put.price == pytest.approx(max(discounted_strike - discounted_spot, 0.0))


def test_expiry_at_the_money_uses_symmetric_delta_convention():
    assert call_price_greeks(100.0, 100.0, 0.0, 0.2, 0.0).delta == 0.5
    assert put_price_greeks(100.0, 100.0, 0.0, 0.2, 0.0).delta == -0.5
