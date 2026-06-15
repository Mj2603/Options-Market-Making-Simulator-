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
