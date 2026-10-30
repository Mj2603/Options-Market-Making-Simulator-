# Historical data protocol

## Purpose

The simulator consumes historical option quote observations. Loaders normalize timestamps and quote fields; they do not manufacture market observations or infer whether a hypothetical order would have executed.

## Lewen Guo minute-level option quote sample

The adapter in `src/options_mm/data/lewen_guo.py` reads the public Parquet sample. Its source schema is `ticker`, `minute`, `ask_price`, `ask_size`, `bid_price`, and `bid_size`. The file contains option quote snapshots only; it does not contain the underlying equity price.

- Pass `session_date` explicitly. The source's `minute` field is interpreted as minutes since midnight in `America/New_York` by default; override the timezone only when the source convention is known.
- The option symbol is parsed into underlying root, expiration date, call/put, and strike. The standard OCC strike integer is scaled by 1,000.
- Expiration is retained as a calendar date. The adapter does not infer settlement time or time to expiry.
- Crossed quotes, invalid prices, and negative displayed sizes are removed. Midprice and quoted spread are derived from the observed bid and ask.
- The output intentionally has no numeric `underlying` column. Join a timestamp-aligned underlying quote feed before pricing or delta calculations.

Install the optional Parquet engine with `pip install -e '.[parquet]'`.

## Canonical pricing schema

The core CSV loader requires:

| Field | Meaning |
| --- | --- |
| timestamp | Observation timestamp, with documented timezone |
| expiry | Contract settlement timestamp, or expiration date plus explicit settlement time |
| underlying | Underlying reference price observed with the quote |
| strike | Option strike |
| bid | Best bid price |
| ask | Best ask price |

Optional fields such as option_type, bid_size, ask_size, volume, open_interest and iv are retained. Dataset-specific column names should be mapped in a separate adapter rather than hard-coded in the core loader.

## Timestamp and settlement conventions

- Keep all observations for a contract on a consistent clock.
- Pass tz when source timestamps are naive and their timezone is known.
- If the source supplies only an expiration date, pass expiry_time explicitly. Do not assume all contracts settle at 16:00; AM-settled index options and PM-settled equity options differ.
- Time to expiry is calculated row by row from each observation timestamp.
- Rows with crossed quotes, invalid prices or non-positive time to expiry are excluded.

## Execution research boundary

A quote snapshot is not an order-level event stream. With quote snapshots, the project can study quoted spreads, quote changes, short-horizon markouts and counterfactual quoting policies. It cannot claim queue position, order priority, or realized passive fill probability unless the dataset contains the required order/trade events or those assumptions are separately modelled and labelled.

## Data provenance record

For every experiment, record:

- Provider and dataset name
- Source URL and access date
- Instrument universe and date range
- Raw file checksum
- Field mapping and timezone
- Expiration/settlement convention
- Filtering rules
- Whether observations are tick, interval, or end-of-day snapshots

Do not commit licensed or redistributed market data unless its terms explicitly permit redistribution. Keep raw files outside Git and commit only the adapter, configuration, provenance record and reproducible analysis code.
