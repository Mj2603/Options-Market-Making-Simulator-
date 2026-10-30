import pytest

from options_mm.execution.queue import L1QueueModel, signed_markout
from options_mm.market.policies import FixedSpreadQuoteModel
from options_mm.simulation.event_driven import EventDrivenBacktest, MarketEvent


def test_queue_model_consumes_ahead_volume_before_filling():
    model = L1QueueModel(latency_seconds=0.5)
    order = model.place(1.0, 10.0, 3.0, 5.0)
    before_active = model.process_trade(
        order, 1.2, 10.0, 10.0, "sell", "buy"
    )
    assert before_active.filled_size == 0.0
    fill = model.process_trade(order, 2.0, 10.0, 5.0, "sell", "buy")
    assert fill.filled_size == pytest.approx(2.0)
    assert fill.remaining_queue == pytest.approx(0.0)


def test_queue_model_and_latency_are_integrated_in_event_backtest():
    def event(timestamp, trade_size=0.0, trade_price=None, side=None):
        return MarketEvent(
            timestamp=timestamp, instrument="OPT", fair_value=10.0,
            price_volatility=0.2, time_to_horizon=0.2,
            trade_price=trade_price, trade_size=trade_size, aggressor_side=side,
            market_bid=9.95, market_ask=10.05,
            market_bid_size=3.0, market_ask_size=4.0,
        )
    result = EventDrivenBacktest(
        quote_model=FixedSpreadQuoteModel(0.05),
        order_size=5.0,
        participation_rate=1.0,
        queue_model=L1QueueModel(latency_seconds=0.5),
    ).run([
        event(1.0),
        event(2.0, 5.0, 9.95, "sell"),
    ])
    assert len(result.fills) == 1
    assert result.fills[0].side == "buy"
    assert result.fills[0].size == pytest.approx(2.0)


def test_signed_markout_negative_means_adverse_selection():
    assert signed_markout("buy", 10.0, 9.8) == pytest.approx(-0.2)
    assert signed_markout("sell", 10.0, 10.2) == pytest.approx(-0.2)
