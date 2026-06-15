from options_mm.metrics.pnl import PnLManager


def test_partial_close_and_mtm():
    p = PnLManager()
    p.record_fill("ABC", 100.0, 10.0)  # buy 10
    p.record_fill("ABC", 110.0, -5.0)  # sell 5
    assert abs(p.realized - 5.0 * (110.0 - 100.0)) < 1e-12
    mtm = p.mark_to_market({"ABC": 120.0})
    # remaining 5 shares at avg 100 -> mtm = 5*(120-100)=100
    assert abs(mtm - 100.0) < 1e-12
    assert abs(p.total_unrealized_plus_realized({"ABC": 120.0}) - (p.realized + mtm)) < 1e-12


def test_flip_side_realized_and_new_position():
    p = PnLManager()
    p.record_fill("ABC", 100.0, 10.0)
    p.record_fill("ABC", 110.0, -15.0)
    # realized from closing 10: 10*(110-100)=100
    assert abs(p.realized - 100.0) < 1e-12
    # net position now -5 at avg price 110
    assert p.positions["ABC"]["qty"] == -5.0
    assert p.positions["ABC"]["avg"] == 110.0
