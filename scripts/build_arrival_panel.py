"""Build the Poisson arrival calibration panel from Alpaca raw CSV exports."""
import argparse
from pathlib import Path

import pandas as pd

from options_mm.experiments.arrival_panel import build_arrival_panel


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quotes", type=Path, default=Path("data/raw/alpaca/quotes.csv"))
    parser.add_argument("--trades", type=Path, default=Path("data/raw/alpaca/trades.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/arrival_panel.csv"))
    parser.add_argument("--distances", default="0.01,0.02,0.05,0.10")
    parser.add_argument("--max-quote-age-seconds", type=float, default=60.0)
    args = parser.parse_args()

    quotes = pd.read_csv(args.quotes)
    trades = pd.read_csv(args.trades)
    quotes["timestamp"] = pd.to_datetime(quotes["t"], utc=True)
    trades["timestamp"] = pd.to_datetime(trades["t"], utc=True)
    for column in ("bp", "ap"):
        quotes[column] = pd.to_numeric(quotes[column], errors="coerce")
    quotes["mid"] = (quotes["bp"] + quotes["ap"]) / 2.0
    trades["price"] = pd.to_numeric(trades["p"], errors="coerce")
    trades["size"] = pd.to_numeric(trades["s"], errors="coerce")
    quotes = quotes.rename(columns={"symbol": "instrument"})
    trades = trades.rename(columns={"symbol": "instrument"})
    distances = tuple(float(value) for value in args.distances.split(","))
    panel = build_arrival_panel(
        quotes[["timestamp", "instrument", "mid"]],
        trades[["timestamp", "instrument", "price", "size"]],
        distances,
        max_quote_age_seconds=args.max_quote_age_seconds,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    panel.to_csv(args.output, index=False)
    print(f"Wrote {len(panel)} exposure rows to {args.output}")
    print("Arrival counts are trade-through proxies, not queue-level fills.")


if __name__ == "__main__":
    main()
