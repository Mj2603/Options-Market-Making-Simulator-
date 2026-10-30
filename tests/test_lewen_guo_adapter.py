import pandas as pd
import pytest

from options_mm.data.lewen_guo import (
    load_lewen_guo_options_parquet,
    parse_option_symbol,
)


def test_parse_occ_style_option_symbol():
    parsed = parse_option_symbol("O:A230120C00050000")
    assert parsed == {
        "underlying_symbol": "A",
        "expiry_date": pd.Timestamp("2023-01-20").date(),
        "option_type": "call",
        "strike": 50.0,
    }


def test_load_parquet_maps_quotes_without_fabricating_underlying(monkeypatch):
    raw = pd.DataFrame(
        {
            "ticker": [
                "O:A230120C00050000",
                "O:A230120C00050000",
                "O:XYL230120P00055000",
            ],
            "minute": [570, 571, 570],
            "ask_price": [1.25, 1.30, 2.10],
            "ask_size": [10, 12, 8],
            "bid_price": [1.15, 1.20, 2.00],
            "bid_size": [11, 9, 7],
        }
    )
    monkeypatch.setattr(pd, "read_parquet", lambda path: raw)

    result = load_lewen_guo_options_parquet(
        "sample.parquet", session_date="2023-01-03"
    )

    assert len(result) == 3
    assert result.loc[0, "underlying_symbol"] == "A"
    assert result.loc[0, "strike"] == 50.0
    assert result.loc[0, "option_type"] == "call"
    assert result.loc[0, "timestamp"] == pd.Timestamp(
        "2023-01-03 09:30:00", tz="America/New_York"
    )
    assert result.loc[0, "mid"] == pytest.approx(1.20)
    assert result.loc[0, "quoted_spread"] == pytest.approx(0.10)
    assert "underlying" not in result.columns


def test_parquet_engine_round_trip(tmp_path):
    raw = pd.DataFrame(
        {
            "ticker": ["O:A230120C00050000"],
            "minute": [570],
            "ask_price": [1.25],
            "ask_size": [10],
            "bid_price": [1.15],
            "bid_size": [11],
        }
    )
    path = tmp_path / "quotes.parquet"
    raw.to_parquet(path, index=False)

    result = load_lewen_guo_options_parquet(
        path, session_date="2023-01-03"
    )
    assert len(result) == 1
    assert result.loc[0, "contract_symbol"] == "O:A230120C00050000"


def test_load_parquet_filters_crossed_quotes(monkeypatch):
    raw = pd.DataFrame(
        {
            "ticker": ["O:A230120C00050000", "O:A230120C00050000"],
            "minute": [570, 571],
            "ask_price": [1.25, 1.10],
            "ask_size": [10, 10],
            "bid_price": [1.15, 1.20],
            "bid_size": [10, 10],
        }
    )
    monkeypatch.setattr(pd, "read_parquet", lambda path: raw)

    result = load_lewen_guo_options_parquet(
        "sample.parquet", session_date="2023-01-03"
    )
    assert len(result) == 1
    assert result.loc[0, "minute_of_day"] == 570


def test_load_parquet_rejects_unparseable_contract_symbol(monkeypatch):
    raw = pd.DataFrame(
        {
            "ticker": ["not-an-option-symbol"],
            "minute": [570],
            "ask_price": [1.25],
            "ask_size": [10],
            "bid_price": [1.15],
            "bid_size": [10],
        }
    )
    monkeypatch.setattr(pd, "read_parquet", lambda path: raw)

    with pytest.raises(ValueError, match="Unsupported option symbol"):
        load_lewen_guo_options_parquet(
            "sample.parquet", session_date="2023-01-03"
        )


def test_load_parquet_requires_explicit_session_date(monkeypatch):
    raw = pd.DataFrame(
        {
            "ticker": ["O:A230120C00050000"],
            "minute": [570],
            "ask_price": [1.25],
            "ask_size": [10],
            "bid_price": [1.15],
            "bid_size": [10],
        }
    )
    monkeypatch.setattr(pd, "read_parquet", lambda path: raw)

    with pytest.raises(ValueError, match="session_date"):
        load_lewen_guo_options_parquet("sample.parquet", session_date="not-a-date")
