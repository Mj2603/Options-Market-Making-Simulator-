from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from options_mm.calibration import calibrate_exponential_arrivals
from options_mm.data.loader import load_option_ticks_csv
from options_mm.data.synthetic import (
    SCENARIOS,
    build_synthetic_arrival_panel,
    generate_research_events,
    generate_sample_ticks,
    scenario_config,
    synthetic_walk_forward_inputs,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_generator_is_deterministic_per_seed(scenario):
    first = generate_research_events(scenario_config(scenario, seed=7, n_events=500))
    second = generate_research_events(scenario_config(scenario, seed=7, n_events=500))
    other = generate_research_events(scenario_config(scenario, seed=8, n_events=500))
    pd.testing.assert_frame_equal(first, second)
    assert not first["fair_value"].equals(other["fair_value"])


def test_generated_events_pass_research_validation():
    frame, events, panel = synthetic_walk_forward_inputs(
        scenario_config("random_walk", seed=0, n_events=500)
    )
    assert len(events) == 500
    assert all(event.contract_multiplier == 100.0 for event in events)
    assert (frame["data_provider"] == "synthetic").all()
    assert {"timestamp", "quote_distance", "arrival_count", "exposure_seconds"} <= set(panel)


def test_arrival_calibration_recovers_generating_k():
    events = generate_research_events(scenario_config("random_walk", seed=1))
    fit = calibrate_exponential_arrivals(build_synthetic_arrival_panel(events))
    assert fit.price_sensitivity == pytest.approx(12.0, rel=0.15)


def test_scenarios_differ_in_order_flow():
    def sides(scenario):
        frame = generate_research_events(scenario_config(scenario, seed=2))
        trades = frame.loc[frame["trade_size"] > 0]
        return frame, trades
    rw_frame, rw = sides("random_walk")
    tr_frame, tr = sides("trending")
    inf_frame, inf = sides("informed")
    assert (tr["aggressor_side"] == "buy").mean() > (rw["aggressor_side"] == "buy").mean() + 0.08
    assert tr_frame["underlying_price"].iloc[-1] > rw_frame["underlying_price"].iloc[-1]

    def flow_alignment(frame, trades, horizon=10):
        fair = frame["fair_value"].to_numpy()
        idx = trades.index.to_numpy()
        idx = idx[idx + horizon < len(fair)]
        move = np.sign(fair[idx + horizon] - fair[idx])
        side = np.where(frame.loc[idx, "aggressor_side"] == "buy", 1.0, -1.0)
        return float(np.mean(move * side))
    assert flow_alignment(inf_frame, inf) > flow_alignment(rw_frame, rw) + 0.15


def test_unknown_scenario_rejected():
    with pytest.raises(ValueError):
        scenario_config("bogus")


def test_committed_sample_ticks_match_generator_and_load():
    path = REPO_ROOT / "data" / "sample_ticks.csv"
    committed = pd.read_csv(path)
    regenerated = pd.read_csv(pd.io.common.StringIO(generate_sample_ticks(seed=0).to_csv(index=False)))
    pd.testing.assert_frame_equal(committed, regenerated)
    loaded = load_option_ticks_csv(path)
    assert len(loaded) == len(committed)
    assert (loaded["time_to_expiry"] > 0).all()
