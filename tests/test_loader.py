import pandas as pd
import pytest

from options_mm.data.loader import load_option_ticks_csv


def _write_quotes(tmp_path, rows):
    path = tmp_path / "quotes.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def test_time_to_expiry_is_calculated_per_observation(tmp_path):
    path = _write_quotes(
        tmp_path,
        [
            {
                "timestamp": "2026-01-02 10:00:00",
                "expiry": "2026-01-02 16:00:00",
                "underlying": 100,
                "strike": 100,
                "bid": 2.0,
                "ask": 2.2,
            },
            {
                "timestamp": "2026-01-02 12:00:00",
                "expiry": "2026-01-02 16:00:00",
                "underlying": 101,
                "strike": 100,
                "bid": 2.1,
                "ask": 2.3,
            },
        ],
    )

    quotes = load_option_ticks_csv(path)

    assert len(quotes) == 2
    assert quotes.loc[0, "time_to_expiry"] > quotes.loc[1, "time_to_expiry"]
    assert quotes.loc[0, "time_to_expiry"] == pytest.approx(
        6 / (365.25 * 24), rel=1e-9
    )
    assert quotes.loc[1, "time_to_expiry"] == pytest.approx(
        4 / (365.25 * 24), rel=1e-9
    )


def test_date_only_expiry_requires_explicit_settlement_time(tmp_path):
    path = _write_quotes(
        tmp_path,
        [
            {
                "timestamp": "2026-01-02 10:00:00",
                "expiry": "2026-01-02",
                "underlying": 100,
                "strike": 100,
                "bid": 2.0,
                "ask": 2.2,
            }
        ],
    )

    with pytest.raises(ValueError, match="settlement convention"):
        load_option_ticks_csv(path)


def test_date_only_expiry_uses_explicit_settlement_time(tmp_path):
    path = _write_quotes(
        tmp_path,
        [
            {
                "timestamp": "2026-01-02 10:00:00",
                "expiry": "2026-01-02",
                "underlying": 100,
                "strike": 100,
                "bid": 2.0,
                "ask": 2.2,
            }
        ],
    )

    quotes = load_option_ticks_csv(path, expiry_time="16:00:00")

    assert len(quotes) == 1
    assert quotes.loc[0, "time_to_expiry"] == pytest.approx(
        6 / (365.25 * 24), rel=1e-9
    )


def test_crossed_quotes_and_expired_rows_are_removed(tmp_path):
    path = _write_quotes(
        tmp_path,
        [
            {
                "timestamp": "2026-01-02 10:00:00",
                "expiry": "2026-01-02 16:00:00",
                "underlying": 100,
                "strike": 100,
                "bid": 2.3,
                "ask": 2.2,
            },
            {
                "timestamp": "2026-01-02 17:00:00",
                "expiry": "2026-01-02 16:00:00",
                "underlying": 100,
                "strike": 100,
                "bid": 2.0,
                "ask": 2.2,
            },
            {
                "timestamp": "2026-01-02 10:00:00",
                "expiry": "2026-01-02 16:00:00",
                "underlying": 100,
                "strike": 100,
                "bid": 2.0,
                "ask": 2.2,
            },
        ],
    )

    quotes = load_option_ticks_csv(path)

    assert len(quotes) == 1
    assert quotes.loc[0, "mid"] == pytest.approx(2.1)
    assert quotes.loc[0, "quoted_spread"] == pytest.approx(0.2)


def test_missing_required_columns_raise_clear_error(tmp_path):
    path = tmp_path / "bad.csv"
    pd.DataFrame({"timestamp": ["2026-01-02"]}).to_csv(path, index=False)

    with pytest.raises(ValueError, match="Missing required columns"):
        load_option_ticks_csv(path)
