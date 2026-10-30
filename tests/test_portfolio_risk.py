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
    assert scenario == pytest.approx(-50.0 * 2.0 + 0.5 * 2.0 * 2.0 + 10.0 * 0.01 - 3.0)
