from options_mm.pricing.black_scholes import call_price_greeks, put_price_greeks


def test_call_put_parity():
    S = 100.0
    K = 100.0
    r = 0.01
    sigma = 0.2
    T = 30 / 365.25
    call = call_price_greeks(S, K, r, sigma, T)
    put = put_price_greeks(S, K, r, sigma, T)
    lhs = call.price - put.price
    rhs = S - K * (1.0 - r * T)
    assert abs(lhs - rhs) < 5.0


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
