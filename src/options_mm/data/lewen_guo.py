"""Adapter for the Lewen Guo minute-level S&P 500 option quote sample.

This source contains option NBBO snapshots but no underlying equity prices.
The adapter therefore returns raw option quote observations and deliberately
does not fabricate the underlying field required by the pricing simulator.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd


_OPTION_SYMBOL = re.compile(
    r"^O:(?P<root>.+?)(?P<expiry>\d{6})(?P<right>[CP])(?P<strike>\d{8})$"
)
_SOURCE_COLUMNS = {
    "ticker",
    "minute",
    "ask_price",
    "ask_size",
    "bid_price",
    "bid_size",
}


def parse_option_symbol(symbol: str) -> dict[str, object]:
    """Parse a Polygon-style OCC option symbol such as O:A230120C00050000."""
    match = _OPTION_SYMBOL.fullmatch(str(symbol).strip())
    if match is None:
        raise ValueError(f"Unsupported option symbol: {symbol!r}")

    fields = match.groupdict()
    expiry = datetime.strptime(fields["expiry"], "%y%m%d").date()
    return {
        "underlying_symbol": fields["root"],
        "expiry_date": expiry,
        "option_type": "call" if fields["right"] == "C" else "put",
        "strike": int(fields["strike"]) / 1000.0,
    }


def load_lewen_guo_options_parquet(
    path: str | Path,
    session_date: str | date,
    timezone: str = "America/New_York",
) -> pd.DataFrame:
    """Load minute-level option quotes for one explicitly supplied session.

    minute is interpreted as minutes since midnight in timezone. Expiry is
    retained as a date; settlement time is intentionally not inferred. The
    source has no underlying-price column, so this output is not directly
    consumable by the Black-Scholes pricing loader until an underlying quote
    stream has been joined.
    """
    try:
        raw = pd.read_parquet(path)
    except ImportError as exc:
        raise ImportError(
            "Parquet support requires PyArrow. Install with "
            "pip install -e '.[parquet]'."
        ) from exc

    missing = _SOURCE_COLUMNS.difference(raw.columns)
    if missing:
        raise ValueError(
            "Unexpected source schema; missing columns: "
            + ", ".join(sorted(missing))
        )

    session = pd.Timestamp(session_date)
    if pd.isna(session):
        raise ValueError("session_date must be a valid calendar date")
    if session.tzinfo is not None:
        raise ValueError("session_date must be a date without timezone")

    df = raw.copy()
    parsed = df["ticker"].astype("string").map(parse_option_symbol)
    parsed_fields = pd.DataFrame(parsed.tolist(), index=df.index)
    df = pd.concat([df, parsed_fields], axis=1)

    minute = pd.to_numeric(df["minute"], errors="coerce")
    valid_minute = np.isfinite(minute) & (minute >= 0) & (minute < 1440)
    valid_minute &= np.equal(minute, np.floor(minute))
    if not valid_minute.all():
        raise ValueError("minute must contain integer minutes in [0, 1440)")

    df["minute_of_day"] = minute.astype("int64")
    local_naive = session.normalize() + pd.to_timedelta(
        df["minute_of_day"], unit="m"
    )
    df["timestamp"] = local_naive.dt.tz_localize(
        timezone, ambiguous="NaT", nonexistent="shift_forward"
    )
    if df["timestamp"].isna().any():
        raise ValueError("Some source minutes could not be localized to the timezone")

    for source, target in (
        ("bid_price", "bid"),
        ("ask_price", "ask"),
        ("bid_size", "bid_size"),
        ("ask_size", "ask_size"),
    ):
        df[target] = pd.to_numeric(df[source], errors="coerce")

    quote_values = ["bid", "ask", "bid_size", "ask_size"]
    valid = np.isfinite(df[quote_values]).all(axis=1)
    valid &= (df["bid"] >= 0) & (df["ask"] > 0) & (df["ask"] >= df["bid"])
    valid &= (df["bid_size"] >= 0) & (df["ask_size"] >= 0)
    df = df.loc[valid].copy()

    df["mid"] = (df["bid"] + df["ask"]) / 2.0
    df["quoted_spread"] = df["ask"] - df["bid"]

    columns = [
        "contract_symbol",
        "underlying_symbol",
        "timestamp",
        "minute_of_day",
        "expiry_date",
        "option_type",
        "strike",
        "bid",
        "ask",
        "bid_size",
        "ask_size",
        "mid",
        "quoted_spread",
    ]
    df = df.rename(columns={"ticker": "contract_symbol"})
    return (
        df[columns]
        .sort_values(["contract_symbol", "timestamp"], kind="stable")
        .reset_index(drop=True)
    )
