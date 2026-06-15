"""CSV loader for options tick data.

Expected CSV columns: timestamp, underlying, strike, expiry, bid, ask, iv
"""
from __future__ import annotations

from dataclasses import dataclass
import pandas as pd
import numpy as np


def load_option_ticks_csv(path: str, tz: str | None = None) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["timestamp"] = pd.to_datetime(df["timestamp"]) 
    df["expiry"] = pd.to_datetime(df["expiry"]).dt.normalize()
    if tz is not None:
        df["timestamp"] = df["timestamp"].dt.tz_localize(tz, ambiguous="NaT", nonexistent="shift_forward")
    df = df.dropna(subset=["underlying", "strike", "bid", "ask"]) 
    df["mid"] = (df["bid"] + df["ask"]) / 2.0
    now = df["timestamp"].max()
    df["time_to_expiry"] = (df["expiry"] - now).dt.total_seconds() / (365.25 * 24 * 3600)
    df["time_to_expiry"] = df["time_to_expiry"].clip(lower=0.0)
    if "iv" in df.columns:
        df["iv"] = pd.to_numeric(df["iv"], errors="coerce")
        df.loc[df["iv"] < 0, "iv"] = np.nan
    return df
