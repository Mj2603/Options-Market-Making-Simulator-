import pytest

from options_mm.metrics.pnl import PnLManager


def test_partial_close_and_mtm():
    p = PnLManager()
    p.record_fill("ABC", 100.0, 10.0)
    p.record_fill("ABC", 110.0, -5.0)
    assert p.realized == pytest.approx(50.0)
    mtm = p.mark_to_market({"ABC": 120.0})
    assert mtm == pytest.approx(100.0)
    assert p.total_unrealized_plus_realized({"ABC": 120.0}) == pytest.approx(150.0)
    assert p.net_total_pnl({"ABC": 120.0}) == pytest.approx(150.0)


def test_flip_side_realized_and_new_position():
    p = PnLManager()
    p.record_fill("ABC", 100.0, 10.0)
    p.record_fill("ABC", 110.0, -15.0)
    assert p.realized == pytest.approx(100.0)
    assert p.positions["ABC"]["qty"] == -5.0
    assert p.positions["ABC"]["avg"] == pytest.approx(110.0)


def test_contract_multiplier_and_commissions_are_separated():
    p = PnLManager(
        commission_per_contract=0.65,
        contract_multipliers={"OPT-100-C": 100.0},
    )
    p.record_fill("OPT-100-C", 1.0, 2.0)
    p.record_fill("OPT-100-C", 1.5, -1.0)

    assert p.realized == pytest.approx(50.0)
    assert p.fees_paid == pytest.approx(1.95)
    assert p.mark_to_market({"OPT-100-C": 1.25}) == pytest.approx(25.0)
    assert p.total_unrealized_plus_realized({"OPT-100-C": 1.25}) == pytest.approx(75.0)
    assert p.net_total_pnl({"OPT-100-C": 1.25}) == pytest.approx(73.05)


@pytest.mark.parametrize(
    "price,size",
    [(-1.0, 1.0), (1.0, 0.0), (float("nan"), 1.0), (1.0, float("inf"))],
)
def test_invalid_fills_are_rejected(price, size):
    with pytest.raises(ValueError):
        PnLManager().record_fill("ABC", price, size)


def test_invalid_commission_and_contract_multiplier_are_rejected():
    with pytest.raises(ValueError):
        PnLManager(commission_per_contract=-0.01)
    with pytest.raises(ValueError):
        PnLManager(contract_multipliers={"OPT": 0.0})


def test_negative_mark_price_is_rejected():
    p = PnLManager()
    p.record_fill("ABC", 1.0, 1.0)
    with pytest.raises(ValueError):
        p.mark_to_market({"ABC": -0.1})
