import math

import pytest

from options_mm.risk.portfolio import OptionRiskPosition, PortfolioRiskManager


def pos(instrument="AAPL-C", underlying="AAPL", quantity=1.0, delta=0.5, value=2.0):
    return OptionRiskPosition(
        instrument=instrument, underlying=underlying, quantity=quantity,
        multiplier=100.0, delta=delta, gamma=0.02, vega=0.1, theta=-0.03,
        market_value=value,
    )


def test_portfolio_greeks_and_concentration_aggregate():
    exposure = PortfolioRiskManager.aggregate([
        pos(quantity=2.0),
        pos(instrument="AAPL-P", quantity=-1.0, delta=-0.4, value=3.0),
    ])
    assert exposure.delta == pytest.approx(140.0)
    assert exposure.gross_market_value == pytest.approx(700.0)
    assert exposure.by_underlying["AAPL"] == pytest.approx(700.0)


def test_pretrade_rejects_delta_limit_breach():
    risk = PortfolioRiskManager(max_abs_delta=50.0)
    decision = risk.pre_trade_check([], pos(quantity=2.0))
    assert not decision.approved
    assert "delta" in decision.reason


def test_pretrade_approves_within_limits():
    risk = PortfolioRiskManager(max_abs_delta=100.0, max_gross_market_value=1000.0)
    decision = risk.pre_trade_check([], pos(quantity=1.0))
    assert decision.approved
    assert decision.reason == "approved"


def test_invalid_risk_position_rejected():
    risk = PortfolioRiskManager()
    with pytest.raises(ValueError):
        risk.pre_trade_check([], pos(quantity=float("nan")))


def test_delta_hedge_and_scenario_pnl():
    positions = [pos(quantity=1.0, delta=0.5)]
    risk = PortfolioRiskManager()
    assert risk.delta_hedge_quantity(positions) == pytest.approx(-50.0)
    exposure = risk.aggregate(positions)
    scenario = risk.scenario_pnl(
        exposure, spot_change=-2.0, volatility_change=0.01, days_elapsed=1.0
    )
    assert scenario == pytest.approx(
        50.0 * -2.0 + 0.5 * 2.0 * (-2.0) ** 2 + 10.0 * 0.01 - 3.0
    )


def test_pretrade_rejects_theta_limit_breach():
    risk = PortfolioRiskManager(max_abs_theta=1.0)
    decision = risk.pre_trade_check([], pos(quantity=1.0))
    assert not decision.approved
    assert "theta" in decision.reason


def test_delta_hedging_is_separated_by_underlying():
    positions = [
        pos(instrument="AAPL-C", underlying="AAPL", quantity=1.0, delta=0.5),
        pos(instrument="MSFT-C", underlying="MSFT", quantity=-1.0, delta=0.5),
    ]
    risk = PortfolioRiskManager()
    hedges = risk.delta_hedge_quantities(positions)
    assert hedges["AAPL"] == pytest.approx(-50.0)
    assert hedges["MSFT"] == pytest.approx(50.0)
    with pytest.raises(ValueError, match="multi-underlying"):
        risk.delta_hedge_quantity(positions)


def test_delta_limits_cannot_be_offset_across_different_underlyings():
    risk = PortfolioRiskManager(max_abs_delta=25.0)
    decision = risk.pre_trade_check(
        [pos(instrument="AAPL-C", underlying="AAPL", quantity=1.0, delta=0.5)],
        pos(instrument="MSFT-C", underlying="MSFT", quantity=-1.0, delta=0.5),
    )
    assert not decision.approved
    assert "delta" in decision.reason


def test_multi_underlying_stress_requires_symbol_specific_shocks():
    exposure = PortfolioRiskManager.aggregate([
        pos(instrument="AAPL-C", underlying="AAPL", quantity=1.0),
        pos(instrument="MSFT-C", underlying="MSFT", quantity=1.0),
    ])
    with pytest.raises(ValueError, match="by underlying"):
        PortfolioRiskManager.scenario_pnl(exposure, 1.0, 0.01)
    pnl = PortfolioRiskManager.scenario_pnl(
        exposure,
        {"AAPL": 1.0, "MSFT": -1.0},
        {"AAPL": 0.01, "MSFT": -0.02},
    )
    assert math.isfinite(pnl)
