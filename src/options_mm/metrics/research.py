"""Performance and execution diagnostics for event-driven backtests."""
from __future__ import annotations

import math
from typing import Iterable

import numpy as np
import pandas as pd

from options_mm.execution.queue import signed_markout
from options_mm.simulation.event_driven import MarketEvent, SimulationResult


def compute_markouts(
    fills,
    events: Iterable[MarketEvent],
    horizons_seconds: tuple[float, ...] = (1.0, 5.0, 30.0),
) -> dict[float, dict[str, float | int]]:
    """Compute maker-side markouts at the first observation after each horizon.

    Future observations are used only for evaluation, never for quote
    generation. Missing future observations are omitted rather than forward
    filled. A negative mean markout indicates adverse selection.
    """
    ordered = sorted(events, key=lambda item: item.timestamp)
    output = {}
    for horizon in horizons_seconds:
        values = []
        for fill in fills:
            target = fill.timestamp + float(horizon)
            future = next(
                (
                    event for event in ordered
                    if event.instrument == fill.instrument and event.timestamp >= target
                ),
                None,
            )
            if future is None:
                continue
            values.append(signed_markout(fill.side, fill.price, future.fair_value))
        output[float(horizon)] = {
            "count": len(values),
            "mean": float(np.mean(values)) if values else float("nan"),
            "median": float(np.median(values)) if values else float("nan"),
            "adverse_selection_rate": (
                float(np.mean(np.asarray(values) < 0.0)) if values else float("nan")
            ),
        }
    return output


def performance_summary(
    result: SimulationResult,
    events: Iterable[MarketEvent],
    initial_capital: float = 1_000_000.0,
    periods_per_year: float = 252.0,
) -> dict[str, float | int]:
    """Return net performance, drawdown, inventory, fill, and markout metrics.

    Sharpe and drawdown are computed from daily last observations to avoid
    treating irregular event timestamps as equally spaced returns. For
    intraday research, pass a regularized equity series instead of interpreting
    this daily metric as a high-frequency Sharpe.
    """
    initial_capital = float(initial_capital)
    periods_per_year = float(periods_per_year)
    if not math.isfinite(initial_capital) or initial_capital <= 0.0:
        raise ValueError("initial_capital must be positive and finite")
    if not math.isfinite(periods_per_year) or periods_per_year <= 0.0:
        raise ValueError("periods_per_year must be positive and finite")

    event_list = list(events)
    equity = pd.DataFrame(
        [
            {"timestamp": pd.to_datetime(point.timestamp, unit="s", utc=True),
             "equity": initial_capital + point.net_pnl}
            for point in result.equity_curve
        ]
    )
    if equity.empty:
        daily_returns = pd.Series(dtype=float)
        max_drawdown = 0.0
    else:
        daily = (
            equity.sort_values("timestamp")
            .set_index("timestamp")["equity"]
            .resample("1D")
            .last()
            .dropna()
        )
        daily_returns = daily.pct_change().dropna()
        running_peak = daily.cummax()
        drawdowns = daily / running_peak - 1.0
        max_drawdown = float(drawdowns.min()) if len(drawdowns) else 0.0

    volatility = float(daily_returns.std(ddof=1)) if len(daily_returns) > 1 else 0.0
    sharpe = (
        float(daily_returns.mean() / volatility * math.sqrt(periods_per_year))
        if volatility > 0.0 else 0.0
    )

    positions = np.asarray([abs(value) for _, value in result.final_positions], dtype=float)
    inventory_path = []
    running = {}
    for fill in result.fills:
        signed = fill.size if fill.side == "buy" else -fill.size
        running[fill.instrument] = running.get(fill.instrument, 0.0) + signed
        inventory_path.append(abs(running[fill.instrument]))
    trades = sum(1 for event in event_list if event.trade_size > 0.0)
    markouts = compute_markouts(result.fills, event_list)
    return {
        "net_pnl": float(result.net_total_pnl),
        "gross_pnl": float(result.gross_total_pnl),
        "fees_paid": float(result.fees_paid),
        "sharpe_daily": sharpe,
        "max_drawdown": max_drawdown,
        "fill_count": len(result.fills),
        "eligible_trade_prints": trades,
        "fill_per_trade_print": (
            float(len(result.fills) / trades) if trades else 0.0
        ),
        "max_abs_inventory": float(max(inventory_path, default=0.0)),
        "mean_abs_inventory_after_fill": (
            float(np.mean(inventory_path)) if inventory_path else 0.0
        ),
        "final_gross_abs_inventory": float(positions.sum()),
        "markout_1s": float(markouts.get(1.0, {}).get("mean", float("nan"))),
        "markout_5s": float(markouts.get(5.0, {}).get("mean", float("nan"))),
        "markout_30s": float(markouts.get(30.0, {}).get("mean", float("nan"))),
    }
