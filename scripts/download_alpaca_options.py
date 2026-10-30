"""Download historical Alpaca option quotes and trades to raw CSV files.

Requires APCA_API_KEY_ID and APCA_API_SECRET_KEY environment variables.
The default feed is indicative; it is not official OPRA NBBO. OPRA access
requires an appropriate Alpaca market-data subscription.
"""
import argparse
import csv
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BASE_URL = "https://data.alpaca.markets/v1beta1/options"


def fetch_pages(endpoint, symbols, start, end, feed, key, secret, limit=10000):
    page_token = None
    while True:
        params = {
            "symbols": ",".join(symbols),
            "start": start,
            "end": end,
            "feed": feed,
            "limit": limit,
            "sort": "asc",
        }
        if page_token:
            params["page_token"] = page_token
        url = f"{BASE_URL}/{endpoint}?{urlencode(params)}"
        request = Request(
            url,
            headers={
                "APCA-API-KEY-ID": key,
                "APCA-API-SECRET-KEY": secret,
                "Accept": "application/json",
                "User-Agent": "options-market-making-research/0.1",
            },
        )
        try:
            with urlopen(request, timeout=60) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Alpaca API returned HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise RuntimeError(f"Could not reach Alpaca market data: {exc}") from exc

        field = "quotes" if endpoint == "quotes" else "trades"
        for symbol, records in payload.get(field, {}).items():
            for record in records:
                yield {"symbol": symbol, **record}

        page_token = payload.get("next_page_token")
        if not page_token:
            break


def write_csv(path: Path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
            count += 1
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", required=True, help="Comma-separated OCC option symbols (max 100)")
    parser.add_argument("--start", required=True, help="RFC-3339 start timestamp")
    parser.add_argument("--end", required=True, help="RFC-3339 end timestamp")
    parser.add_argument("--feed", choices=("indicative", "opra"), default="indicative")
    parser.add_argument("--output-dir", type=Path, default=Path("data/raw/alpaca"))
    args = parser.parse_args()

    symbols = [item.strip() for item in args.symbols.split(",") if item.strip()]
    if not symbols or len(symbols) > 100:
        parser.error("provide between 1 and 100 option symbols")
    key = os.getenv("APCA_API_KEY_ID")
    secret = os.getenv("APCA_API_SECRET_KEY")
    if not key or not secret:
        parser.error("set APCA_API_KEY_ID and APCA_API_SECRET_KEY in the environment")

    quotes = fetch_pages("quotes", symbols, args.start, args.end, args.feed, key, secret)
    trades = fetch_pages("trades", symbols, args.start, args.end, args.feed, key, secret)
    quote_count = write_csv(
        args.output_dir / "quotes.csv",
        quotes,
        ["symbol", "t", "bp", "bs", "ap", "as", "bx", "ax", "c"],
    )
    trade_count = write_csv(
        args.output_dir / "trades.csv",
        trades,
        ["symbol", "t", "p", "s", "x", "c"],
    )
    print(f"Downloaded {quote_count} quote records and {trade_count} trade records.")
    print(f"Feed: {args.feed}. Treat indicative records as indicative, not OPRA quotes.")


if __name__ == "__main__":
    main()
