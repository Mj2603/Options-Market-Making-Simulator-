# Quantitative research and walk-forward framework

## Experimental protocol

The framework compares two policies under the same event stream and
execution assumptions:

1. Fixed half-spread quoting.
2. Inventory-aware Avellaneda–Stoikov quoting.

At each expanding-window fold:

1. Fit the exponential arrival model using arrival-panel observations whose
   timestamps are no later than the training cutoff.
2. Select A-S risk aversion from the configured grid by maximizing training
   net P&L less a configurable inventory penalty.
3. Select the fixed half-spread from its own configured grid using the same
   training objective.
4. Freeze both parameter sets.
5. Evaluate both policies on the strictly later test window.
6. Report net/gross P&L, fees, daily Sharpe, max drawdown, fill diagnostics,
   inventory exposure, and post-fill markouts.

The test fold is not used for parameter selection. The calibration panel must
be timestamped and derived from the same underlying market history. The
arrival model is a Poisson composite-likelihood fit to trade-through counts;
it is not an exchange fill-probability estimate.

## Run the experiment

First download and normalize data as described in
[data_sources.md](data_sources.md), then build the arrival panel:

```bash
python scripts/run_walk_forward.py \
  --events data/processed/research_events.csv \
  --arrival-panel data/processed/arrival_panel.csv \
  --splits 3 \
  --train-fraction 0.6 \
  --gamma-grid 0.01,0.03,0.1,0.3,1.0 \
  --fixed-spread-grid 0.01,0.02,0.05,0.1,0.2 \
  --commission-per-contract 0.65 \
  --inventory-penalty 0.01 \
  --queue-aware \
  --latency-seconds 0.05
```

All cost, lot-size, and multiplier assumptions must be checked against the
specific contract and venue. The commission argument is a per-contract
commission only; exchange fees, rebates, clearing fees, regulatory fees,
slippage, and funding are not automatically included.

## Metrics and interpretation

- **Net P&L:** gross realized plus unrealized P&L, less configured commissions.
- **Daily Sharpe:** computed from daily last marked equity observations. It is
  not a high-frequency Sharpe. A short sample can produce an uninformative
  estimate.
- **Maximum drawdown:** peak-to-trough drawdown of daily marked equity.
- **Fill count / eligible prints:** diagnostic ratios, not true fill
  probabilities when trade prints are used as proxies.
- **Inventory:** maximum and average absolute position after fills.
- **Markout:** maker-side signed price change at 1, 5, and 30 seconds (first
  available observation after each horizon). Negative values indicate adverse
  selection. If the feed is sampled more coarsely than the horizon, the result
  is not meaningful.
- **Fees:** the configured commission model only.

The selected risk aversion is a training-window hyperparameter selected under
an explicit P&L/inventory objective. It is not a parameter statistically
identified by the arrival model. The inventory penalty is in P&L units per
squared contract and must be declared before running the experiment.

## Volatility surface

`SVIVolatilitySurface.fit` accepts arrays of expiry in years, forward, strike,
and implied volatility. It fits a raw-SVI slice per expiry and interpolates
total variance across maturities. The fit reports residual error and minimum
variance diagnostics but does not enforce all butterfly/calendar arbitrage
conditions. It must not be described as an arbitrage-free surface.

`price_with_surface` passes the queried implied volatility into the
Black–Scholes European pricing implementation. The forward, spot, rate,
settlement clock, and implied-volatility convention must be internally
consistent. American exercise, discrete dividends, borrow, and early exercise
are not implemented.

`EWMAVolatility` is a causal return-volatility estimator. It is a baseline
forecast, not a stochastic-volatility model. For options, use the surface or a
validated mapping from underlying volatility to option-premium volatility;
do not substitute underlying percentage volatility directly into the
Avellaneda–Stoikov price-volatility input.

## Execution model hierarchy

The default event engine uses trade-through participation fills. The optional
`L1QueueModel`:
- waits until configured quote latency has elapsed;
- initializes queue-ahead volume from displayed NBBO size when our quote joins
  at the same price;
- assumes zero queue ahead when our quote improves the NBBO;
- refuses fills when our quote is behind the NBBO because depth at that price
  is unobserved;
- consumes reported trade volume ahead of the order before filling our size.

This is a conservative L1 queue proxy, not a full depth/order-level replay.
It does not reconstruct cancellations, hidden liquidity, exchange routing,
order acknowledgements, replace/cancel races, or queue position changes from
individual order messages. The latency model cancels/replaces immediately and
activates the new quote after the configured delay; it is a sensitivity
assumption, not a measured venue latency distribution.

## Portfolio risk

`PortfolioRiskManager` aggregates delta, gamma, vega, theta, gross market
value, and underlying concentration. When supplied to `EventDrivenBacktest`,
it checks each candidate fill against the configured portfolio limits before
updating inventory and P&L. The event stream must carry current underlying and
Greeks for every fill. The delta hedge helper returns the theoretical
underlying quantity needed to neutralize net option delta. It does not submit
or simulate an underlying hedge order, so hedge slippage and hedge costs are
not included.
