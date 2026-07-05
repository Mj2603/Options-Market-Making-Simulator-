"""Benchmark scripts for options market-making components."""
import time
import pandas as pd
from options_mm.data.loader import load_option_ticks_csv
from options_mm.market.quote_engine import QuoteEngine
from options_mm.pricing.black_scholes import call_price_greeks, put_price_greeks


def benchmark_pricing(df: pd.DataFrame, n_runs: int = 1000) -> dict:
    start = time.perf_counter()
    for _ in range(n_runs):
        for _, row in df.iterrows():
            S = float(row["underlying"])
            K = float(row["strike"])
            T = float(row["time_to_expiry"])
            sigma = float(row.get("iv", 0.2) or 0.2)
            call_price_greeks(S, K, 0.01, sigma, T)
            put_price_greeks(S, K, 0.01, sigma, T)
    elapsed = time.perf_counter() - start
    return {"runs": n_runs, "elapsed_seconds": elapsed, "per_iteration": elapsed / (n_runs * len(df))}


def benchmark_quote_engine(df: pd.DataFrame, n_runs: int = 1000) -> dict:
    engine = QuoteEngine(half_spread=0.05)
    start = time.perf_counter()
    for _ in range(n_runs):
        for _, row in df.iterrows():
            engine.quote(
                float(row["underlying"]),
                float(row["strike"]),
                0.01,
                float(row.get("iv", 0.2) or 0.2),
                float(row["time_to_expiry"]),
                "call",
            )
    elapsed = time.perf_counter() - start
    return {"runs": n_runs, "elapsed_seconds": elapsed, "per_iteration": elapsed / (n_runs * len(df))}


def main() -> None:
    df = load_option_ticks_csv("data/sample_ticks.csv")
    pricing = benchmark_pricing(df, n_runs=100)
    quoting = benchmark_quote_engine(df, n_runs=100)
    print("Pricing benchmark:", pricing)
    print("Quote engine benchmark:", quoting)


if __name__ == "__main__":
    main()
