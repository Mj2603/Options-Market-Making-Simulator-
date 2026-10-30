"""Run the fixed-spread versus inventory-aware walk-forward experiment."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path

import pandas as pd

from options_mm.data.research import load_research_events_csv, to_market_events
from options_mm.experiments.walk_forward import walk_forward_compare
from options_mm.risk.portfolio import PortfolioRiskManager


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", type=Path, default=Path("data/processed/research_events.csv"))
    parser.add_argument("--arrival-panel", type=Path, default=Path("data/processed/arrival_panel.csv"))
    parser.add_argument("--output", type=Path, default=Path("reports/walk_forward.json"))
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
    parser.add_argument("--max-gross-market-value", type=float)
    parser.add_argument("--max-underlying-gross-value", type=float)
    args = parser.parse_args()

    event_frame = load_research_events_csv(args.events)
    events = to_market_events(event_frame)
    panel = pd.read_csv(args.arrival_panel)
    risk_values = {
        "max_abs_delta": args.max_abs_delta,
        "max_abs_gamma": args.max_abs_gamma,
        "max_abs_vega": args.max_abs_vega,
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
    payload = [asdict(fold) for fold in results]
    args.output.write_text(json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8")
    print(f"Wrote {len(results)} walk-forward folds to {args.output}")
    for fold in results:
        fixed = fold.fixed_spread_metrics
        aware = fold.inventory_aware_metrics
        print(
            f"Fold {fold.fold}: fixed net PnL={fixed['net_pnl']:.2f}, "
            f"A-S net PnL={aware['net_pnl']:.2f}, gamma={fold.selected_risk_aversion:.4g}"
        )


if __name__ == "__main__":
    main()
