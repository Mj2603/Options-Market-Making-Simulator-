# Options Market-Making Simulator

A Python research prototype for option pricing, quote construction, execution assumptions, inventory tracking and P&L analysis. The current code is a simulation foundation, not an exchange-grade matching or execution system.

## Implemented components

- Black–Scholes option prices and Greeks
- Fixed-width theoretical bid/ask quote generation
- Basic touch/cross execution rules
- Per-instrument inventory tracking
- Realized and mark-to-market P&L
- Delta aggregation and hedge sizing
- A simple volatility threshold classifier
- Validated CSV ingestion with row-specific time-to-expiry calculation
- A dataset-specific adapter for the public minute-level option quote Parquet sample

## Research status

The current repository is being upgraded from a prototype into a reproducible historical-quote research framework. Unit tests use small synthetic fixtures; those fixtures are software tests and must not be interpreted as market evidence.

The core CSV loader calculates time to expiry from each quote's own timestamp, validates quote fields, and requires an explicit settlement time when a source contains date-only expirations. The Parquet adapter parses option symbols and quote sizes, but does not invent an underlying price or settlement timestamp. See the Historical Data Protocol.

## Candidate public data source

A public research page provides a 5,000-row sample of minute-level S&P 500 constituent option quotes from 3 January 2023, with bid/ask prices and sizes. The page describes a 106.5-million-row, 432.3 MB source file and says the full file can be requested from the author:

- Dataset page and sample download: https://lewenguo.com/data
- Direct Parquet sample: https://lewenguo.com/data/sp500-options-2023-01-03-sample.parquet

Install the optional Parquet reader with:

    pip install -e '.[parquet]'

The sample is interval quote data, not order-level event data. It can support quoted-spread, quote-change and forward-midprice-markout analysis. It does not reveal queue priority or prove that a hypothetical passive order would have filled. A single trading day is a development sample, not enough for a robust out-of-sample performance claim. A multi-day sample is needed before strategy performance is reported.

The option quote file does not contain underlying equity prices. Join a timestamp-aligned underlying quote feed before calculating theoretical option values or Greeks. Do not use the underlying symbol as if it were an underlying price.

Do not commit downloaded market data unless its license and redistribution terms permit it. Keep raw files outside Git and record their source, date range, timezone, schema and checksum in each experiment.

## Setup

Create a virtual environment, then install the project and test dependencies:

    pip install -e . -r requirements-dev.txt

## Tests

Run pytest. Tests use synthetic fixtures and should run without downloading market data.

## Repository guide

- src/options_mm/: simulator package
- tests/: unit tests
- benchmarks/: timing scripts
- scripts/: demo runners
- docs/architecture.md: current component design
- docs/derivations.md: pricing formulas
- docs/historical_data_protocol.md: data schema and timestamp rules
- .github/workflows/ci.yml: GitHub Actions test workflow

## Current limitations

- Quote widths are fixed; inventory-aware quoting is not yet implemented.
- Execution rules are simplified and do not model queue position or latency.
- No historical strategy performance is claimed.
- No passive fill probability is inferred from quote snapshots.
- The one-day sample is not sufficient for a robust out-of-sample strategy evaluation.
