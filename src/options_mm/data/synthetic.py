"""Deterministic synthetic option quote/trade-print generator.

Everything produced here is SYNTHETIC. It exists so that the walk-forward
pipeline, demo scripts, and benchmarks can be run end to end without
licensed market data. Results computed on these data describe the behaviour
of the simulator under the stated generating assumptions, not the
profitability of any strategy in a real market.

Generating model (one session, one European call):

* The underlying follows a discretised GBM with annualised volatility
  ``underlying_volatility`` and drift ``drift`` (zero except in "trending").
* The option fair value is its Black-Scholes price; ``price_volatility`` is
  ``|delta| * S * sigma`` (premium volatility in price units per sqrt-year).
* At each event a trade print arrives with probability ``trade_probability``.
  Its distance from the previous fair value (the reference of the resting
  quote) is Exponential(rate=k), so trade-through intensity decays as
  ``exp(-k * distance)``, which is the arrival model the A-S calibration fits.
* Aggressor side depends on the scenario:
    - ``random_walk``: buy/sell with probability 1/2, independent of prices.
    - ``informed``: a fraction ``informed_fraction`` of prints trade in the
      direction of the fair-value change over the next ``informed_horizon``
      events (adverse selection); the rest are uninformed.
    - ``trending``: the underlying drifts upward and aggressors buy with
      probability ``trend_buy_probability`` (momentum flow).
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import math

import numpy as np
import pandas as pd
from scipy.stats import norm

SCENARIOS = ("random_walk", "informed", "trending")
SECONDS_PER_YEAR = 365.25 * 24 * 60 * 60
TRADING_SECONDS_PER_YEAR = 252 * 6.5 * 60 * 60


@dataclass(frozen=True)
class SyntheticConfig:
    scenario: str = "random_walk"
    seed: int = 0
    n_events: int = 4680
    event_interval_seconds: float = 5.0
    start: str = "2026-01-05T14:30:00Z"
    instrument: str = "SYNTH-C100"
    underlying_symbol: str = "SYNTH"
    spot: float = 100.0
    strike: float = 100.0
    days_to_expiry: float = 30.0
    underlying_volatility: float = 0.25
    risk_free_rate: float = 0.01
    drift: float = 0.0
    trade_probability: float = 0.3
    trade_distance_k: float = 12.0
    mean_trade_size: float = 20.0
    contract_multiplier: float = 100.0
    informed_fraction: float = 0.0
    informed_horizon: int = 10
    trend_buy_probability: float = 0.5

    def __post_init__(self) -> None:
        if self.scenario not in SCENARIOS:
            raise ValueError(f"scenario must be one of {', '.join(SCENARIOS)}")
        if self.n_events < 10:
            raise ValueError("n_events must be at least 10")
        if not 0.0 < self.trade_probability <= 1.0:
            raise ValueError("trade_probability must be in (0, 1]")
        if self.trade_distance_k <= 0.0 or self.contract_multiplier <= 0.0:
            raise ValueError("trade_distance_k and contract_multiplier must be positive")


def scenario_config(scenario: str, seed: int = 0, **overrides) -> SyntheticConfig:
    """Return the documented default configuration for a named scenario."""
    if scenario not in SCENARIOS:
        raise ValueError(f"scenario must be one of {', '.join(SCENARIOS)}")
    base = SyntheticConfig(scenario=scenario, seed=int(seed))
    if scenario == "informed":
        base = replace(base, informed_fraction=0.3)
    elif scenario == "trending":
        # Roughly a +3 standard-deviation session move with buy-side flow.
        base = replace(base, drift=12.0, trend_buy_probability=0.65)
    return replace(base, **overrides)


def _bs_call(spot, strike, rate, vol, tau):
    tau = np.maximum(tau, 1e-10)
    sqrt_tau = np.sqrt(tau)
    d1 = (np.log(spot / strike) + (rate + 0.5 * vol**2) * tau) / (vol * sqrt_tau)
    d2 = d1 - vol * sqrt_tau
    price = spot * norm.cdf(d1) - strike * np.exp(-rate * tau) * norm.cdf(d2)
    return price, norm.cdf(d1)


def generate_research_events(config: SyntheticConfig) -> pd.DataFrame:
    """Generate canonical research-event rows (see data.research).

    The output passes ``load_research_events_csv`` validation and can be
    converted with ``to_market_events``. Same config -> identical frame.
    """
    rng = np.random.default_rng(config.seed)
    n = config.n_events
    dt_trading = config.event_interval_seconds / TRADING_SECONDS_PER_YEAR
    shocks = rng.standard_normal(n)
    shocks[0] = 0.0
    sigma = config.underlying_volatility
    log_steps = (config.drift - 0.5 * sigma**2) * dt_trading + sigma * math.sqrt(dt_trading) * shocks
    spot = config.spot * np.exp(np.cumsum(log_steps))

    elapsed = np.arange(n) * config.event_interval_seconds
    tau = config.days_to_expiry / 365.25 - elapsed / SECONDS_PER_YEAR
    fair, delta = _bs_call(spot, config.strike, config.risk_free_rate, sigma, tau)
    price_vol = np.abs(delta) * spot * sigma
    session_seconds = n * config.event_interval_seconds
    horizon = (session_seconds - elapsed) / TRADING_SECONDS_PER_YEAR

    has_trade = rng.random(n) < config.trade_probability
    has_trade[0] = False
    distances = rng.exponential(1.0 / config.trade_distance_k, n)
    sizes = 1.0 + rng.poisson(config.mean_trade_size - 1.0, n)
    side_draw = rng.random(n)
    informed_draw = rng.random(n)

    buy_probability = 0.5 if config.scenario != "trending" else config.trend_buy_probability
    is_buy = side_draw < buy_probability
    if config.scenario == "informed" and config.informed_fraction > 0.0:
        h = max(1, int(config.informed_horizon))
        future = np.concatenate([fair[h:], np.repeat(fair[-1], h)])
        move = future - fair
        informed = informed_draw < config.informed_fraction
        is_buy = np.where(informed & (move != 0.0), move > 0.0, is_buy)

    reference = np.concatenate([[fair[0]], fair[:-1]])
    trade_price = np.where(is_buy, reference + distances, np.maximum(0.0, reference - distances))

    start = pd.Timestamp(config.start)
    timestamps = start + pd.to_timedelta(elapsed, unit="s")
    frame = pd.DataFrame({
        "timestamp": timestamps.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "instrument": config.instrument,
        "underlying": config.underlying_symbol,
        "underlying_price": np.round(spot, 6),
        "fair_value": np.round(fair, 6),
        "price_volatility": np.round(price_vol, 6),
        "time_to_horizon": horizon,
        "trade_price": np.where(has_trade, np.round(trade_price, 6), np.nan),
        "trade_size": np.where(has_trade, sizes, 0.0),
        "aggressor_side": np.where(has_trade, np.where(is_buy, "buy", "sell"), ""),
        "contract_multiplier": config.contract_multiplier,
        "data_provider": "synthetic",
        "data_feed": f"synthetic:{config.scenario}:seed={config.seed}",
    })
    frame.loc[~has_trade, "aggressor_side"] = None
    return frame


def build_synthetic_arrival_panel(
    events: pd.DataFrame,
    quote_distances: tuple[float, ...] = (0.0, 0.02, 0.05, 0.1, 0.15, 0.2, 0.3),
) -> pd.DataFrame:
    """Trade-through exposure panel from the generated events.

    For each interval between consecutive events, a hypothetical quote at
    +/- distance around the earlier event's fair value is exposed for the
    interval length; a print at the later event counts as an arrival if it
    reaches that level. This mirrors ``experiments.arrival_panel`` semantics.
    """
    ts = pd.to_datetime(events["timestamp"], utc=True)
    seconds = (ts.astype("int64") / 1e9).to_numpy()
    fair = events["fair_value"].to_numpy(dtype=float)
    price = events["trade_price"].to_numpy(dtype=float)
    size = events["trade_size"].to_numpy(dtype=float)
    instrument = events["instrument"].astype(str).to_numpy()
    rows = []
    for i in range(len(events) - 1):
        exposure = seconds[i + 1] - seconds[i]
        if exposure <= 0.0:
            continue
        traded = size[i + 1] > 0.0
        for distance in quote_distances:
            hit = traded and (
                price[i + 1] <= fair[i] - distance or price[i + 1] >= fair[i] + distance
            )
            rows.append({
                "timestamp": float(seconds[i]),
                "instrument": instrument[i],
                "quote_distance": float(distance),
                "arrival_count": int(hit),
                "exposure_seconds": float(exposure),
            })
    return pd.DataFrame(rows)


def generate_sample_ticks(seed: int = 0, n_timestamps: int = 4) -> pd.DataFrame:
    """Small option-chain snapshot in the ``load_option_ticks_csv`` contract."""
    rng = np.random.default_rng(seed)
    start = pd.Timestamp("2026-01-05T14:30:00")
    expiry = "2026-02-20T16:00:00"
    strikes = (90.0, 95.0, 100.0, 105.0, 110.0)
    spot = 100.0
    rows = []
    for step in range(n_timestamps):
        timestamp = start + pd.Timedelta(minutes=30 * step)
        spot *= math.exp(0.003 * rng.standard_normal())
        tau = (pd.Timestamp(expiry) - timestamp).total_seconds() / SECONDS_PER_YEAR
        for strike in strikes:
            iv = 0.22 + 0.4 * (math.log(strike / spot)) ** 2 + 0.002 * rng.standard_normal()
            price, _ = _bs_call(np.array(spot), strike, 0.01, iv, np.array(tau))
            price = float(price)
            half = max(0.025, 0.02 * price)
            rows.append({
                "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "expiry": expiry,
                "underlying": round(spot, 4),
                "strike": strike,
                "option_type": "call",
                "bid": round(max(0.0, price - half), 2),
                "ask": round(price + half, 2),
                "iv": round(iv, 4),
            })
    return pd.DataFrame(rows)


def synthetic_walk_forward_inputs(config: SyntheticConfig):
    """Return (validated event frame, MarketEvent list, arrival panel)."""
    import io

    from options_mm.data.research import load_research_events_csv, to_market_events

    raw = generate_research_events(config)
    buffer = io.StringIO(raw.to_csv(index=False))
    frame = load_research_events_csv(buffer)
    return frame, to_market_events(frame), build_synthetic_arrival_panel(raw)
