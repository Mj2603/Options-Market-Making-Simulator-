# Options Market-Making Simulator

A Python research prototype for studying the core mechanics of options market making: theoretical valuation, quote construction, simplified execution, inventory accounting, P&L attribution, and delta hedging.

The repository is organized as a modular simulation toolkit. It is intended for quantitative finance experimentation and software development practice—not live trading, broker connectivity, or production execution.

[![Python CI](https://github.com/Mj2603/Options-Market-Making-Simulator-/actions/workflows/python-ci.yml/badge.svg)](https://github.com/Mj2603/Options-Market-Making-Simulator-/actions/workflows/python-ci.yml)
[![CI](https://github.com/Mj2603/Options-Market-Making-Simulator-/actions/workflows/ci.yml/badge.svg)](https://github.com/Mj2603/Options-Market-Making-Simulator-/actions/workflows/ci.yml)

## Scope

The current implementation contains the following research components:

| Component | Current functionality |
|---|---|
| Option pricing | Unit-tested European Black–Scholes prices and Greeks, including continuous dividend yield; raw-SVI implied-volatility slices and surface-based valuation |
| Quote construction | Fixed-spread benchmark plus inventory-aware Avellaneda–Stoikov quoting with training-window calibration |
| Execution model | Event-driven trade-print fills, optional L1 queue-ahead and latency proxy, partial fills, discrete lots, and inventory caps |
| Inventory and portfolio risk | Per-instrument caps plus portfolio delta/gamma/vega/theta, gross concentration, and pre-trade limits |
| P&L | Average-cost accounting with contract multipliers, per-contract commissions, gross P&L, and net P&L |
| Delta hedging | Net option delta aggregation and theoretical underlying hedge quantity |
| Volatility | Causal EWMA estimator, threshold regime baseline, and calibrated raw-SVI surface interpolation |
| Data ingestion | CSV validation, Alpaca historical quote/trade downloader, causal normalization, and arrival-exposure panel |
| Synthetic data | Seeded generator for option quote/trade-print sessions (`random_walk`, `informed`, `trending`) and a small committed sample chain |


## Architecture

```text
CSV observations
      |
      v
Data validation and normalization
      |
      v
Black–Scholes valuation -----> Greeks
      |                         |
      v                         v
Fixed / inventory-aware quote models
      |
      v
Resting quotes <----- Event-driven replay
      |                       ^
      v                       |
Trade-print fill model -------+
      |
      +------> Inventory state and limits
      |
      +------> Realized / unrealized P&L

Greeks ---------------------> Delta hedge sizing

Returns --------------------> Volatility regime label
```

The main package is under `src/options_mm/`:

- `data/` — CSV ingestion, quote-data validation, and the deterministic synthetic generator (`data/synthetic.py`)
- `pricing/` — Black–Scholes pricing/Greeks, SVI volatility surfaces, and causal EWMA volatility
- `market/` — fixed-spread and inventory-aware bid/ask quote construction
- `execution/` — simplified order-fill rules, L1 queue-ahead proxy, latency, and maker-side markouts
- `simulation/` — ordered market-event replay, resting-quote matching, inventory-aware fill caps, and P&L snapshots
- `risk/` — inventory state, portfolio Greeks, concentration limits, and pre-trade checks
- `metrics/` — average-cost realized/unrealized P&L, contract multipliers, commissions, and net P&L
- `hedge/` — net-delta and hedge-quantity calculations
- `experiments/` — volatility regimes, arrival calibration panels, and expanding-window policy comparisons

## Installation

Requires Python 3.10, 3.11, or 3.12 (the `numpy<2` pin has no wheels for 3.13).

```bash
git clone https://github.com/Mj2603/Options-Market-Making-Simulator-.git
cd Options-Market-Making-Simulator-

python -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
pip install -e ".[parquet]"
pip install -r requirements-dev.txt
```

For a CSV-only installation, install the package without the optional Parquet extra:

```bash
pip install -e .
```

## Tests

Run the automated test suite from the repository root:

```bash
pytest
```

GitHub Actions runs the suite on Python 3.10, 3.11, and 3.12. The tests include smoke runs of the scripts documented below, so every command in this README is exercised by CI.

## Quick start (no external data required)

All commands run from the repository root after installation.

```bash
# Black-Scholes prices/Greeks for the committed SYNTHETIC sample chain (data/sample_ticks.csv)
python scripts/run_phase1.py

# Pricing / quoting micro-benchmarks on the same sample
python benchmarks/benchmark_simulator.py

# Hand-constructed event-driven example: fills, inventory cap, multiplier 100, $0.65 commission
python scripts/run_synthetic_backtest.py

# One walk-forward comparison on a generated SYNTHETIC session
python scripts/run_walk_forward.py --synthetic random_walk --seed 0

# The full multi-seed SYNTHETIC experiment (about 1.5 minutes; writes results/)
python scripts/run_synthetic_experiment.py
```

`data/sample_ticks.csv` is synthetic and is regenerated byte-for-byte with
`python scripts/generate_synthetic_data.py`. The same script writes a synthetic
research-event CSV and arrival panel in the real-data format with
`--research-events {random_walk,informed,trending}` (output in `data/synthetic/`).

### Contract multiplier and commissions

P&L is `price change x quantity x multiplier`, and commissions are charged per
contract. The engine's default multiplier is **1.0**, which is only right for
unit-sized instruments: with a 1.0 multiplier and a $0.65 commission, a few
cents of captured spread are swamped by fees. US equity options use **100**.
Set it explicitly, either per event (`MarketEvent(contract_multiplier=100.0)`,
which the Alpaca normalizer and the synthetic generator both do) or on the
P&L manager:

```python
from options_mm.metrics.pnl import PnLManager
from options_mm.simulation import EventDrivenBacktest
from options_mm.market.policies import FixedSpreadQuoteModel

engine = EventDrivenBacktest(
    quote_model=FixedSpreadQuoteModel(half_spread=0.05),
    pnl_manager=PnLManager(
        commission_per_contract=0.65,
        contract_multipliers={"SYNTH-C100": 100.0},
    ),
)
```

## SYNTHETIC walk-forward results

> **Synthetic data only.** These numbers describe how the two quoting policies
> behave inside this simulator under the generator's assumptions. They are not
> evidence of profitability on real markets. Full report, setup, and caveats:
> [results/synthetic_walkforward.md](results/synthetic_walkforward.md); per-seed
> rows: [results/synthetic_walkforward_seeds.csv](results/synthetic_walkforward_seeds.csv).

Setup: 20 seeds per scenario, one 6.5-hour session per seed (4,680 events), a
30-day ATM call on a GBM underlying, trade-print distances Exponential(k=12),
multiplier 100, $0.65 per contract, 3 expanding-window folds with a 0.6
initial training fraction. k is fitted by Poisson MLE and gamma / the fixed
half-spread are grid-searched on each training window; only out-of-sample test
folds are counted. Net P&L in $, summed over the three test folds of each seed.

| Scenario | Policy | Total net P&L | Median / seed | Std / seed | Sharpe-like (mean/std) | Mean max abs inventory |
|---|---|---:|---:|---:|---:|---:|
| random_walk | Fixed spread | 46,257 | 2,255 | 497 | 4.65 | 23.7 |
| random_walk | A-S | 47,206 | 2,361 | 324 | 7.29 | 17.9 |
| informed | Fixed spread | 41,232 | 2,086 | 496 | 4.16 | 20.6 |
| informed | A-S | 41,510 | 2,036 | 366 | 5.67 | 16.1 |
| trending | Fixed spread | 17,102 | 1,102 | 637 | 1.34 | 13.1 |
| trending | A-S | 31,650 | 1,672 | 625 | 2.53 | 17.1 |

| Scenario | A-S wins | Mean A-S minus fixed / seed | Std error | 95% bootstrap CI |
|---|---:|---:|---:|---:|
| random_walk | 11/20 | +47 | 68 | [-80, 180] |
| informed | 9/20 | +14 | 73 | [-117, 162] |
| trending | 19/20 | +727 | 101 | [535, 923] |

What this supports:

- Under random-walk and informed flow, A-S and the tuned fixed spread earn
  statistically indistinguishable net P&L (the 95% CIs contain zero); A-S shows
  lower per-seed P&L dispersion and about 20-25% lower peak inventory.
- Under trending prices with one-sided flow, A-S beats the fixed spread in
  19/20 seeds (+85% total net P&L), largely because the tuned fixed spread
  widens to the edge of its grid (0.2, selected in every trending fold) and
  fills about a quarter as often. A-S does not hold less peak inventory in that
  scenario.
- Training-window selection recovers the generating k (mean fitted k 12.07 vs
  12) and mostly picks the smallest gamma in the grid (0.01), so a wider grid
  could change the comparison.
- The arrival model A-S calibrates is the model that generated the data, which
  favours A-S. Results on real option data have not been produced in this
  repository.

## Historical data and research pipeline

The repository includes a paginated Alpaca historical options downloader, a
backward-as-of quote/trade normalizer, an arrival-calibration panel builder,
and a walk-forward runner. Raw market data are not committed, and running
this path requires Alpaca API keys. Without the processed files,
`run_walk_forward.py` exits with a message pointing to these steps and to
`--synthetic`.

The complete setup and assumptions are documented in
[docs/research_framework.md](docs/research_framework.md).

```bash
# 1. Set APCA_API_KEY_ID and APCA_API_SECRET_KEY in the shell.
python scripts/download_alpaca_options.py \
  --symbols "AAPL260116C00100000,AAPL260116P00100000" \
  --start "2026-01-02T14:30:00Z" --end "2026-01-02T21:00:00Z" \
  --feed indicative

# 2. Supply the correct New York settlement time for these contracts
#    (the normalizer's --contract-multiplier defaults to 100).
python scripts/prepare_alpaca_research_data.py --settlement-time 16:00:00

# 3. Build a training calibration panel.
python scripts/build_arrival_panel.py

# 4. Compare both policies out of sample.
python scripts/run_walk_forward.py --splits 3 --train-fraction 0.6
```

The data normalizer estimates option-premium volatility with a causal EWMA
and infers trade aggressor side from midpoint/tick rules.

## Market-data contract

The canonical CSV loader expects these columns:

```text
timestamp, expiry, underlying, strike, bid, ask
```

Optional columns such as `iv`, `option_type`, `bid_size`, and `ask_size` are
retained. Date-only expiries require an explicit `expiry_time`.

## Research limitations

This is an intentionally limited research prototype:

- **No real-data results.** The only committed performance numbers come from
  the synthetic generator. Its exponential trade-through model is the same
  model the A-S policy calibrates, fair value and premium volatility are known
  exactly, and each seed is a single session of one contract.
- The arrival model is calibrated from a Poisson composite-likelihood panel of trade-through events. Its price-sensitivity parameter is fitted from data; risk aversion is selected on the training window by a declared P&L/inventory objective. The calibration is not an exchange fill-probability model.
- Fills are a participation fraction of trade prints that cross the resting quote. The optional L1 queue model initializes queue ahead from displayed NBBO size and applies configurable latency. It does not reconstruct order-level queue changes, cancellations, hidden liquidity, full depth, exchange routing, or cancel/replace races. It is a sensitivity proxy, not exchange-level execution.
- The event-driven engine caps fills so simulated positions remain within the configured absolute inventory limit. The standalone execution API is not wired into a comprehensive order-management or pre-trade risk-control system.
- P&L supports contract multipliers (default 1.0; set 100 for US equity options) and per-contract commissions. It omits exchange rebates, clearing/regulatory fees, funding, exercise/assignment cash flows, and corporate actions. Delta hedges are sized but not executed or costed in the event engine.
- The SVI surface is a raw-SVI interpolation baseline and does not guarantee calendar or butterfly arbitrage freedom. The EWMA estimator is a simple causal forecast, not a stochastic-volatility model. Black–Scholes valuation is European and does not model American exercise or discrete dividends.
- The data normalizer infers aggressor side from trade price versus midpoint and a tick rule. Its option-premium EWMA is a proxy. Adjusted contracts, AM-settled contracts, and non-standard multipliers require explicit contract metadata.
- Walk-forward tests prevent training/test timestamp overlap, but results are only meaningful with a sufficiently long, representative historical sample, reliable fees, and vendor-quality quote/trade data. A passing unit-test suite does not establish trading profitability or production readiness.

The project should not be connected to a live brokerage account or used to make trading decisions.
