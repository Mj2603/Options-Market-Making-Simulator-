# Options Market-Making Simulator

A Python research prototype for studying the core mechanics of options market making: theoretical valuation, quote construction, simplified execution, inventory accounting, P&L attribution, and delta hedging.

The repository is organized as a modular simulation toolkit. It is intended for quantitative finance experimentation and software development practice—not live trading, broker connectivity, or production execution.

[![Python CI](https://github.com/Mj2603/Options-Market-Making-Simulator-/actions/workflows/python-ci.yml/badge.svg)](https://github.com/Mj2603/Options-Market-Making-Simulator-/actions/workflows/python-ci.yml)
[![CI](https://github.com/Mj2603/Options-Market-Making-Simulator-/actions/workflows/ci.yml/badge.svg)](https://github.com/Mj2603/Options-Market-Making-Simulator-/actions/workflows/ci.yml)

## Scope

The current implementation contains the following research components:

| Component | Current functionality |
|---|---|
| Option pricing | Validated European Black–Scholes prices and Greeks, including continuous dividend yield; raw-SVI implied-volatility slices and surface-based valuation |
| Quote construction | Fixed-spread benchmark plus inventory-aware Avellaneda–Stoikov quoting with training-window calibration |
| Execution model | Event-driven trade-print fills, optional L1 queue-ahead and latency proxy, partial fills, discrete lots, and inventory caps |
| Inventory and portfolio risk | Per-instrument caps plus portfolio delta/gamma/vega/theta, gross concentration, and pre-trade limits |
| P&L | Average-cost accounting with contract multipliers, per-contract commissions, gross P&L, and net P&L |
| Delta hedging | Net option delta aggregation and theoretical underlying hedge quantity |
| Volatility | Causal EWMA estimator, threshold regime baseline, and calibrated raw-SVI surface interpolation |
| Data ingestion | CSV validation, Alpaca historical quote/trade downloader, causal normalization, and arrival-exposure panel |


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

- `data/` — CSV ingestion and quote-data validation
- `pricing/` — Black–Scholes pricing/Greeks, SVI volatility surfaces, and causal EWMA volatility
- `market/` — fixed-spread and inventory-aware bid/ask quote construction
- `execution/` — simplified order-fill rules, L1 queue-ahead proxy, latency, and maker-side markouts
- `simulation/` — ordered market-event replay, resting-quote matching, inventory-aware fill caps, and P&L snapshots
- `risk/` — inventory state, portfolio Greeks, concentration limits, and pre-trade checks
- `metrics/` — average-cost realized/unrealized P&L, contract multipliers, commissions, and net P&L
- `hedge/` — net-delta and hedge-quantity calculations
- `experiments/` — volatility regimes, arrival calibration panels, and expanding-window policy comparisons

## Installation

Requires Python 3.10 or later.

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

GitHub Actions currently tests the project on Python 3.10, 3.11, and 3.12. The workflows install the package and test dependencies before running pytest.

## Historical data and research pipeline

The repository includes a paginated Alpaca historical options downloader, a
backward-as-of quote/trade normalizer, an arrival-calibration panel builder,
and a walk-forward runner. Raw market data are not committed. 

The complete setup and assumptions are documented in
[docs/research_framework.md](docs/research_framework.md).

```bash
# 1. Set APCA_API_KEY_ID and APCA_API_SECRET_KEY in the shell.
python scripts/download_alpaca_options.py \
  --symbols "AAPL260116C00100000,AAPL260116P00100000" \
  --start "2026-01-02T14:30:00Z" --end "2026-01-02T21:00:00Z" \
  --feed indicative

# 2. Supply the correct New York settlement time for these contracts.
python scripts/prepare_alpaca_research_data.py --settlement-time 16:00:00

# 3. Build a training calibration panel.
python scripts/build_arrival_panel.py

# 4. Compare both policies out of sample.
python scripts/run_walk_forward.py --splits 3 --train-fraction 0.6
```

The data normalizer estimates option-premium volatility with a causal EWMA
and infers trade aggressor side from midpoint/tick rules.

## Synthetic event-driven example

Run the deterministic example from the repository root:

```bash
python scripts/run_synthetic_backtest.py
```

The example demonstrates quote updates, trade-print matching, partial fills,
inventory limits, contract multipliers, commissions, and gross/net P&L. It uses
hand-constructed synthetic events

## Market-data contract

The canonical CSV loader expects these columns:

```text
timestamp, expiry, underlying, strike, bid, ask
```
