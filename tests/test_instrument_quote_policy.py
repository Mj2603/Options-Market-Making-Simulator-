import pytest

from options_mm.market.policies import InstrumentAwareASQuoteModel


def test_instrument_aware_policy_uses_distinct_arrival_sensitivities():
    policy = InstrumentAwareASQuoteModel(
        risk_aversion=0.1,
        price_sensitivity_by_instrument={"OPT-A": 1.0, "OPT-B": 20.0},
        default_price_sensitivity=5.0,
    )
    quote_a = policy.quote_for_instrument("OPT-A", 10.0, 0.0, 0.5, 0.25)
    quote_b = policy.quote_for_instrument("OPT-B", 10.0, 0.0, 0.5, 0.25)
    quote_unknown = policy.quote_for_instrument("OPT-X", 10.0, 0.0, 0.5, 0.25)
    assert quote_a.half_spread > quote_b.half_spread
    assert quote_unknown.half_spread > quote_b.half_spread
