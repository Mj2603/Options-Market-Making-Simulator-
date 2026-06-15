from options_mm.hedge.delta import compute_net_delta, hedge_quantity_for_underlying


def test_compute_net_delta_and_hedge():
    # two long calls with delta 0.5 each
    positions = [(0.5, 10), (0.5, 10)]
    net = compute_net_delta(positions)
    assert net == 10.0
    hedge_qty = hedge_quantity_for_underlying(positions)
    assert hedge_qty == -10.0


def test_mixed_positions():
    positions = [(0.6, 5), (-0.4, -8)]  # second is short puts -> negative size
    net = compute_net_delta(positions)
    assert abs(net - (0.6 * 5 + (-0.4) * -8)) < 1e-12
    assert hedge_quantity_for_underlying(positions) == -net
