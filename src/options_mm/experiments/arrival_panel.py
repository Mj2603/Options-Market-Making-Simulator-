"""Construct a quote-distance/count/exposure panel for arrival calibration."""
from __future__ import annotations

import numpy as np
import pandas as pd


def build_arrival_panel(
    quotes: pd.DataFrame,
    trades: pd.DataFrame,
    quote_distances: tuple[float, ...],
    max_quote_age_seconds: float = 60.0,
) -> pd.DataFrame:
    """Create a simple empirical exposure panel from timestamped NBBO and prints.

    Required quote columns: timestamp, instrument, mid.
    Required trade columns: timestamp, instrument, price, size.
    For each quote observation and candidate distance, count prints that
    reached the hypothetical bid/ask level before the next quote update or
    max_quote_age_seconds. This is a trade-through proxy, not an exchange
    queue fill count. Use it to estimate the price-distance decay only.
    """
    q = quotes.copy()
    t = trades.copy()
    for frame, name in ((q, "quotes"), (t, "trades")):
        if not {"timestamp", "instrument"}.issubset(frame.columns):
            raise ValueError(f"{name} requires timestamp and instrument")
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
        if frame["timestamp"].isna().any():
            raise ValueError(f"{name} has invalid timestamps")
    if not {"mid"}.issubset(q.columns) or not {"price", "size"}.issubset(t.columns):
        raise ValueError("quotes require mid; trades require price and size")
    q["mid"] = pd.to_numeric(q["mid"], errors="coerce")
    t["price"] = pd.to_numeric(t["price"], errors="coerce")
    t["size"] = pd.to_numeric(t["size"], errors="coerce")
    if not np.isfinite(q["mid"]).all() or (q["mid"] <= 0).any():
        raise ValueError("quote mids must be positive and finite")
    if not np.isfinite(t[["price", "size"]].to_numpy()).all() or (t["size"] <= 0).any():
        raise ValueError("trade prices and sizes must be finite; sizes positive")
    distances = tuple(float(x) for x in quote_distances)
    if not distances or any(not np.isfinite(x) or x < 0 for x in distances):
        raise ValueError("quote_distances must be non-empty and non-negative")
    if max_quote_age_seconds <= 0:
        raise ValueError("max_quote_age_seconds must be positive")

    rows = []
    for instrument, instrument_quotes in q.groupby("instrument"):
        instrument_quotes = instrument_quotes.sort_values("timestamp").reset_index(drop=True)
        instrument_trades = t.loc[t["instrument"] == instrument].sort_values("timestamp")
        trade_times = instrument_trades["timestamp"].astype("int64").to_numpy()
        trade_prices = instrument_trades["price"].to_numpy(dtype=float)
        trade_sizes = instrument_trades["size"].to_numpy(dtype=float)
        for index, quote in instrument_quotes.iterrows():
            start = quote["timestamp"]
            next_time = (
                instrument_quotes.loc[index + 1, "timestamp"]
                if index + 1 < len(instrument_quotes)
                else start + pd.Timedelta(seconds=max_quote_age_seconds)
            )
            end = min(next_time, start + pd.Timedelta(seconds=max_quote_age_seconds))
            lo = np.searchsorted(trade_times, start.value, side="left")
            hi = np.searchsorted(trade_times, end.value, side="left")
            prices = trade_prices[lo:hi]
            sizes = trade_sizes[lo:hi]
            exposure = max(0.0, (end - start).total_seconds())
            if exposure <= 0.0:
                continue
            mid = float(quote["mid"])
            for distance in distances:
                bid = max(0.0, mid - distance)
                ask = mid + distance
                # Each print is counted once if it reaches either side.
                arrivals = int(np.count_nonzero((prices <= bid) | (prices >= ask)))
                rows.append({
                    "timestamp": float(start.timestamp()),
                    "instrument": instrument,
                    "quote_distance": distance,
                    "arrival_count": arrivals,
                    "exposure_seconds": exposure,
                    "traded_volume": float(sizes[
                        (prices <= bid) | (prices >= ask)
                    ].sum()),
                })
    if not rows:
        raise ValueError("no quote exposure rows could be constructed")
    return pd.DataFrame(rows)
