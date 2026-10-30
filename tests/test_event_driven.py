import pytest

from options_mm.market.avellaneda_stoikov import AvellanedaStoikovQuoteModel
from options_mm.metrics.pnl import PnLManager
from options_mm.risk.inventory import InventoryManager
from options_mm.simulation.event_driven import EventDrivenBacktest, MarketEvent


def event(timestamp, **kwargs):
    defaults = {
        "timestamp": timestamp,
        "instrument": "OPT-100-C",
        "fair_value": 10.0,
        "price_volatility": 0.5,
        "time_to_horizon": 0.25,
    }
    defaults.update(kwargs)
    return MarketEvent(**defaults)


def test_first_event_posts_quotes_and_second_event_can_fill_resting_ask():
    model = AvellanedaStoikovQuoteModel(
        risk_aversion=0.1, order_arrival_intensity=1.5
    )
    first = event(1.0)
    initial_quote = model.quote(10.0, 0.0, 0.5, 0.25)
    second = event(
        2.0,
        trade_price=initial_quote.ask,
        trade_size=100.0,
        aggressor_side="buy",
    )

    result = EventDrivenBacktest(
        quote_model=model, order_size=5.0, participation_rate=0.5
    ).run([first, second])

    assert len(result.fills) == 1
    fill = result.fills[0]
    assert fill.side == "sell"
    assert fill.price == pytest.approx(initial_quote.ask)
    assert fill.size == pytest.approx(5.0)
    assert dict(result.final_positions)["OPT-100-C"] == pytest.approx(-5.0)


def test_sell_aggressor_fills_resting_bid_and_updates_inventory():
    model = AvellanedaStoikovQuoteModel()
    bid = model.quote(10.0, 0.0, 0.5, 0.25).bid
    result = EventDrivenBacktest(order_size=4.0, participation_rate=0.5).run(
        [
            event(1.0),
            event(
                2.0,
                trade_price=bid,
                trade_size=20.0,
                aggressor_side="sell",
            ),
        ]
    )
    assert len(result.fills) == 1
    assert result.fills[0].side == "buy"
    assert result.fills[0].size == pytest.approx(4.0)
    assert dict(result.final_positions)["OPT-100-C"] == pytest.approx(4.0)


def test_trade_that_does_not_cross_resting_quote_does_not_fill():
    result = EventDrivenBacktest().run(
        [
            event(1.0),
            event(
                2.0,
                trade_price=10.0,
                trade_size=100.0,
                aggressor_side="buy",
            ),
        ]
    )
    assert result.fills == ()


def test_inventory_limit_caps_partial_fill():
    inventory = InventoryManager(max_position=3.0)
    result = EventDrivenBacktest(
        inventory_manager=inventory,
        order_size=2.0,
        participation_rate=1.0,
    ).run(
        [
            event(1.0),
            event(
                2.0,
                trade_price=0.0,
                trade_size=2.0,
                aggressor_side="sell",
            ),
            event(
                3.0,
                trade_price=0.0,
                trade_size=100.0,
                aggressor_side="sell",
            ),
        ]
    )
    assert [fill.size for fill in result.fills] == pytest.approx([2.0, 1.0])
    assert dict(result.final_positions)["OPT-100-C"] == pytest.approx(3.0)


def test_out_of_order_events_are_rejected():
    with pytest.raises(ValueError, match="sorted"):
        EventDrivenBacktest().run([event(2.0), event(1.0)])


def test_engine_cannot_be_reused_for_a_second_run():
    engine = EventDrivenBacktest()
    engine.run([event(1.0)])
    with pytest.raises(RuntimeError, match="only run once"):
        engine.run([event(2.0)])


@pytest.mark.parametrize(
    "kwargs",
    [
        {"trade_size": 1.0},
        {"trade_size": -1.0},
        {"trade_size": 1.0, "trade_price": 10.0},
        {"trade_size": 1.0, "trade_price": 10.0, "aggressor_side": "other"},
    ],
)
def test_invalid_trade_events_are_rejected(kwargs):
    with pytest.raises(ValueError):
        event(1.0, **kwargs)


def test_pnl_is_marked_to_last_fair_value():
    model = AvellanedaStoikovQuoteModel()
    ask = model.quote(10.0, 0.0, 0.5, 0.25).ask
    result = EventDrivenBacktest(
        quote_model=model, order_size=2.0, participation_rate=1.0
    ).run(
        [
            event(1.0),
            event(
                2.0,
                trade_price=ask,
                trade_size=2.0,
                aggressor_side="buy",
            ),
            event(3.0, fair_value=9.0),
        ]
    )
    assert result.realized_pnl == pytest.approx(0.0)
    assert result.unrealized_pnl == pytest.approx(2.0 * (ask - 9.0))
    assert result.total_pnl == pytest.approx(result.realized_pnl + result.unrealized_pnl)


def test_quantity_step_rounds_fill_down_to_valid_lot():
    result = EventDrivenBacktest(
        order_size=10.0,
        participation_rate=1.0,
        quantity_step=0.25,
    ).run(
        [
            event(1.0),
            event(
                2.0,
                trade_price=0.0,
                trade_size=1.13,
                aggressor_side="sell",
            ),
        ]
    )
    assert len(result.fills) == 1
    assert result.fills[0].size == pytest.approx(1.0)


def test_invalid_quantity_step_is_rejected():
    with pytest.raises(ValueError, match="quantity_step"):
        EventDrivenBacktest(quantity_step=0.0)


def test_first_event_cannot_fill_against_a_quote_not_yet_posted():
    result = EventDrivenBacktest().run(
        [
            event(
                1.0,
                trade_price=0.0,
                trade_size=100.0,
                aggressor_side="sell",
            )
        ]
    )
    assert result.fills == ()


def test_inventory_limit_also_caps_sell_fills_for_short_positions():
    inventory = InventoryManager(max_position=3.0)
    model = AvellanedaStoikovQuoteModel()
    ask_at_zero_inventory = model.quote(10.0, 0.0, 0.5, 0.25).ask
    ask_at_short_inventory = model.quote(10.0, -2.0, 0.5, 0.25).ask
    result = EventDrivenBacktest(
        inventory_manager=inventory,
        order_size=2.0,
        participation_rate=1.0,
    ).run(
        [
            event(1.0),
            event(
                2.0,
                trade_price=ask_at_zero_inventory,
                trade_size=2.0,
                aggressor_side="buy",
            ),
            event(
                3.0,
                trade_price=ask_at_short_inventory,
                trade_size=100.0,
                aggressor_side="buy",
            ),
        ]
    )
    assert [fill.size for fill in result.fills] == pytest.approx([2.0, 1.0])
    assert all(fill.side == "sell" for fill in result.fills)
    assert dict(result.final_positions)["OPT-100-C"] == pytest.approx(-3.0)


def test_non_finite_market_event_timestamp_is_rejected():
    with pytest.raises(ValueError, match="timestamp"):
        event(float("nan"))



def test_initial_inventory_and_pnl_state_must_match():
    inventory = InventoryManager(max_position=10.0)
    inventory.on_fill("OPT-100-C", 2.0)
    with pytest.raises(ValueError, match="must be consistent"):
        EventDrivenBacktest(inventory_manager=inventory)



def test_open_initial_position_requires_a_final_fair_value():
    inventory = InventoryManager(max_position=10.0)
    inventory.on_fill("OPT-100-C", 2.0)
    pnl = PnLManager()
    pnl.record_fill("OPT-100-C", 1.5, 2.0)
    engine = EventDrivenBacktest(
        inventory_manager=inventory,
        pnl_manager=pnl,
    )
    with pytest.raises(ValueError, match="missing final fair value"):
        engine.run([])



def test_simulation_result_reports_gross_and_net_pnl():
    model = AvellanedaStoikovQuoteModel()
    ask = model.quote(10.0, 0.0, 0.5, 0.25).ask
    pnl = PnLManager(
        commission_per_contract=0.5,
        contract_multipliers={"OPT-100-C": 100.0},
    )
    result = EventDrivenBacktest(
        quote_model=model,
        pnl_manager=pnl,
        order_size=2.0,
        participation_rate=1.0,
    ).run(
        [
            event(1.0),
            event(
                2.0,
                trade_price=ask,
                trade_size=2.0,
                aggressor_side="buy",
            ),
            event(3.0, fair_value=9.0),
        ]
    )
    assert result.fees_paid == pytest.approx(1.0)
    assert result.gross_total_pnl == pytest.approx(200.0 * (ask - 9.0))
    assert result.net_total_pnl == pytest.approx(result.gross_total_pnl - 1.0)
    assert result.total_pnl == pytest.approx(result.net_total_pnl)
