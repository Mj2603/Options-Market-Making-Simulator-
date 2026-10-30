import pandas as pd
import pytest

from options_mm.data.research import load_research_events_csv, to_market_events


def test_canonical_research_data_loads_and_preserves_nbbo(tmp_path):
    path = tmp_path / "events.csv"
    pd.DataFrame([{
        "timestamp": "2026-01-02T15:00:00Z",
        "instrument": "AAPL260116C00100000",
        "fair_value": 2.0,
        "price_volatility": 0.5,
        "time_to_horizon": 0.04,
        "trade_price": 2.1,
        "trade_size": 1,
        "aggressor_side": "buy",
        "market_bid": 1.9,
        "market_ask": 2.1,
        "market_bid_size": 10,
        "market_ask_size": 20,
    }]).to_csv(path, index=False)
    frame = load_research_events_csv(path)
    events = to_market_events(frame)
    assert events[0].market_bid == pytest.approx(1.9)
    assert events[0].market_ask_size == pytest.approx(20.0)


def test_canonical_research_data_rejects_bad_aggressor(tmp_path):
    path = tmp_path / "events.csv"
    pd.DataFrame([{
        "timestamp": "2026-01-02T15:00:00Z", "instrument": "OPT",
        "fair_value": 2.0, "price_volatility": 0.5,
        "time_to_horizon": 0.04, "trade_price": 2.1,
        "trade_size": 1, "aggressor_side": "unknown",
    }]).to_csv(path, index=False)
    with pytest.raises(ValueError):
        load_research_events_csv(path)
