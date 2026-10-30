"""Load vendor-normalized quote/trade events for research experiments."""
from __future__ import annotations

from pathlib import Path
import math

import numpy as np
import pandas as pd

REQUIRED_RESEARCH_COLUMNS = {
    "timestamp", "instrument", "fair_value", "price_volatility",
    "time_to_horizon", "trade_price", "trade_size", "aggressor_side",
}


def load_research_events_csv(path: str | Path) -> pd.DataFrame:
    """Load sorted canonical event rows and reject look-ahead/invalid records.

    A row is either a quote update (trade_size=0 and empty trade fields) or a
    trade print joined to the latest quote at or before that print. Timestamps
    must be UTC or timezone-aware ISO-8601 strings. The function intentionally
    does not infer option expiry conventions, volatility, or aggressor side.
    """
    frame = pd.read_csv(path)
    missing = REQUIRED_RESEARCH_COLUMNS.difference(frame.columns)
    if missing:
        raise ValueError(f"missing research columns: {', '.join(sorted(missing))}")
    frame = frame.copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
    if frame["timestamp"].isna().any():
        raise ValueError("timestamp contains invalid values")
    if frame["instrument"].isna().any() or (frame["instrument"].astype(str).str.strip() == "").any():
        raise ValueError("instrument must be non-empty")
    numeric = ["fair_value", "price_volatility", "time_to_horizon", "trade_size"]
    for column in numeric:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if not np.isfinite(frame[numeric].to_numpy(dtype=float)).all():
        raise ValueError("research numeric columns must be finite")
    if (frame["fair_value"] < 0).any() or (frame["price_volatility"] < 0).any():
        raise ValueError("fair value and price volatility must be non-negative")
    if (frame["time_to_horizon"] < 0).any() or (frame["trade_size"] < 0).any():
        raise ValueError("time to horizon and trade size must be non-negative")
    has_trade = frame["trade_size"] > 0
    frame["trade_price"] = pd.to_numeric(frame["trade_price"], errors="coerce")
    if frame.loc[has_trade, "trade_price"].isna().any():
        raise ValueError("trade rows require a valid trade_price")
    if (frame.loc[has_trade, "trade_price"] < 0).any():
        raise ValueError("trade_price must be non-negative")
    if not frame.loc[has_trade, "aggressor_side"].isin(["buy", "sell"]).all():
        raise ValueError("trade rows require aggressor_side 'buy' or 'sell'")
    if frame.loc[~has_trade, "trade_price"].notna().any():
        raise ValueError("quote-only rows must have an empty trade_price")
    frame = frame.sort_values(["timestamp", "instrument"], kind="stable").reset_index(drop=True)
    return frame


def to_market_events(frame: pd.DataFrame):
    """Convert a validated canonical frame into EventDrivenBacktest events."""
    from options_mm.simulation.event_driven import MarketEvent

    required = REQUIRED_RESEARCH_COLUMNS
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"missing research columns: {', '.join(sorted(missing))}")
    events = []
    for row in frame.itertuples(index=False):
        timestamp = pd.Timestamp(row.timestamp)
        if timestamp.tzinfo is None:
            raise ValueError("event timestamps must be timezone-aware")
        events.append(
            MarketEvent(
                timestamp=float(timestamp.timestamp()),
                instrument=str(row.instrument),
                fair_value=float(row.fair_value),
                price_volatility=float(row.price_volatility),
                time_to_horizon=float(row.time_to_horizon),
                trade_price=None if pd.isna(row.trade_price) else float(row.trade_price),
                trade_size=float(row.trade_size),
                aggressor_side=None if float(row.trade_size) == 0 else str(row.aggressor_side),
            )
        )
    return events
