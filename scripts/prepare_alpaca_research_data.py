"""Prepare canonical events from Alpaca historical option quote/trade CSVs.

The script uses backward as-of quote joins only. Trade aggressor side is
inferred from trade price versus the contemporaneous midpoint, with a tick
test for midpoint prints. Ambiguous first midpoint prints are discarded.
"""
import argparse
from datetime import datetime, time
from pathlib import Path
import re
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd


OCC_PATTERN = re.compile(r"^(.+?)(\d{6})([CP])(\d{8})$")


def contract_metadata(symbol: str, settlement_time: str):
    match = OCC_PATTERN.match(symbol)
    if not match:
        raise ValueError(f"cannot parse OCC option symbol: {symbol}")
    underlying, yymmdd, option_type, strike_raw = match.groups()
    expiry_date = datetime.strptime(yymmdd, "%y%m%d").date()
    expiry_local = datetime.combine(
        expiry_date, time.fromisoformat(settlement_time), tzinfo=ZoneInfo("America/New_York")
    )
    return underlying.rstrip(), expiry_local, option_type, int(strike_raw) / 1000.0


def prepare_events(
    quotes_path: Path,
    trades_path: Path,
    settlement_time: str,
    quote_tolerance_seconds: float = 60.0,
    contract_multiplier: float = 100.0,
):
    quotes = pd.read_csv(quotes_path)
    trades = pd.read_csv(trades_path)
    required_quotes = {"symbol", "t", "bp", "bs", "ap", "as"}
    required_trades = {"symbol", "t", "p", "s"}
    if not required_quotes.issubset(quotes.columns):
        raise ValueError(f"quote file missing: {sorted(required_quotes - set(quotes.columns))}")
    if not required_trades.issubset(trades.columns):
        raise ValueError(f"trade file missing: {sorted(required_trades - set(trades.columns))}")
    if contract_multiplier <= 0.0 or not np.isfinite(contract_multiplier):
        raise ValueError("contract_multiplier must be positive and finite")

    quotes["timestamp"] = pd.to_datetime(quotes["t"], utc=True, errors="coerce")
    trades["timestamp"] = pd.to_datetime(trades["t"], utc=True, errors="coerce")
    for frame, name in ((quotes, "quotes"), (trades, "trades")):
        if frame["timestamp"].isna().any():
            raise ValueError(f"{name} contains invalid timestamps")
    for column in ("bp", "bs", "ap", "as"):
        quotes[column] = pd.to_numeric(quotes[column], errors="coerce")
    for column in ("p", "s"):
        trades[column] = pd.to_numeric(trades[column], errors="coerce")

    quotes = quotes.dropna(subset=["bp", "bs", "ap", "as"])
    quotes = quotes.loc[
        (quotes["bp"] >= 0) & (quotes["ap"] > 0)
        & (quotes["ap"] >= quotes["bp"])
        & (quotes["bs"] >= 0) & (quotes["as"] >= 0)
    ].copy()
    quotes["mid"] = (quotes["bp"] + quotes["ap"]) / 2.0
    quotes = quotes.loc[quotes["mid"] > 0].sort_values(["symbol", "timestamp"])
    if quotes.empty:
        raise ValueError("no valid non-crossed quotes in source file")

    vol_frames = []
    for symbol, group in quotes.groupby("symbol", sort=False):
        minute = (
            group.set_index("timestamp")["mid"]
            .resample("1min").last().dropna()
        )
        log_returns = np.log(minute).diff()
        sigma = log_returns.ewm(span=30, min_periods=5, adjust=False).std(bias=False)
        vol = (minute * sigma * np.sqrt(252.0 * 390.0)).rename("price_volatility")
        vol_frames.append(
            pd.DataFrame({"timestamp": vol.index, "symbol": symbol, "price_volatility": vol.values})
        )
    volatility = pd.concat(vol_frames, ignore_index=True).dropna()
    quotes = pd.merge_asof(
        quotes.sort_values("timestamp"),
        volatility.sort_values("timestamp"),
        on="timestamp",
        by="symbol",
        direction="backward",
        tolerance=pd.Timedelta(minutes=2),
    )
    quotes = quotes.dropna(subset=["price_volatility"]).copy()
    if quotes.empty:
        raise ValueError("not enough quote history to initialize EWMA volatility")

    metadata = {
        symbol: contract_metadata(symbol, settlement_time)
        for symbol in quotes["symbol"].unique()
    }

    quote_rows = []
    for row in quotes.itertuples(index=False):
        underlying, expiry_local, option_type, strike = metadata[row.symbol]
        tte = (expiry_local.astimezone(ZoneInfo("UTC")) - row.timestamp).total_seconds() / (365.25 * 86400.0)
        if tte <= 0:
            continue
        quote_rows.append({
            "timestamp": row.timestamp,
            "instrument": row.symbol,
            "underlying": underlying,
            "option_type": option_type,
            "strike": strike,
            "expiry": expiry_local.isoformat(),
            "fair_value": row.mid,
            "price_volatility": row.price_volatility,
            "time_to_horizon": tte,
            "market_bid": row.bp,
            "market_ask": row.ap,
            "market_bid_size": row.bs,
            "market_ask_size": row._as if hasattr(row, "_as") else getattr(row, "as"),
            "trade_price": np.nan,
            "trade_size": 0.0,
            "aggressor_side": "",
            "contract_multiplier": contract_multiplier,
            "data_feed_note": "Alpaca feed selected at download; check raw source metadata",
        })
    quote_events = pd.DataFrame(quote_rows)
    if quote_events.empty:
        raise ValueError("no quote rows remain after expiry filtering")

    trades = trades.dropna(subset=["p", "s"]).loc[
        (trades["p"] >= 0) & (trades["s"] > 0)
    ].sort_values(["symbol", "timestamp"])
    quote_for_join = quotes[
        ["symbol", "timestamp", "mid", "bp", "bs", "ap", "as", "price_volatility"]
    ].rename(columns={"timestamp": "quote_timestamp"})
    trade_events = []
    for symbol, group in trades.groupby("symbol", sort=False):
        qgroup = quote_for_join.loc[quote_for_join["symbol"] == symbol].drop(columns="symbol")
        if qgroup.empty:
            continue
        merged = pd.merge_asof(
            group.sort_values("timestamp"),
            qgroup.sort_values("quote_timestamp"),
            left_on="timestamp",
            right_on="quote_timestamp",
            direction="backward",
            tolerance=pd.Timedelta(seconds=quote_tolerance_seconds),
        ).dropna(subset=["mid", "price_volatility"])
        previous_price = None
        for row in merged.itertuples(index=False):
            if row.p > row.mid:
                side = "buy"
            elif row.p < row.mid:
                side = "sell"
            elif previous_price is not None and row.p != previous_price:
                side = "buy" if row.p > previous_price else "sell"
            else:
                previous_price = row.p
                continue
            previous_price = row.p
            underlying, expiry_local, option_type, strike = metadata[symbol]
            tte = (expiry_local.astimezone(ZoneInfo("UTC")) - row.timestamp).total_seconds() / (365.25 * 86400.0)
            if tte <= 0:
                continue
            trade_events.append({
                "timestamp": row.timestamp,
                "instrument": symbol,
                "underlying": underlying,
                "option_type": option_type,
                "strike": strike,
                "expiry": expiry_local.isoformat(),
                "fair_value": row.mid,
                "price_volatility": row.price_volatility,
                "time_to_horizon": tte,
                "market_bid": row.bp,
                "market_ask": row.ap,
                "market_bid_size": row.bs,
                "market_ask_size": getattr(row, "as"),
                "trade_price": row.p,
                "trade_size": row.s,
                "aggressor_side": side,
                "contract_multiplier": contract_multiplier,
                "data_feed_note": "Aggressor side inferred from midpoint/tick rule",
            })
    combined = pd.concat(
        [quote_events, pd.DataFrame(trade_events)],
        ignore_index=True,
    )
    return combined.sort_values(["timestamp", "instrument"], kind="stable").reset_index(drop=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quotes", type=Path, default=Path("data/raw/alpaca/quotes.csv"))
    parser.add_argument("--trades", type=Path, default=Path("data/raw/alpaca/trades.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/research_events.csv"))
    parser.add_argument("--settlement-time", required=True, help="Contract settlement time in New York local time, e.g. 16:00:00")
    parser.add_argument("--quote-tolerance-seconds", type=float, default=60.0)
    parser.add_argument("--contract-multiplier", type=float, default=100.0)
    args = parser.parse_args()
    events = prepare_events(
        args.quotes, args.trades, args.settlement_time,
        args.quote_tolerance_seconds, args.contract_multiplier,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    events.to_csv(args.output, index=False)
    print(f"Wrote {len(events)} event rows to {args.output}")
    print("Volatility is causal EWMA of option-premium returns; aggressor side is inferred.")
    print("Do not use adjusted contracts with the default multiplier or settlement time.")


if __name__ == "__main__":
    main()
