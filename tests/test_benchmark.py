import pandas as pd

from benchmarks.benchmark_simulator import benchmark_pricing, benchmark_quote_engine


def _market_fixture():
    return pd.DataFrame(
        {
            "underlying": [100.0, 101.0, 99.5],
            "strike": [100.0, 100.0, 100.0],
            "time_to_expiry": [30 / 365.25, 45 / 365.25, 60 / 365.25],
            "iv": [0.20, 0.22, 0.19],
        }
    )


def test_benchmark_pricing_runs_without_external_market_data():
    result = benchmark_pricing(_market_fixture(), n_runs=1)
    assert result["runs"] == 1
    assert result["elapsed_seconds"] >= 0.0


def test_benchmark_quote_engine_runs_without_external_market_data():
    result = benchmark_quote_engine(_market_fixture(), n_runs=1)
    assert result["runs"] == 1
    assert result["elapsed_seconds"] >= 0.0
