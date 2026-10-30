from options_mm.market.quote_engine import QuoteEngine
from options_mm.pricing.black_scholes import call_price_greeks


def test_quote_engine_mid_matches_greeks():
    engine = QuoteEngine(half_spread=0.1)
    S = 100.0
    K = 100.0
    r = 0.01
    sigma = 0.2
    T = 30 / 365.25
    q = engine.quote(S, K, r, sigma, T, "call")
    expected_mid = call_price_greeks(S, K, r, sigma, T).price
    assert abs(q.mid - expected_mid) < 1e-8
    assert abs(q.ask - q.bid - 0.2) < 1e-12


def test_quote_engine_rejects_invalid_spread_and_option_type():
    import pytest

    for spread in (-0.01, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            QuoteEngine(half_spread=spread)

    with pytest.raises(ValueError, match="option_type"):
        QuoteEngine().quote(100, 100, 0.01, 0.2, 1.0, "binary")
