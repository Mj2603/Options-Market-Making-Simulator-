"""Run the fixed-spread versus inventory-aware walk-forward experiment.

Real data: build data/processed/research_events.csv and arrival_panel.csv
with the Alpaca pipeline (see README). Without licensed data, pass
--synthetic {random_walk,informed,trending} to generate a deterministic,
clearly labelled SYNTHETIC session instead.
"""
import argparse
from dataclasses import asdict
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from options_mm.data.research import load_research_events_csv, to_market_events
from options_mm.data.synthetic import SCENARIOS, scenario_config, synthetic_walk_forward_inputs
from options_mm.experiments.walk_forward import walk_forward_compare
from options_mm.risk.portfolio import PortfolioRiskManager


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--synthetic", choices=SCENARIOS,
        help="use a generated SYNTHETIC session instead of --events/--arrival-panel",
    )
    parser.add_argument("--seed", type=int, default=0, help="seed for --synthetic")
    parser.add_argument("--events", type=Path, default=Path("data/processed/research_events.csv"))
    parser.add_argument("--arrival-panel", type=Path, default=Path("data/processed/arrival_panel.csv"))
    parser.add_argument(
        "--output", type=Path, default=None,
        help="JSON output (default reports/walk_forward.json, or "
        "reports/walk_forward_synthetic_<scenario>_seed<seed>.json with --synthetic)",
    )
    parser.add_argument("--source-metadata", type=Path, default=Path("data/raw/alpaca/metadata.json"))
    parser.add_argument("--splits", type=int, default=3)
    parser.add_argument("--train-fraction", type=float, default=0.6)
    parser.add_argument("--gamma-grid", default="0.01,0.03,0.1,0.3,1.0")
    parser.add_argument("--fixed-spread-grid", default="0.01,0.02,0.05,0.1,0.2")
    parser.add_argument("--order-size", type=float, default=10.0)
    parser.add_argument("--participation-rate", type=float, default=0.1)
    parser.add_argument("--inventory-penalty", type=float, default=0.01)
    parser.add_argument("--latency-seconds", type=float, default=0.0)
    parser.add_argument("--queue-aware", action="store_true")
    parser.add_argument("--commission-per-contract", type=float, default=0.65)
    parser.add_argument("--max-abs-delta", type=float)
    parser.add_argument("--max-abs-gamma", type=float)
    parser.add_argument("--max-abs-vega", type=float)
    parser.add_argument("--max-abs-theta", type=float)
    parser.add_argument("--max-gross-market-value", type=float)
    parser.add_argument("--max-underlying-gross-value", type=float)
    args = parser.parse_args(argv)

    if args.synthetic:
        event_frame, events, panel = synthetic_walk_forward_inputs(
            scenario_config(args.synthetic, args.seed)
        )
        args.events = Path(f"<synthetic:{args.synthetic}:seed={args.seed}>")
        args.arrival_panel = args.events
        if args.output is None:
            args.output = Path(
                f"reports/walk_forward_synthetic_{args.synthetic}_seed{args.seed}.json"
            )
        print(f"Using SYNTHETIC data: scenario={args.synthetic}, seed={args.seed}")
    else:
        missing = [path for path in (args.events, args.arrival_panel) if not path.exists()]
        if missing:
            parser.exit(2, (
                "error: real market data not found: "
                + ", ".join(str(path) for path in missing)
                + "\nBuild it with scripts/download_alpaca_options.py, "
                "scripts/prepare_alpaca_research_data.py and scripts/build_arrival_panel.py "
                "(requires Alpaca API keys), or run on generated data with\n"
                "  python scripts/run_walk_forward.py --synthetic random_walk\n"
            ))
        event_frame = load_research_events_csv(args.events)
        events = to_market_events(event_frame)
        panel = pd.read_csv(args.arrival_panel)
        if args.output is None:
            args.output = Path("reports/walk_forward.json")
    risk_values = {
        "max_abs_delta": args.max_abs_delta,
        "max_abs_gamma": args.max_abs_gamma,
        "max_abs_vega": args.max_abs_vega,
        "max_abs_theta": args.max_abs_theta,
        "max_gross_market_value": args.max_gross_market_value,
        "max_underlying_gross_value": args.max_underlying_gross_value,
    }
    portfolio_risk_manager = (
        PortfolioRiskManager(**{
            key: value for key, value in risk_values.items() if value is not None
        })
        if any(value is not None for value in risk_values.values())
        else None
    )
    results = walk_forward_compare(
        events,
        panel,
        n_splits=args.splits,
        train_fraction=args.train_fraction,
        risk_aversion_grid=tuple(float(x) for x in args.gamma_grid.split(",")),
        fixed_spread_grid=tuple(float(x) for x in args.fixed_spread_grid.split(",")),
        order_size=args.order_size,
        participation_rate=args.participation_rate,
        inventory_penalty=args.inventory_penalty,
        latency_seconds=args.latency_seconds,
        queue_aware=args.queue_aware,
        commission_per_contract=args.commission_per_contract,
        portfolio_risk_manager=portfolio_risk_manager,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    source_metadata = (
        json.loads(args.source_metadata.read_text(encoding="utf-8"))
        if not args.synthetic and args.source_metadata.exists()
        else {
            "provider": sorted(event_frame["data_provider"].dropna().unique().tolist())
            if "data_provider" in event_frame else ["unspecified"],
            "feed": sorted(event_frame["data_feed"].dropna().unique().tolist())
            if "data_feed" in event_frame else ["unspecified"],
        }
    )
    payload = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "synthetic": bool(args.synthetic),
        "source_metadata": source_metadata,
        "configuration": {
            "synthetic_scenario": args.synthetic,
            "synthetic_seed": args.seed if args.synthetic else None,
            "events_file": str(args.events),
            "arrival_panel_file": str(args.arrival_panel),
            "n_splits": args.splits,
            "train_fraction": args.train_fraction,
            "gamma_grid": [float(x) for x in args.gamma_grid.split(",")],
            "fixed_spread_grid": [float(x) for x in args.fixed_spread_grid.split(",")],
            "order_size": args.order_size,
            "participation_rate": args.participation_rate,
            "inventory_penalty": args.inventory_penalty,
            "latency_seconds": args.latency_seconds,
            "queue_aware": args.queue_aware,
            "commission_per_contract": args.commission_per_contract,
            "portfolio_risk_limits": risk_values,
        },
        "folds": [asdict(fold) for fold in results],
    }
    args.output.write_text(json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8")
    print(f"Wrote {len(results)} walk-forward folds to {args.output}")
    for fold in results:
        fixed = fold.fixed_spread_metrics
        aware = fold.inventory_aware_metrics
        print(
            f"Fold {fold.fold}: fixed net PnL={fixed['net_pnl']:.2f}, "
            f"A-S net PnL={aware['net_pnl']:.2f}, gamma={fold.selected_risk_aversion:.4g}"
        )
    return results


if __name__ == "__main__":
    main()
