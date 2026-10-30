# Event-driven backtesting contract

## Event schema

Each MarketEvent contains:
- a numeric timestamp in Unix seconds;
- an instrument identifier;
- a fair value supplied by the pricing or market-data layer;
- annualized instrument-price volatility in price units per square-root year;
- time remaining to the quoting horizon in years;
- optionally, one trade print with price, size, and aggressor side.

Events must be supplied in non-decreasing timestamp order. Equal timestamps are
processed in input order, so callers must define a deterministic tie-break
when multiple instruments or event types share a timestamp.

## State-transition order

For each event, the engine performs these operations in order:

1. Match the event's trade print against the quote resting from the previous
   event for that instrument.
2. Cap the candidate fill by configured order size, the participation fraction
   of the reported trade size, and the remaining absolute inventory capacity.
3. Apply the signed fill to inventory and average-cost P&L.
4. Recompute the instrument's quote using the current fair value and updated
   inventory, then rest that quote for the next event.

The first event for an instrument can only establish its first quote; it cannot
fill against a quote that did not exist before that event. This avoids
same-event look-ahead.

## Trade-print fill convention

A buy-aggressor trade at or above our resting ask is eligible to fill our ask.
A sell-aggressor trade at or below our resting bid is eligible to fill our bid.
The simulated fill occurs at our resting quote price.

Eligible fill size is:

    min(order_size, trade_size * participation_rate, inventory_headroom)

This is a deliberately simplified participation model. A consolidated trade
print does not reveal how much volume was available at our queue position.
The participation fraction should therefore be treated as a scenario
parameter, not a measured fill probability.

## Inventory and P&L

The engine prevents fills that would move absolute instrument inventory beyond
the configured per-instrument limit. P&L uses the existing average-cost
accounting and marks remaining positions to the last supplied fair value for
each instrument. Fees, rebates, contract multipliers, funding, and exercise or
assignment cash flows are not yet included.

## Important limitations

The engine does not model order-book depth, queue priority, cancellations,
latency, hidden liquidity, market impact, adverse selection, or exchange
matching rules. It is a deterministic event-replay framework for testing
state transitions and sensitivity to simple fill assumptions. It is not a
production-grade execution simulator and does not establish strategy
profitability.
