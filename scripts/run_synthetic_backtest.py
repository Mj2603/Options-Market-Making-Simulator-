"""Run a deterministic synthetic event-driven market-making example.

This script demonstrates the simulator mechanics only. The synthetic events
are not historical market data and the resulting P&L is not a performance
estimate.
"""
from options_mm.market.avellaneda_stoikov import AvellanedaStoikovQuoteModel
from options_mm.metrics.pnl import PnLManager
from options_mm.risk.inventory import InventoryManager
from options_mm.simulation import EventDrivenBacktest, MarketEvent


def run_demo():
    model = AvellanedaStoikovQuoteModel(
        risk_aversion=0.05,
        order_arrival_intensity=1.5,
    )
    volatility = 0.8
    horizon = 0.25
    instrument = "SYNTH-100-C"

    quote_at_zero = model.quote(2.50, 0.0, volatility, horizon)
    quote_at_short_five = model.quote(2.50, -5.0, volatility, horizon)
    quote_at_short_two = model.quote(2.48, -2.0, volatility, horizon)

    events = [
        MarketEvent(
            timestamp=1.0,
            instrument=instrument,
            fair_value=2.50,
            price_volatility=volatility,
            time_to_horizon=horizon,
        ),
        MarketEvent(
            timestamp=2.0,
            instrument=instrument,
            fair_value=2.50,
            price_volatility=volatility,
            time_to_horizon=horizon,
            trade_price=quote_at_zero.ask,
            trade_size=50.0,
            aggressor_side="buy",
        ),
        MarketEvent(
            timestamp=3.0,
            instrument=instrument,
            fair_value=2.48,
            price_volatility=volatility,
            time_to_horizon=horizon,
            trade_price=quote_at_short_five.bid,
            trade_size=30.0,
            aggressor_side="sell",
        ),
        MarketEvent(
            timestamp=4.0,
            instrument=instrument,
            fair_value=2.52,
            price_volatility=volatility,
            time_to_horizon=horizon,
            trade_price=quote_at_short_two.ask,
            trade_size=40.0,
            aggressor_side="buy",
        ),
        MarketEvent(
            timestamp=5.0,
            instrument=instrument,
            fair_value=2.50,
            price_volatility=volatility,
            time_to_horizon=horizon,
        ),
    ]

    engine = EventDrivenBacktest(
        quote_model=model,
        inventory_manager=InventoryManager(max_position=20.0),
        pnl_manager=PnLManager(
            commission_per_contract=0.65,
            contract_multipliers={instrument: 100.0},
        ),
        order_size=5.0,
        participation_rate=0.1,
        quantity_step=1.0,
    )
    return engine.run(events)


def main() -> None:
    result = run_demo()
    print("Synthetic event-driven market-making example")
    print("Fills:")
    for fill in result.fills:
        print(
            f"  t={fill.timestamp:.0f} {fill.side:4s} "
            f"{fill.size:.0f} @ {fill.price:.4f}"
        )
    print(f"Final positions: {dict(result.final_positions)}")
    print(f"Gross P&L: {result.gross_total_pnl:.2f}")
    print(f"Fees paid: {result.fees_paid:.2f}")
    print(f"Net P&L: {result.net_total_pnl:.2f}")
    print("Synthetic illustration only; not a strategy performance result.")


if __name__ == "__main__":
    main()
