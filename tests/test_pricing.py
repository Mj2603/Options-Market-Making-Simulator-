import math

import pytest

from options_mm.pricing.black_scholes import call_price_greeks, put_price_greeks


def test_call_put_parity():
    S, K, r, sigma, T = 100.0, 100.0, 0.05, 0.2, 1.0
    call = call_price_greeks(S, K, r, sigma, T)
    put = put_price_greeks(S, K, r, sigma, T)
    assert call.price - put.price == pytest.approx(S - K * math.exp(-r * T), abs=1e-12)


def test_reference_black_scholes_prices():
    call = call_price_greeks(100.0, 100.0, 0.05, 0.2, 1.0)
    put = put_price_greeks(100.0, 100.0, 0.05, 0.2, 1.0)
    assert call.price == pytest.approx(10.450583572185565, abs=1e-10)
    assert put.price == pytest.approx(5.573526022256971, abs=1e-10)


def test_delta_monotonic():
    deltas = [
        call_price_greeks(spot, 100.0, 0.01, 0.2, 60 / 365.25).delta
        for spot in (90.0, 100.0, 110.0)
    ]
    assert deltas[0] < deltas[1] < deltas[2]


def test_zero_volatility_uses_discounted_strike():
    call = call_price_greeks(100.0, 105.0, 0.05, 0.0, 1.0)
    put = put_price_greeks(100.0, 105.0, 0.05, 0.0, 1.0)
    discounted_strike = 105.0 * math.exp(-0.05)
    assert call.price == pytest.approx(max(100.0 - discounted_strike, 0.0))
    assert put.price == pytest.approx(max(discounted_strike - 100.0, 0.0))
    assert call.delta == 1.0
    assert put.delta == 0.0
    assert call.gamma == call.vega == call.theta == 0.0


def test_expiry_at_the_money_uses_symmetric_delta_convention():
    assert call_price_greeks(100.0, 100.0, 0.0, 0.2, 0.0).delta == 0.5
    assert put_price_greeks(100.0, 100.0, 0.0, 0.2, 0.0).delta == -0.5


@pytest.mark.parametrize(
    "args",
    [
        (0.0, 100.0, 0.01, 0.2, 1.0),
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
