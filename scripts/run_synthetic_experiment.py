"""Multi-seed SYNTHETIC walk-forward comparison: Avellaneda-Stoikov vs fixed spread.

For each scenario and seed, generate one synthetic session, run the
expanding-window walk-forward comparison (arrival k fitted by Poisson MLE on
each training window, gamma and the fixed half-spread chosen by grid search on
the same training window), and sum out-of-sample net P&L over the test folds.

Outputs (default results/):
  synthetic_walkforward_seeds.csv  one row per scenario/seed
  synthetic_walkforward.csv        one row per scenario summary
  synthetic_walkforward.md         human-readable report

All data are SYNTHETIC; see options_mm.data.synthetic for the generating model.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from options_mm.data.synthetic import SCENARIOS, scenario_config, synthetic_walk_forward_inputs
from options_mm.experiments.walk_forward import walk_forward_compare


def run_seed(scenario: str, seed: int, args) -> dict:
    config = scenario_config(scenario, seed, **({"n_events": args.n_events} if args.n_events else {}))
    _, events, panel = synthetic_walk_forward_inputs(config)
    folds = walk_forward_compare(
        events,
        panel,
        n_splits=args.splits,
        train_fraction=args.train_fraction,
        commission_per_contract=args.commission_per_contract,
    )
    row = {"scenario": scenario, "seed": seed, "folds": len(folds)}
    for label, key in (("fixed", "fixed_spread_metrics"), ("as", "inventory_aware_metrics")):
        metrics = [getattr(fold, key) for fold in folds]
        row[f"{label}_net_pnl"] = sum(m["net_pnl"] for m in metrics)
        row[f"{label}_gross_pnl"] = sum(m["gross_pnl"] for m in metrics)
        row[f"{label}_fees"] = sum(m["fees_paid"] for m in metrics)
        row[f"{label}_fills"] = sum(m["fill_count"] for m in metrics)
        row[f"{label}_max_abs_inventory"] = max(m["max_abs_inventory"] for m in metrics)
    row["fitted_k_mean"] = float(np.mean([f.arrival_calibration.price_sensitivity for f in folds]))
    row["gamma_selected"] = ";".join(f"{f.selected_risk_aversion:g}" for f in folds)
    row["fixed_half_spread_selected"] = ";".join(f"{f.selected_fixed_half_spread:g}" for f in folds)
    row["diff_net_pnl"] = row["as_net_pnl"] - row["fixed_net_pnl"]
    return row


def bootstrap_mean_ci(values: np.ndarray, n_boot: int, seed: int, level: float = 0.95):
    rng = np.random.default_rng(seed)
    draws = rng.choice(values, size=(n_boot, len(values)), replace=True).mean(axis=1)
    tail = (1.0 - level) / 2.0
    return float(np.quantile(draws, tail)), float(np.quantile(draws, 1.0 - tail))


def summarize(seeds: pd.DataFrame, n_boot: int) -> pd.DataFrame:
    rows = []
    for scenario, group in seeds.groupby("scenario", sort=False):
        n = len(group)
        diff = group["diff_net_pnl"].to_numpy(dtype=float)
        lo, hi = bootstrap_mean_ci(diff, n_boot, seed=12345)
        row = {"scenario": scenario, "seeds": n}
        for label in ("fixed", "as"):
            pnl = group[f"{label}_net_pnl"].to_numpy(dtype=float)
            std = float(pnl.std(ddof=1))
            row[f"{label}_total_net_pnl"] = float(pnl.sum())
            row[f"{label}_mean_net_pnl"] = float(pnl.mean())
            row[f"{label}_median_net_pnl"] = float(np.median(pnl))
            row[f"{label}_std_net_pnl"] = std
            row[f"{label}_sharpe_like"] = float(pnl.mean() / std) if std > 0 else float("nan")
            row[f"{label}_mean_max_abs_inventory"] = float(group[f"{label}_max_abs_inventory"].mean())
            row[f"{label}_worst_max_abs_inventory"] = float(group[f"{label}_max_abs_inventory"].max())
            row[f"{label}_mean_fills"] = float(group[f"{label}_fills"].mean())
        for column, name in (("gamma_selected", "gamma"), ("fixed_half_spread_selected", "fixed_half_spread")):
            picks = pd.Series(";".join(group[column]).split(";"))
            counts = picks.value_counts()
            row[f"modal_{name}"] = float(counts.index[0])
            row[f"modal_{name}_share"] = float(counts.iloc[0] / len(picks))
        row["fitted_k_mean"] = float(group["fitted_k_mean"].mean())
        row["as_win_rate"] = float((diff > 0).mean())
        row["mean_diff"] = float(diff.mean())
        row["median_diff"] = float(np.median(diff))
        row["diff_std_error"] = float(diff.std(ddof=1) / np.sqrt(n))
        row["diff_ci95_low"] = lo
        row["diff_ci95_high"] = hi
        row["as_vs_fixed_total_pct"] = (
            100.0 * (row["as_total_net_pnl"] / row["fixed_total_net_pnl"] - 1.0)
            if row["fixed_total_net_pnl"] > 0 else float("nan")
        )
        rows.append(row)
    return pd.DataFrame(rows)


def _fmt(value: float, digits: int = 0) -> str:
    return f"{value:,.{digits}f}"


def render_markdown(summary: pd.DataFrame, args) -> str:
    lines = [
        "# SYNTHETIC walk-forward results: Avellaneda-Stoikov vs fixed spread",
        "",
        "> **SYNTHETIC DATA ONLY.** Every number below comes from simulated quote and",
        "> trade-print streams generated by `options_mm.data.synthetic`. They measure how",
        "> the simulator's two quoting policies behave under the stated generating",
        "> assumptions. They are **not** evidence of profitability on real markets.",
        "",
        "Reproduce:",
        "",
        "```bash",
        f"python scripts/run_synthetic_experiment.py --seeds {args.seeds} --splits {args.splits} "
        f"--train-fraction {args.train_fraction} --commission-per-contract {args.commission_per_contract}",
        "```",
        "",
        "## Setup",
        "",
        f"- Scenarios: {', '.join(args.scenario_list)}; seeds 0-{args.seeds - 1} per scenario "
        "(the same seed shares the same underlying path and noise draws across scenarios).",
        "- One session per seed: 6.5 hours, one event every 5 seconds (4,680 events), a 30-day",
        "  ATM call on a GBM underlying (sigma 25%), fair value = Black-Scholes price.",
        "- Trade prints arrive with probability 0.3 per event; distance from the prior fair value",
        "  is Exponential(k=12 per $); sizes 1 + Poisson(19). Contract multiplier **100**,",
        f"  commission **${args.commission_per_contract:.2f} per contract**.",
        "- `informed`: 30% of prints trade in the direction of the fair-value move over the",
        "  next 10 events. `trending`: underlying drift of 12/yr (about +3 session sigmas)",
        "  with 65% buyer-initiated prints.",
        f"- Walk-forward: {args.splits} expanding-window folds, initial train fraction "
        f"{args.train_fraction}. On each training window k is fitted by Poisson MLE on a",
        "  trade-through panel, gamma is chosen from (0.01, 0.03, 0.1, 0.3, 1.0) and the",
        "  fixed half-spread from (0.01, 0.02, 0.05, 0.1, 0.2) by training net P&L less an",
        "  inventory penalty. Only out-of-sample test folds are reported.",
        "- Fill model: a print through our resting quote fills min(10, 10% of print size)",
        "  contracts, floored to whole lots, subject to a 1,000-contract inventory cap.",
        "  No queue model, no latency.",
        "",
        "## Results (net P&L in $, summed over the 3 out-of-sample folds of each seed)",
        "",
        "| Scenario | Policy | Total net P&L | Mean / seed | Median / seed | Std / seed | Sharpe-like (mean/std) | Mean max abs inventory | Worst max abs inventory |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for _, row in summary.iterrows():
        for label, name in (("fixed", "Fixed spread"), ("as", "A-S")):
            lines.append(
                f"| {row['scenario']} | {name} | {_fmt(row[f'{label}_total_net_pnl'])} | "
                f"{_fmt(row[f'{label}_mean_net_pnl'])} | {_fmt(row[f'{label}_median_net_pnl'])} | "
                f"{_fmt(row[f'{label}_std_net_pnl'])} | {row[f'{label}_sharpe_like']:.2f} | "
                f"{row[f'{label}_mean_max_abs_inventory']:.1f} | {row[f'{label}_worst_max_abs_inventory']:.0f} |"
            )
    lines += [
        "",
        "## Paired difference (A-S minus fixed, per seed)",
        "",
        "| Scenario | A-S wins | Mean diff | Median diff | Std error | 95% bootstrap CI of mean | A-S vs fixed total |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for _, row in summary.iterrows():
        pct = row["as_vs_fixed_total_pct"]
        lines.append(
            f"| {row['scenario']} | {int(round(row['as_win_rate'] * row['seeds']))}/{int(row['seeds'])} | "
            f"{_fmt(row['mean_diff'])} | {_fmt(row['median_diff'])} | {_fmt(row['diff_std_error'])} | "
            f"[{_fmt(row['diff_ci95_low'])}, {_fmt(row['diff_ci95_high'])}] | "
            f"{'n/a' if pd.isna(pct) else f'{pct:+.1f}%'} |"
        )
    lines += [
        "",
        f"Bootstrap: {args.bootstrap:,} resamples of the per-seed paired differences, percentile",
        "interval. With 20 seeds the interval is wide; a CI that contains 0 means the",
        "difference is not distinguishable from noise in this experiment.",
        "",
        "## Parameters selected on training windows",
        "",
        "| Scenario | Mean fitted k (true 12) | Most-selected gamma (share of folds) | Most-selected fixed half-spread (share of folds) |",
        "|---|---:|---:|---:|",
    ]
    for _, row in summary.iterrows():
        lines.append(
            f"| {row['scenario']} | {row['fitted_k_mean']:.2f} | {row['modal_gamma']:g} "
            f"({100 * row['modal_gamma_share']:.0f}%) | {row['modal_fixed_half_spread']:g} "
            f"({100 * row['modal_fixed_half_spread_share']:.0f}%) |"
        )
    lines += [
        "",
        "Grid edges: gamma grid (0.01, 0.03, 0.1, 0.3, 1.0); fixed grid (0.01, 0.02, 0.05, 0.1, 0.2).",
        "A selection at a grid edge means the optimum may lie outside the searched range.",
        "",
        "## Caveats",
        "",
        "- The arrival model fitted by the A-S policy is the model that generated the data",
        "  (exponential trade-through decay), which favours A-S relative to real markets.",
        "- Fair value and premium volatility are known exactly; on real data both are estimated.",
        "- Sharpe-like is mean/std of per-seed session P&L, not an annualised Sharpe ratio.",
        "- Per-seed rows are in `synthetic_walkforward_seeds.csv`; the summary is in",
        "  `synthetic_walkforward.csv`.",
        "",
    ]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--scenarios", default=",".join(SCENARIOS))
    parser.add_argument("--seeds", type=int, default=20, help="run seeds 0..N-1")
    parser.add_argument("--splits", type=int, default=3)
    parser.add_argument("--train-fraction", type=float, default=0.6)
    parser.add_argument("--commission-per-contract", type=float, default=0.65)
    parser.add_argument("--n-events", type=int, default=None, help="override events per session")
    parser.add_argument("--bootstrap", type=int, default=10_000)
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    args = parser.parse_args(argv)
    args.scenario_list = [item.strip() for item in args.scenarios.split(",") if item.strip()]
    unknown = set(args.scenario_list).difference(SCENARIOS)
    if unknown:
        parser.error(f"unknown scenario(s): {', '.join(sorted(unknown))}; choose from {', '.join(SCENARIOS)}")

    rows = []
    for scenario in args.scenario_list:
        for seed in range(args.seeds):
            rows.append(run_seed(scenario, seed, args))
            print(f"{scenario} seed {seed}: fixed={rows[-1]['fixed_net_pnl']:.0f} A-S={rows[-1]['as_net_pnl']:.0f}")
    seeds = pd.DataFrame(rows)
    summary = summarize(seeds, args.bootstrap)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    seeds.to_csv(args.output_dir / "synthetic_walkforward_seeds.csv", index=False, float_format="%.4f")
    summary.to_csv(args.output_dir / "synthetic_walkforward.csv", index=False, float_format="%.4f")
    (args.output_dir / "synthetic_walkforward.md").write_text(render_markdown(summary, args), encoding="utf-8")
    print(f"Wrote results to {args.output_dir}/synthetic_walkforward.md")
    return summary


if __name__ == "__main__":
    main()
