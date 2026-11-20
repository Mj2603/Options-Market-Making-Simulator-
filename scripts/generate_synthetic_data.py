"""Write deterministic SYNTHETIC data files.

Default: regenerate data/sample_ticks.csv (the small option-chain snapshot
used by scripts/run_phase1.py and benchmarks/benchmark_simulator.py).
With --research-events SCENARIO also write a synthetic research-event CSV
and arrival panel in the format scripts/run_walk_forward.py reads.
"""
import argparse
from pathlib import Path

from options_mm.data.synthetic import (
    SCENARIOS,
    build_synthetic_arrival_panel,
    generate_research_events,
    generate_sample_ticks,
    scenario_config,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--sample-ticks", type=Path, default=Path("data/sample_ticks.csv"))
    parser.add_argument("--research-events", choices=SCENARIOS)
    parser.add_argument("--output-dir", type=Path, default=Path("data/synthetic"))
    args = parser.parse_args(argv)

    args.sample_ticks.parent.mkdir(parents=True, exist_ok=True)
    generate_sample_ticks(seed=args.seed).to_csv(args.sample_ticks, index=False)
    print(f"Wrote SYNTHETIC sample ticks to {args.sample_ticks}")
    if args.research_events:
        events = generate_research_events(scenario_config(args.research_events, args.seed))
        args.output_dir.mkdir(parents=True, exist_ok=True)
        events_path = args.output_dir / f"research_events_{args.research_events}_seed{args.seed}.csv"
        panel_path = args.output_dir / f"arrival_panel_{args.research_events}_seed{args.seed}.csv"
        events.to_csv(events_path, index=False)
        build_synthetic_arrival_panel(events).to_csv(panel_path, index=False)
        print(f"Wrote SYNTHETIC events to {events_path} and arrival panel to {panel_path}")


if __name__ == "__main__":
    main()
