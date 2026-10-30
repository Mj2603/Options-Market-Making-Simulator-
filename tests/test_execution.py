from options_mm.execution.execution import ExecutionEngine, Order


def test_market_buy_fills_at_ask():
    engine = ExecutionEngine()
    order = Order(side="buy", size=10.0)
    fill = engine.execute(order, bid=1.0, ask=1.2)
    assert fill is not None
    assert fill.price == 1.2
    assert fill.size == 10.0


def test_limit_buy_fills_when_limit_good():
    engine = ExecutionEngine()
    order = Order(side="buy", size=5.0, limit_price=1.25)
    fill = engine.execute(order, bid=1.0, ask=1.2)
    assert fill is not None
    assert fill.price == 1.2


def test_limit_buy_no_fill_when_limit_low():
    engine = ExecutionEngine()
    order = Order(side="buy", size=5.0, limit_price=1.1)
    fill = engine.execute(order, bid=1.0, ask=1.2)
    assert fill is None


def test_execution_rejects_invalid_order_and_market_inputs():
    import pytest

    engine = ExecutionEngine()
    for order in (
        Order(side="hold", size=1.0),
        Order(side="buy", size=0.0),
        Order(side="sell", size=float("nan")),
        Order(side="buy", size=1.0, limit_price=-0.1),
    ):
        with pytest.raises(ValueError):
            engine.execute(order, bid=1.0, ask=1.2)

    with pytest.raises(ValueError, match="quotes"):
        engine.execute(Order(side="buy", size=1.0), bid=1.3, ask=1.2)


def test_market_sell_fills_at_bid_and_limit_sell_respects_limit():
    engine = ExecutionEngine()
    fill = engine.execute(Order(side="sell", size=2.0), bid=1.0, ask=1.2)
    assert fill is not None and fill.price == 1.0
    assert engine.execute(
        Order(side="sell", size=2.0, limit_price=1.1), bid=1.0, ask=1.2
    ) is None
