# Options Market-Making Simulator

A Python research prototype for studying the core mechanics of options market making: theoretical valuation, quote construction, simplified execution, inventory accounting, P&L attribution, and delta hedging.

The repository is organized as a modular simulation toolkit. It is intended for quantitative finance experimentation and software development practice—not live trading, broker connectivity, or production execution.

[![Python CI](https://github.com/Mj2603/Options-Market-Making-Simulator-/actions/workflows/python-ci.yml/badge.svg)](https://github.com/Mj2603/Options-Market-Making-Simulator-/actions/workflows/python-ci.yml)
[![CI](https://github.com/Mj2603/Options-Market-Making-Simulator-/actions/workflows/ci.yml/badge.svg)](https://github.com/Mj2603/Options-Market-Making-Simulator-/actions/workflows/ci.yml)

## Scope

The current implementation contains the following research components:

| Component | Current functionality |
|---|---|
| Option pricing | Black–Scholes European call/put prices and first-order/second-order Greeks |
| Quote construction | Fixed-spread baseline plus an inventory-aware Avellaneda–Stoikov reservation-price model |
| Execution model | Deterministic order rules plus event-driven trade-print matching with configurable participation, discrete quantity steps, and inventory caps |
| Inventory | Per-instrument position tracking, limit checks, and fill-size caps in the event-driven engine |
| P&L | Average-cost realized P&L and mark-to-market unrealized P&L |
| Delta hedging | Net option delta aggregation and theoretical underlying hedge quantity |
| Volatility regime | Threshold-based classification using the standard deviation of supplied returns |
| Data ingestion | CSV validation, row-specific time-to-expiry, quote filtering, and mid/spread derivation |

The modules are deliberately separated so that individual models can be tested and replaced as the simulator becomes more realistic.

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
- `pricing/` — Black–Scholes pricing and Greeks
- `market/` — fixed-spread and inventory-aware bid/ask quote construction
- `execution/` — simplified order-fill rules
- `simulation/` — ordered market-event replay, resting-quote matching, inventory-aware fill caps, and P&L snapshots
- `risk/` — inventory state and position-limit checks
- `metrics/` — realized and mark-to-market P&L
- `hedge/` — net-delta and hedge-quantity calculations
- `experiments/` — basic volatility-regime experiments

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

## Market-data contract

The canonical CSV loader expects these columns:

```text
timestamp, expiry, underlying, strike, bid, ask
```

Optional source fields (for example implied volatility or displayed sizes) are retained. The loader validates required fields and market values, calculates time-to-expiry for each observation, filters crossed and expired quotes, and derives midpoint and quoted spread.

If `expiry` contains date-only values, pass the contract's actual settlement time through `expiry_time`. Do not assume a universal expiry convention: AM- and PM-settled contracts can have materially different time-to-expiry.

No historical market-data file is bundled with this repository. The loader can be tested using the synthetic fixtures in `tests/test_loader.py`. A real-data research run requires a correctly mapped dataset and documented contract metadata.

## Research limitations

This is an intentionally limited research prototype. In particular:

- The Avellaneda–Stoikov module now skews quotes for signed inventory and widens the model spread with price volatility and remaining horizon. It assumes constant volatility and exponential order arrivals; its intensity parameter is not calibrated from data. It does not model queue position, adverse selection, or market impact.
- The event-driven simulator matches trade prints against quotes resting from the prior event and applies a configurable participation fraction. It supports partial fills through trade-size and order-size caps, but does not simulate queue priority, full order-book depth, latency, cancellations, market impact, or adverse selection. Its fill assumptions are a sensitivity model, not exchange-level execution.
- The event-driven engine caps fills so simulated positions remain within the configured absolute inventory limit. The standalone execution API is still not wired into a comprehensive order-management or pre-trade risk-control system.
- P&L accounting is simplified and does not yet include exchange fees, rebates, contract multipliers, funding, exercise/assignment, or corporate actions.
- Pricing is European Black–Scholes only. Input domains and deterministic zero-volatility / expiry cases are validated, but the implementation does not calibrate an implied-volatility surface or model stochastic volatility.
- The regime detector is a simple threshold baseline, not a validated forecasting model.
- A passing unit-test suite verifies the tested software behavior. It does not establish trading profitability, execution quality, or production readiness.

Consequently, the project should not be connected to a live brokerage account or used to make trading decisions.

## Roadmap

The next engineering priorities are:

1. Extend risk controls to all order-entry paths and add portfolio-level Greeks and concentration limits.
2. Calibrate quote-model parameters on training data and evaluate them out of sample against the fixed-spread baseline.
3. Add transaction costs, contract multipliers, and independently reconciled net P&L.
4. Add realistic order-book replay, queue priority, cancellations, and latency only when suitable message-level data is available.
5. Build walk-forward experiments with benchmark policies, parameter controls, and leakage-safe evaluation.
6. Add structured logging, configuration, data provenance, and reproducible experiment outputs.
7. Add option-surface calibration and dynamic volatility inputs before claiming options-specific market-making performance.

## Project status

The project is under active development as a quantitative research and engineering portfolio project. The current goal is correctness, transparency of assumptions, and reproducibility—not a claim of institutional-grade or production trading infrastructure.
