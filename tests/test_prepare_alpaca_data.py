from datetime import datetime, timedelta, timezone

import pandas as pd

from scripts.prepare_alpaca_research_data import prepare_events


def test_alpaca_normalizer_creates_causal_quote_and_trade_events(tmp_path):
    symbol = "AAPL260116C00100000"
    start = datetime(2026, 1, 2, 14, 30, tzinfo=timezone.utc)
    quote_rows = []
    for index in range(12):
        timestamp = start + timedelta(minutes=index)
        mid = 2.0 + index * 0.01
        quote_rows.append({
            "symbol": symbol,
            "t": timestamp.isoformat().replace("+00:00", "Z"),
            "bp": mid - 0.05,
            "bs": 10,
            "ap": mid + 0.05,
            "as": 12,
        })
    trade_rows = [
        {
            "symbol": symbol,
            "t": (start + timedelta(minutes=10, seconds=30)).isoformat().replace("+00:00", "Z"),
            "p": 2.12,
            "s": 2,
            "x": "A",
            "c": "",
        },
    ]
    quotes_path = tmp_path / "quotes.csv"
    trades_path = tmp_path / "trades.csv"
    pd.DataFrame(quote_rows).to_csv(quotes_path, index=False)
    pd.DataFrame(trade_rows).to_csv(trades_path, index=False)

    events = prepare_events(
        quotes_path, trades_path, settlement_time="16:00:00",
        contract_multiplier=100.0,
    )
    assert len(events) > 0
    trade_events = events.loc[events["trade_size"] > 0]
    assert len(trade_events) == 1
    assert trade_events.iloc[0]["aggressor_side"] == "buy"
    assert trade_events.iloc[0]["market_bid_size"] == 10
    assert trade_events.iloc[0]["contract_multiplier"] == 100.0
