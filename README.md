# Options Market-Making Simulator

Phase 1 scaffold for an options market-making simulator. This repository contains
a small, well-tested core: market data loader, Black–Scholes pricing and Greeks,
and minimal unit tests. It is designed to be a starting point for iterative
development (quoting engine, execution, inventory and risk modules follow).

Quick start
-----------

Create a virtualenv and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```

Run the demo to compute theoretical prices for sample ticks:

```bash
python scripts/run_phase1.py
```
