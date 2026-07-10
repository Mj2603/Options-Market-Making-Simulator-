# Options Market-Making Simulator

A lightweight Python simulator for options market-making research. 
## Project Overview

The package provides a modular research foundation for option pricing, quoting, execution, risk, and hedging:

- `src/options_mm/pricing/black_scholes.py`: Black-Scholes pricing and Greeks
- `src/options_mm/market/quote_engine.py`: theoretical quote generation
- `src/options_mm/execution/execution.py`: simple order fill model
- `src/options_mm/risk/inventory.py`: inventory tracking and limits
- `src/options_mm/metrics/pnl.py`: realized and mark-to-market PnL
- `src/options_mm/hedge/delta.py`: delta aggregation and hedge sizing
- `src/options_mm/experiments/regime.py`: volatility regime detection

## Getting Started

### Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
```

### Run tests

```bash
pytest
```

### Run the demo

```bash
python scripts/run_phase1.py
```

### Run benchmarks

```bash
python benchmarks/benchmark_simulator.py
python benchmarks/plot_benchmarks.py
```

This will generate a benchmark plot at `benchmarks/benchmark_performance.png`.

## Documentation

- `docs/architecture.md` - architecture and component diagram
- `docs/derivations.md` - Black-Scholes derivation and Greeks
- `docs/benchmark_results.md` - benchmark summaries

## Repository Structure

- `src/options_mm/`: core simulator package
- `data/`: sample tick dataset
- `scripts/`: example demo runner
- `tests/`: unit and benchmark tests
- `docs/`: research documentation and diagrams
- `benchmarks/`: performance benchmark scripts and plotting
- `.github/workflows/ci.yml`: continuous integration pipeline
