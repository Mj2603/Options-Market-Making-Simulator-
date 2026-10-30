import pandas as pd

from options_mm.experiments.arrival_panel import build_arrival_panel


def test_arrival_panel_excludes_same_timestamp_trade_and_counts_later_trade():
    quotes = pd.DataFrame([
        {"timestamp": "2026-01-02T15:00:00Z", "instrument": "OPT", "mid": 10.0},
        {"timestamp": "2026-01-02T15:01:00Z", "instrument": "OPT", "mid": 10.0},
    ])
    trades = pd.DataFrame([
        {"timestamp": "2026-01-02T15:00:00Z", "instrument": "OPT", "price": 9.8, "size": 1},
        {"timestamp": "2026-01-02T15:00:30Z", "instrument": "OPT", "price": 9.8, "size": 2},
    ])
    panel = build_arrival_panel(quotes, trades, (0.1,), max_quote_age_seconds=60.0)
    first = panel.iloc[0]
    assert first["arrival_count"] == 1
    assert first["traded_volume"] == 2.0
