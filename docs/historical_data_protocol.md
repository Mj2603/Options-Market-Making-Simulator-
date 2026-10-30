# Historical data protocol

## Purpose

The simulator consumes historical option quote observations. The loader normalizes
timestamps and quote fields; it does not manufacture market observations or infer
whether a hypothetical order would have executed.

## Canonical CSV schema

Required fields:

| Field | Meaning |
| --- | --- |
| timestamp | Observation timestamp, with documented timezone |
| expiry | Contract settlement timestamp, or expiration date plus explicit settlement time |
| underlying | Underlying reference price observed with the quote |
| strike | Option strike |
| bid | Best bid price |
| ask | Best ask price |

Optional fields such as option_type, bid_size, ask_size, volume, open_interest
and iv are retained. Dataset-specific column names should be mapped to this
schema in a separate adapter rather than hard-coded in the core loader.

## Timestamp and settlement conventions

- Keep all observations for a contract on a consistent clock.
- Pass tz when source timestamps are naive and their timezone is known.
- If the source supplies only an expiration date, pass expiry_time explicitly.
  Do not assume all contracts settle at 16:00; AM-settled index options and
  PM-settled equity options differ.
- Time to expiry is calculated row by row from each observation timestamp.
- Rows with crossed quotes, invalid prices or non-positive time to expiry are
  excluded.

## Execution research boundary

A quote snapshot is not an order-level event stream. With quote snapshots, the
project can study quoted spreads, quote changes, short-horizon markouts and
counterfactual quoting policies. It cannot claim queue position, order priority,
or realized passive fill probability unless the dataset contains the required
order/trade events or those assumptions are separately modelled and labelled.

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

Do not commit licensed or redistributed market data unless its terms explicitly
permit redistribution. Keep raw data outside Git and commit only the adapter,
configuration, provenance record and reproducible analysis code.
