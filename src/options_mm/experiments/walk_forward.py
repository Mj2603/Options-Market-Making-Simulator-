"""Chronological walk-forward comparison of fixed and inventory-aware quotes."""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

import pandas as pd

from options_mm.calibration import ArrivalCalibration, calibrate_exponential_arrivals
from options_mm.execution.queue import L1QueueModel
from options_mm.market.avellaneda_stoikov import AvellanedaStoikovQuoteModel
from options_mm.market.policies import FixedSpreadQuoteModel
from options_mm.metrics.research import performance_summary
from options_mm.simulation.event_driven import EventDrivenBacktest, MarketEvent


@dataclass(frozen=True)
class WalkForwardFold:
    fold: int
    train_start: float
    train_end: float
    test_start: float
    test_end: float
    arrival_calibration: ArrivalCalibration
    selected_risk_aversion: float
    fixed_spread_metrics: dict
    inventory_aware_metrics: dict


def _inventory_penalty(result) -> float:
    inventory = {}
    squared = []
    for fill in result.fills:
        signed = fill.size if fill.side == "buy" else -fill.size
        inventory[fill.instrument] = inventory.get(fill.instrument, 0.0) + signed
        squared.append(inventory[fill.instrument] ** 2)
    return sum(squared) / len(squared) if squared else 0.0


def _select_gamma(
    training_events: list[MarketEvent],
    price_sensitivity: float,
    gamma_grid: tuple[float, ...],
    order_size: float,
    participation_rate: float,
    inventory_penalty: float,
) -> float:
    best_gamma = None
    best_score = -math.inf
    for gamma in gamma_grid:
        model = AvellanedaStoikovQuoteModel(
            risk_aversion=gamma,
            order_arrival_intensity=price_sensitivity,
        )
        result = EventDrivenBacktest(
            quote_model=model,
            order_size=order_size,
            participation_rate=participation_rate,
            queue_model=queue_model,
        ).run(training_events)
        score = result.net_total_pnl - inventory_penalty * _inventory_penalty(result)
        if score > best_score:
            best_score, best_gamma = score, gamma
    if best_gamma is None:
        raise RuntimeError("risk-aversion grid did not produce a valid model")
    return float(best_gamma)


def walk_forward_compare(
    events: Iterable[MarketEvent],
    arrival_observations: pd.DataFrame,
    n_splits: int = 3,
    train_fraction: float = 0.6,
    risk_aversion_grid: tuple[float, ...] = (0.01, 0.03, 0.1, 0.3, 1.0),
    fixed_half_spread: float = 0.05,
    order_size: float = 10.0,
    participation_rate: float = 0.1,
    inventory_penalty: float = 0.01,
    latency_seconds: float = 0.0,
    queue_aware: bool = False,
) -> list[WalkForwardFold]:
    """Run expanding-window tests with calibration/tuning restricted to train.

    arrival_observations must contain timestamp plus quote_distance,
    arrival_count, and exposure_seconds. Each test fold is strictly later than
    its training window. A single observation panel row is never allowed to
    enter both train and test calibration. This function expects caller-built
    arrival exposures from real or explicitly labelled simulated data.
    """
    ordered = sorted(events, key=lambda item: item.timestamp)
    if not math.isfinite(inventory_penalty) or inventory_penalty < 0.0:
        raise ValueError("inventory_penalty must be finite and non-negative")
    if not math.isfinite(latency_seconds) or latency_seconds < 0.0:
        raise ValueError("latency_seconds must be finite and non-negative")
    if queue_aware and any(
        event.market_bid is None or event.market_ask is None for event in ordered
    ):
        raise ValueError("queue_aware requires NBBO bid/ask on every event")
    queue_model = (
        L1QueueModel(latency_seconds=latency_seconds)
        if queue_aware or latency_seconds > 0.0 else None
    )
    if len(ordered) < 10:
        raise ValueError("at least 10 market events are required")
    if "timestamp" not in arrival_observations:
        raise ValueError("arrival_observations requires timestamp")
    if n_splits < 1:
        raise ValueError("n_splits must be positive")
    if not 0.2 <= train_fraction < 0.9:
        raise ValueError("train_fraction must be in [0.2, 0.9)")
    if not risk_aversion_grid or any(
        not math.isfinite(float(gamma)) or gamma <= 0.0
        for gamma in risk_aversion_grid
    ):
        raise ValueError("risk_aversion_grid must contain positive finite values")

    times = sorted({event.timestamp for event in ordered})
    initial_train_end = max(2, int(len(times) * train_fraction))
    remaining = len(times) - initial_train_end
    if remaining < n_splits:
        raise ValueError("not enough post-training timestamps for requested folds")
    fold_size = max(1, remaining // n_splits)
    panel = arrival_observations.copy()
    panel["timestamp"] = pd.to_numeric(panel["timestamp"], errors="coerce")
    if panel["timestamp"].isna().any():
        raise ValueError("arrival panel timestamps must be numeric Unix seconds")

    folds = []
    for fold_index in range(n_splits):
        train_end_idx = initial_train_end + fold_index * fold_size
        test_end_idx = (
            len(times) if fold_index == n_splits - 1
            else min(len(times), train_end_idx + fold_size)
        )
        train_times = set(times[:train_end_idx])
        test_times = set(times[train_end_idx:test_end_idx])
        if not test_times:
            continue
        train_events = [event for event in ordered if event.timestamp in train_times]
        test_events = [event for event in ordered if event.timestamp in test_times]
        train_end = max(train_times)
        test_start, test_end = min(test_times), max(test_times)
        train_panel = panel.loc[panel["timestamp"] <= train_end]
        if train_panel.empty:
            raise ValueError("no arrival calibration observations in training window")
        calibration = calibrate_exponential_arrivals(train_panel)
        gamma = _select_gamma(
            train_events,
            calibration.price_sensitivity,
            risk_aversion_grid,
            order_size,
            participation_rate,
            inventory_penalty,
        )

        fixed_result = EventDrivenBacktest(
            quote_model=FixedSpreadQuoteModel(fixed_half_spread),
            order_size=order_size,
            participation_rate=participation_rate,
            queue_model=queue_model,
        ).run(test_events)
        as_result = EventDrivenBacktest(
            quote_model=AvellanedaStoikovQuoteModel(
                risk_aversion=gamma,
                order_arrival_intensity=calibration.price_sensitivity,
            ),
            order_size=order_size,
            participation_rate=participation_rate,
        ).run(test_events)
        folds.append(
            WalkForwardFold(
                fold=fold_index + 1,
                train_start=min(train_times),
                train_end=train_end,
                test_start=test_start,
                test_end=test_end,
                arrival_calibration=calibration,
                selected_risk_aversion=gamma,
                fixed_spread_metrics=performance_summary(fixed_result, test_events),
                inventory_aware_metrics=performance_summary(as_result, test_events),
            )
        )
    return folds
