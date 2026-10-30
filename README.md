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
| Execution model | Deterministic touch/cross fill rules for marketable and limit orders |
| Inventory | Per-instrument position tracking and limit checks |
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
Fixed / inventory-aware quote models   Delta hedge sizing
      |
      v
Simplified execution rules
      |
      +------> Inventory state
      |
      +------> Realized / unrealized P&L

Returns --------------------> Volatility regime label
```

The main package is under `src/options_mm/`:

- `data/` — CSV ingestion and quote-data validation
- `pricing/` — Black–Scholes pricing and Greeks
- `market/` — fixed-spread and inventory-aware bid/ask quote construction
- `execution/` — simplified order-fill rules
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
- The execution model is deterministic and does not simulate queue priority, order-book depth, partial fills, latency, cancellations, or market impact.
- Inventory limits are exposed as checks; the current execution flow does not provide a complete pre-trade risk-control layer.
- P&L accounting is simplified and does not yet include exchange fees, rebates, contract multipliers, funding, exercise/assignment, or corporate actions.
- Pricing is European Black–Scholes only. Input domains and deterministic zero-volatility / expiry cases are validated, but the implementation does not calibrate an implied-volatility surface or model stochastic volatility.
- The regime detector is a simple threshold baseline, not a validated forecasting model.
- A passing unit-test suite verifies the tested software behavior. It does not establish trading profitability, execution quality, or production readiness.

Consequently, the project should not be connected to a live brokerage account or used to make trading decisions.

## Roadmap

The next engineering priorities are:

1. Introduce a reproducible event-driven simulation loop with explicit event ordering and state transitions.
2. Add pre-trade risk controls that cannot be bypassed by the execution path.
3. Calibrate quote-model parameters on training data and evaluate them out of sample against the fixed-spread baseline.
4. Replace deterministic fills with configurable fill, partial-fill, and latency models; add queue-aware execution only when suitable order-book data is available.
5. Add transaction costs, contract multipliers, and independently reconciled P&L.
6. Build walk-forward experiments with benchmark policies, parameter controls, and leakage-safe evaluation.
7. Add structured logging, configuration, data provenance, and reproducible experiment outputs.

## Project status

The project is under active development as a quantitative research and engineering portfolio project. The current goal is correctness, transparency of assumptions, and reproducibility—not a claim of institutional-grade or production trading infrastructure.
