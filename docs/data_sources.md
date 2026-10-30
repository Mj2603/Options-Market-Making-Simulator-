# Historical options data and provenance

## Supported download path

The repository includes a downloader for Alpaca historical option quotes and
trades. It writes raw provider fields to:

- `data/raw/alpaca/quotes.csv`
- `data/raw/alpaca/trades.csv`
- `data/raw/alpaca/metadata.json`

Set API credentials in environment variables; never commit credentials:

```bash
export APCA_API_KEY_ID="..."
export APCA_API_SECRET_KEY="..."

python scripts/download_alpaca_options.py \
  --symbols "AAPL260116C00100000,AAPL260116P00100000" \
  --start "2026-01-02T14:30:00Z" \
  --end "2026-01-02T21:00:00Z" \
  --feed indicative
```

Alpaca documents historical options data from February 2024 onward. Its
indicative feed is a modified derivative of OPRA, not actual OPRA quotes, and
trades are delayed by 15 minutes. The OPRA feed requires a qualifying
subscription. A backtest using indicative data must be labelled accordingly;
do not describe it as exchange-grade OPRA replay.

Sources:
- [Alpaca historical options data](https://docs.alpaca.markets/us/docs/historical-option-data)
- [Alpaca historical option quotes and trades API](https://docs.alpaca.markets/us/reference/optiontrades)
- [Cboe option quote intervals](https://datashop.cboe.com/option-quote-intervals)
- [Cboe option trades](https://datashop.cboe.com/option-trades)

Cboe's option quote interval product includes NBBO prices and displayed sizes
and can include implied volatility and Greeks. It is a commercial historical
data product. Tick-level data and exchange-level order-book reconstruction
require a separately licensed dataset; NBBO snapshots alone do not reveal
queue priority or cancellations.

## Normalize into research events

```bash
python scripts/prepare_alpaca_research_data.py \
  --settlement-time 16:00:00 \
  --output data/processed/research_events.csv
```

The settlement time is deliberately mandatory. OCC option symbols encode an
expiration date but do not by themselves tell this pipeline whether a contract
is AM- or PM-settled. The default multiplier is 100 and is appropriate only
for standard US equity options; adjusted contracts require explicit metadata.

The normalizer:
- uses backward as-of quote joins, never future quotes;
- removes invalid/crossed quotes and stale trade/quote joins;
- computes a causal EWMA volatility estimate from option-premium returns;
- infers aggressor side from trade price versus midpoint, then applies a tick
  test to midpoint prints; ambiguous prints are discarded;
- records NBBO sizes for the L1 queue approximation.

The aggressor side is inferred, not supplied by the historical trade API.
The volatility forecast is an option-premium proxy, not a fitted underlying
volatility process. These are explicit data-quality limitations.

## Arrival calibration panel

```bash
python scripts/build_arrival_panel.py \
  --distances 0.01,0.02,0.05,0.10 \
  --output data/processed/arrival_panel.csv
```

For each quote observation and candidate quote distance, the panel counts
prints that reach the hypothetical bid or ask before the next quote update
(or the maximum quote age). This is a trade-through proxy. It is not an
observed maker fill and does not reveal the amount of volume ahead in queue.
Counts at different distances are nested and correlated, so the Poisson fit
is a composite-likelihood calibration; its likelihood should not be
interpreted as an independent-sample confidence statement.

The fitted intensity is:

`lambda(delta) = A * exp(-k * delta)`

`A` is the estimated arrival rate at zero distance; `k` is price-distance
sensitivity and maps to the A-S model's `k` parameter. The simplified
stationary quote-width expression uses `k`; `A` is reported as a diagnostic.

## Data licensing and reproducibility

Raw data are intentionally not committed. Confirm vendor terms before storing,
redistributing, or publishing downloaded data. Preserve the generated
`metadata.json`, the original raw files, feed selection, date range, symbols,
settlement convention, contract multiplier, and normalization command for
every experiment.
