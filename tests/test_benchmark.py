import pandas as pd
from options_mm.data.loader import load_option_ticks_csv
from benchmarks.benchmark_simulator import benchmark_pricing, benchmark_quote_engine


def test_benchmark_pricing_runs():
    df = load_option_ticks_csv("data/sample_ticks.csv")
    result = benchmark_pricing(df, n_runs=1)
    assert result["runs"] == 1
    assert result["elapsed_seconds"] >= 0.0


def test_benchmark_quote_engine_runs():
    df = load_option_ticks_csv("data/sample_ticks.csv")
    result = benchmark_quote_engine(df, n_runs=1)
    assert result["runs"] == 1
    assert result["elapsed_seconds"] >= 0.0
