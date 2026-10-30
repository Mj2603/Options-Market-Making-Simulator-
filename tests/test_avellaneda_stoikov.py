import math

import pytest

from options_mm.market.avellaneda_stoikov import AvellanedaStoikovQuoteModel


def test_zero_inventory_quotes_are_symmetric_around_fair_value():
    model = AvellanedaStoikovQuoteModel(
        risk_aversion=0.2, order_arrival_intensity=2.0
    )
    quote = model.quote(
        fair_value=10.0,
        inventory=0.0,
        price_volatility=1.5,
        time_to_horizon=0.25,
    )
    assert quote.reservation_price == pytest.approx(10.0)
    assert (quote.ask + quote.bid) / 2 == pytest.approx(10.0)
    assert quote.ask - quote.bid == pytest.approx(2 * quote.half_spread)


def test_positive_inventory_skews_quotes_down():
    model = AvellanedaStoikovQuoteModel()
    flat = model.quote(10.0, 0.0, 1.0, 0.5)
    long = model.quote(10.0, 20.0, 1.0, 0.5)
    assert long.reservation_price < flat.reservation_price
    assert long.bid < flat.bid
    assert long.ask < flat.ask


def test_negative_inventory_skews_quotes_up():
    model = AvellanedaStoikovQuoteModel()
    flat = model.quote(10.0, 0.0, 1.0, 0.5)
    short = model.quote(10.0, -20.0, 1.0, 0.5)
    assert short.reservation_price > flat.reservation_price
    assert short.bid > flat.bid
    assert short.ask > flat.ask


def test_spread_increases_with_volatility_and_horizon():
    model = AvellanedaStoikovQuoteModel()
    base = model.quote(10.0, 0.0, 0.5, 0.25)
    higher_vol = model.quote(10.0, 0.0, 1.0, 0.25)
    longer_horizon = model.quote(10.0, 0.0, 0.5, 1.0)
    assert higher_vol.half_spread > base.half_spread
    assert longer_horizon.half_spread > base.half_spread


def test_zero_volatility_and_zero_horizon_have_finite_spread():
    model = AvellanedaStoikovQuoteModel()
    quote = model.quote(5.0, 100.0, 0.0, 0.0)
    expected = math.log1p(
        model.risk_aversion / model.order_arrival_intensity
    ) / model.risk_aversion
    assert quote.half_spread == pytest.approx(expected)
    assert math.isfinite(quote.bid)
    assert math.isfinite(quote.ask)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"fair_value": -1.0, "inventory": 0.0, "price_volatility": 1.0, "time_to_horizon": 1.0},
        {"fair_value": 1.0, "inventory": 0.0, "price_volatility": -1.0, "time_to_horizon": 1.0},
        {"fair_value": 1.0, "inventory": 0.0, "price_volatility": 1.0, "time_to_horizon": -1.0},
        {"fair_value": float("nan"), "inventory": 0.0, "price_volatility": 1.0, "time_to_horizon": 1.0},
        {"fair_value": 1.0, "inventory": float("inf"), "price_volatility": 1.0, "time_to_horizon": 1.0},
    ],
)
def test_invalid_market_inputs_are_rejected(kwargs):
    with pytest.raises(ValueError):
        AvellanedaStoikovQuoteModel().quote(**kwargs)


@pytest.mark.parametrize(
    "gamma,k",
    [(0.0, 1.0), (-0.1, 1.0), (0.1, 0.0), (0.1, -1.0), (float("nan"), 1.0)],
)
def test_invalid_model_parameters_are_rejected(gamma, k):
    with pytest.raises(ValueError):
        AvellanedaStoikovQuoteModel(
            risk_aversion=gamma, order_arrival_intensity=k
        )


def test_extreme_inventory_never_produces_negative_or_crossed_quotes():
    model = AvellanedaStoikovQuoteModel()
    quote = model.quote(1.0, 1e9, 2.0, 1.0)
    assert quote.bid >= 0.0
    assert quote.ask >= quote.bid
