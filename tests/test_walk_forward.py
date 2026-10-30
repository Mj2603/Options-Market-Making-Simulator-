import numpy as np
import pandas as pd
import pytest

from options_mm.experiments.walk_forward import walk_forward_compare
from options_mm.simulation.event_driven import MarketEvent


def make_events():
    events = []
    for timestamp in range(20):
        if timestamp == 0:
            events.append(MarketEvent(
                timestamp=timestamp, instrument="OPT", fair_value=10.0,
                price_volatility=0.5, time_to_horizon=0.2,
            ))
        else:
            events.append(MarketEvent(
                timestamp=timestamp, instrument="OPT", fair_value=10.0,
                price_volatility=0.5, time_to_horizon=0.2,
                trade_price=0.0, trade_size=2.0, aggressor_side="sell",
            ))
    return events


def make_arrival_panel():
    rows = []
    for timestamp in range(20):
        for distance, count in ((0.05, 8), (0.10, 5), (0.15, 3), (0.20, 1)):
            rows.append({
                "timestamp": timestamp,
                "quote_distance": distance,
                "arrival_count": count,
                "exposure_seconds": 60.0,
            })
    return pd.DataFrame(rows)


def test_walk_forward_calibrates_only_on_prior_data_and_compares_models():
    folds = walk_forward_compare(
        make_events(),
        make_arrival_panel(),
        n_splits=2,
        train_fraction=0.5,
        risk_aversion_grid=(0.01, 0.1),
        order_size=1.0,
        participation_rate=0.5,
    )
    assert len(folds) == 2
    assert folds[0].train_end < folds[0].test_start
    assert folds[1].train_end < folds[1].test_start
    assert folds[0].arrival_calibration.price_sensitivity > 0.0
    assert folds[0].selected_risk_aversion in (0.01, 0.1)
    assert "net_pnl" in folds[0].fixed_spread_metrics
    assert "net_pnl" in folds[0].inventory_aware_metrics


def test_walk_forward_rejects_missing_timestamp_in_calibration_panel():
    with pytest.raises(ValueError, match="timestamp"):
        walk_forward_compare(make_events(), pd.DataFrame({
            "quote_distance": [0.1],
            "arrival_count": [1],
            "exposure_seconds": [1.0],
        }))
