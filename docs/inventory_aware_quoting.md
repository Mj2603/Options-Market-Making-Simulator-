# Inventory-aware quoting: Avellaneda–Stoikov baseline

## Purpose

The fixed-spread quote engine is retained as a transparent benchmark. The
inventory-aware model adds a separate baseline so that the effect of inventory
skew and risk-sensitive spread widening can be tested without changing the
legacy quote API.

## Model

Let:

- m be the current theoretical fair value of the instrument;
- q be signed inventory (long is positive);
- gamma be the positive risk-aversion parameter;
- sigma be the annualized standard deviation of the instrument's price change,
  expressed in price units per square-root year;
- tau be the time remaining to the quoting horizon, in years;
- k be the positive exponential order-arrival intensity parameter.

The reservation price is

    r = m - q * gamma * sigma^2 * tau

and the optimal half-spread under the simplified model is

    h = 0.5 * gamma * sigma^2 * tau
        + (1 / gamma) * log(1 + gamma / k)

The unbounded model quotes are r - h and r + h. Since option prices cannot be
negative, the implementation floors the bid at zero and prevents the ask from
falling below the bid.

## Interpretation

Positive inventory lowers the reservation price and shifts both quotes down,
making sells more competitive and buys less competitive. Negative inventory
does the reverse. Higher price volatility or a longer horizon increases the
risk component of the spread. The arrival-intensity term controls the
liquidity component.

## Input units and option caveat

The volatility input is the volatility of the quoted instrument's price, not
the underlying's percentage volatility. For an option, a local first-order
approximation may use absolute option-price volatility approximately equal to
absolute delta times underlying spot times underlying percentage volatility.
That approximation ignores gamma, volatility-surface dynamics, jumps, and
changes in delta. It must not be treated as a calibrated option-price process.

Time is measured in years. Inventory is a signed number of instrument units.
The model parameters must be estimated or selected using training data only
before any out-of-sample strategy evaluation.

## Assumptions and exclusions

This implementation assumes constant price volatility, constant exponential
order-arrival intensity, continuous quote updates, and a simplified terminal
inventory penalty. It does not model order-book queue priority, fill sizes,
partial fills, cancellations, latency, adverse selection, market impact,
transaction costs, or parameter calibration. It is therefore a research
baseline, not evidence of profitability or a production execution model.

## Validation

The unit tests check symmetry at zero inventory, the direction of inventory
skew, spread monotonicity in volatility and horizon, zero-volatility and
zero-horizon behaviour, numerical stability, and invalid-input rejection.
