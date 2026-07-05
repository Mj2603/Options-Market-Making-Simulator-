"""Generate benchmark performance plots for the simulator."""
import os
import sys
import matplotlib.pyplot as plt
import pandas as pd
from options_mm.data.loader import load_option_ticks_csv

try:
    from .benchmark_simulator import benchmark_pricing, benchmark_quote_engine
except ImportError:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    from benchmarks.benchmark_simulator import benchmark_pricing, benchmark_quote_engine


def plot_benchmarks(output_path: str = "benchmark_performance.png") -> None:
    df = load_option_ticks_csv(os.path.join("data", "sample_ticks.csv"))
    pricing = benchmark_pricing(df, n_runs=100)
    quoting = benchmark_quote_engine(df, n_runs=100)

    labels = ["Pricing", "Quote Engine"]
    values = [pricing["elapsed_seconds"], quoting["elapsed_seconds"]]

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(labels, values, color=["#1f77b4", "#ff7f0e"])
    ax.set_title("Options Simulator Benchmark Performance")
    ax.set_ylabel("Elapsed time (s)")
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    fig.tight_layout()
    fig.savefig(output_path)
    print(f"Saved benchmark plot to {output_path}")


if __name__ == "__main__":
    plot_benchmarks(os.path.join("benchmarks", "benchmark_performance.png"))
