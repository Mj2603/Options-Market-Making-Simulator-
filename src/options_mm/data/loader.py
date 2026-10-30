"""Load and validate timestamped option quote observations.

The loader deliberately does not infer an option's settlement time. If the
source only supplies an expiration date, pass the market-specific settlement
time through expiry_time (for example, "16:00:00" for a PM-settled contract).
Do not use this default blindly for AM-settled index options.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


REQUIRED_COLUMNS = {
    "timestamp",
    "expiry",
    "underlying",
    "strike",
    "bid",
    "ask",
}


def _parse_datetime_column(values: pd.Series, name: str) -> pd.Series:
    parsed = pd.to_datetime(values, errors="coerce")
    if parsed.isna().any():
        bad = int(parsed.isna().sum())
        raise ValueError(f"{name!r} contains {bad} invalid or missing datetime values")
    return parsed


def _apply_timezone(values: pd.Series, tz: str | None, name: str) -> pd.Series:
    if tz is None:
        return values
    try:
        if values.dt.tz is None:
            return values.dt.tz_localize(
                tz, ambiguous="NaT", nonexistent="shift_forward"
            )
        return values.dt.tz_convert(tz)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Could not apply timezone {tz!r} to {name!r}") from exc


def load_option_ticks_csv(
    path: str | Path,
    tz: str | None = None,
    expiry_time: str | None = None,
) -> pd.DataFrame:
    """Read option quotes and compute row-specific time to expiry.

    Expected columns: timestamp, expiry, underlying, strike, bid, ask.
    Optional columns (such as iv, option_type, bid_size and ask_size) are
    retained. expiry_time is used only when expiry values are date-only.
    Rows with invalid market values, crossed quotes, or non-positive time to
    expiry are excluded. The original index is reset after filtering.
    """
    df = pd.read_csv(path)

    missing = REQUIRED_COLUMNS.difference(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")

    df = df.copy()
    df["timestamp"] = _parse_datetime_column(df["timestamp"], "timestamp")
    df["expiry"] = _parse_datetime_column(df["expiry"], "expiry")

    expiry_is_midnight = (
        (df["expiry"].dt.hour == 0)
        & (df["expiry"].dt.minute == 0)
        & (df["expiry"].dt.second == 0)
        & (df["expiry"].dt.microsecond == 0)
    )
    if expiry_is_midnight.any():
        if expiry_time is None:
            raise ValueError(
                "Date-only expiry values detected. Pass expiry_time using the "
                "contract's actual settlement convention."
            )
        try:
            time_value = pd.to_timedelta(expiry_time)
        except (TypeError, ValueError) as exc:
            raise ValueError("expiry_time must be a valid time such as '16:00:00'") from exc
        if time_value < pd.Timedelta(0) or time_value >= pd.Timedelta(days=1):
            raise ValueError("expiry_time must be within a 24-hour day")
        df.loc[expiry_is_midnight, "expiry"] = (
            df.loc[expiry_is_midnight, "expiry"].dt.normalize() + time_value
        )

    df["timestamp"] = _apply_timezone(df["timestamp"], tz, "timestamp")
    df["expiry"] = _apply_timezone(df["expiry"], tz, "expiry")

    numeric_columns = ["underlying", "strike", "bid", "ask"]
    for column in numeric_columns:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    valid = np.isfinite(df[numeric_columns]).all(axis=1)
    valid &= df["underlying"] > 0
    valid &= df["strike"] > 0
    valid &= df["bid"] >= 0
    valid &= df["ask"] > 0
    valid &= df["ask"] >= df["bid"]
    df = df.loc[valid].copy()

    df["time_to_expiry"] = (
        df["expiry"] - df["timestamp"]
    ).dt.total_seconds() / (365.25 * 24 * 60 * 60)

    df = df.loc[df["time_to_expiry"] > 0].copy()
    df["mid"] = (df["bid"] + df["ask"]) / 2.0
    df["quoted_spread"] = df["ask"] - df["bid"]

    if "iv" in df.columns:
        df["iv"] = pd.to_numeric(df["iv"], errors="coerce")
        df.loc[~np.isfinite(df["iv"]) | (df["iv"] <= 0), "iv"] = np.nan

    return df.reset_index(drop=True)
