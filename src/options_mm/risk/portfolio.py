"""Portfolio-level option Greeks, concentration, stress, and pre-trade controls."""
from dataclasses import dataclass
import math
from typing import Iterable


@dataclass(frozen=True)
class OptionRiskPosition:
    instrument: str
    underlying: str
    quantity: float
    multiplier: float
    delta: float
    gamma: float
    vega: float
    theta: float
    market_value: float = 0.0


@dataclass(frozen=True)
class PortfolioExposure:
    delta: float
    gamma: float
    vega: float
    theta: float
    gross_market_value: float
    net_market_value: float
    by_underlying: dict[str, float]
    delta_by_underlying: dict[str, float]
    greeks_by_underlying: dict[str, dict[str, float]]


@dataclass(frozen=True)
class RiskDecision:
    approved: bool
    reason: str
    projected: PortfolioExposure


class PortfolioRiskManager:
    """Reject trades that breach per-underlying Greeks or concentration limits.

    Greeks are per option unit; quantity and contract multiplier are applied
    once. Delta is in underlying-share equivalents; gamma is currency P&L per
    squared one-unit spot move; vega is currency P&L per 1.00 absolute volatility
    change; theta is currency P&L per calendar day. Supply Greeks in these
    units consistently across all contracts. Standard Black-Scholes theta is
    per year and must be divided by 365.25 before it is supplied here.
    """

    def __init__(
        self,
        max_abs_delta: float = math.inf,
        max_abs_gamma: float = math.inf,
        max_abs_vega: float = math.inf,
        max_abs_theta: float = math.inf,
        max_gross_market_value: float = math.inf,
        max_underlying_gross_value: float = math.inf,
    ):
        limits = {
            "max_abs_delta": max_abs_delta,
            "max_abs_gamma": max_abs_gamma,
            "max_abs_vega": max_abs_vega,
            "max_abs_theta": max_abs_theta,
            "max_gross_market_value": max_gross_market_value,
            "max_underlying_gross_value": max_underlying_gross_value,
        }
        for name, value in limits.items():
            number = float(value)
            if math.isnan(number) or number <= 0.0:
                raise ValueError(f"{name} must be positive")
            setattr(self, name, number)

    @staticmethod
    def _validate_position(position: OptionRiskPosition):
        if not position.instrument or not position.underlying:
            raise ValueError("instrument and underlying are required")
        values = (
            position.quantity, position.multiplier, position.delta,
            position.gamma, position.vega, position.theta, position.market_value,
        )
        if not all(math.isfinite(float(value)) for value in values):
            raise ValueError("risk position values must be finite")
        if position.multiplier <= 0.0 or position.market_value < 0.0:
            raise ValueError("multiplier must be positive and market value non-negative")

    @classmethod
    def aggregate(cls, positions: Iterable[OptionRiskPosition]) -> PortfolioExposure:
        delta = gamma = vega = theta = gross = net = 0.0
        by_underlying: dict[str, float] = {}
        greeks_by_underlying: dict[str, dict[str, float]] = {}
        for position in positions:
            cls._validate_position(position)
            scale = position.quantity * position.multiplier
            position_delta = scale * position.delta
            position_gamma = scale * position.gamma
            position_vega = scale * position.vega
            position_theta = scale * position.theta
            delta += position_delta
            gamma += position_gamma
            vega += position_vega
            theta += position_theta
            signed_value = scale * position.market_value
            gross += abs(signed_value)
            net += signed_value
            by_underlying[position.underlying] = (
                by_underlying.get(position.underlying, 0.0) + abs(signed_value)
            )
            greek_state = greeks_by_underlying.setdefault(
                position.underlying,
                {"delta": 0.0, "gamma": 0.0, "vega": 0.0, "theta": 0.0},
            )
            greek_state["delta"] += position_delta
            greek_state["gamma"] += position_gamma
            greek_state["vega"] += position_vega
            greek_state["theta"] += position_theta
        return PortfolioExposure(
            delta=delta, gamma=gamma, vega=vega, theta=theta,
            gross_market_value=gross, net_market_value=net,
            by_underlying=by_underlying,
            delta_by_underlying={
                underlying: values["delta"]
                for underlying, values in greeks_by_underlying.items()
            },
            greeks_by_underlying=greeks_by_underlying,
        )

    def delta_hedge_quantities(
        self, positions: Iterable[OptionRiskPosition]
    ) -> dict[str, float]:
        """Return a separate theoretical hedge quantity for each underlying."""
        exposure = self.aggregate(positions)
        return {
            underlying: -delta
            for underlying, delta in exposure.delta_by_underlying.items()
        }

    def delta_hedge_quantity(
        self,
        positions: Iterable[OptionRiskPosition],
        underlying: str | None = None,
    ) -> float:
        """Return one underlying hedge; require a symbol for multi-underlying books."""
        hedges = self.delta_hedge_quantities(positions)
        if underlying is not None:
            return hedges.get(underlying, 0.0)
        if len(hedges) > 1:
            raise ValueError("specify underlying for a multi-underlying portfolio")
        return next(iter(hedges.values()), 0.0)

    @staticmethod
    def scenario_pnl(
        exposure: PortfolioExposure,
        spot_change: float | dict[str, float],
        volatility_change: float | dict[str, float],
        days_elapsed: float = 0.0,
    ) -> float:
        """Second-order Greek P&L, with separate shocks per underlying.

        A scalar shock is accepted only for a single-underlying portfolio.
        """
        days_elapsed = float(days_elapsed)
        if not math.isfinite(days_elapsed) or days_elapsed < 0.0:
            raise ValueError("days_elapsed must be finite and non-negative")
        underlyings = exposure.greeks_by_underlying
        if not underlyings:
            return 0.0
        if not isinstance(spot_change, dict):
            if len(underlyings) > 1:
                raise ValueError("provide spot_change by underlying for multi-underlying risk")
            spot_change = {next(iter(underlyings)): float(spot_change)}
        if not isinstance(volatility_change, dict):
            if len(underlyings) > 1:
                raise ValueError("provide volatility_change by underlying for multi-underlying risk")
            volatility_change = {next(iter(underlyings)): float(volatility_change)}

        pnl = 0.0
        for underlying, greeks in underlyings.items():
            d_spot = float(spot_change.get(underlying, 0.0))
            d_vol = float(volatility_change.get(underlying, 0.0))
            if not math.isfinite(d_spot) or not math.isfinite(d_vol):
                raise ValueError("scenario shocks must be finite")
            pnl += (
                greeks["delta"] * d_spot
                + 0.5 * greeks["gamma"] * d_spot**2
                + greeks["vega"] * d_vol
                + greeks["theta"] * days_elapsed
            )
        return pnl

    def pre_trade_check(
        self,
        positions: Iterable[OptionRiskPosition],
        proposed: OptionRiskPosition,
    ) -> RiskDecision:
        current = list(positions)
        self._validate_position(proposed)
        projected = self.aggregate(current + [proposed])
        per_underlying_greeks = list(projected.greeks_by_underlying.values())
        checks = [
            (
                max((abs(x["delta"]) for x in per_underlying_greeks), default=0.0)
                <= self.max_abs_delta,
                "per-underlying portfolio delta limit",
            ),
            (
                max((abs(x["gamma"]) for x in per_underlying_greeks), default=0.0)
                <= self.max_abs_gamma,
                "per-underlying portfolio gamma limit",
            ),
            (
                max((abs(x["vega"]) for x in per_underlying_greeks), default=0.0)
                <= self.max_abs_vega,
                "per-underlying portfolio vega limit",
            ),
            (
                max((abs(x["theta"]) for x in per_underlying_greeks), default=0.0)
                <= self.max_abs_theta,
                "per-underlying portfolio theta limit",
            ),
            (projected.gross_market_value <= self.max_gross_market_value, "gross market value limit"),
            (
                projected.by_underlying.get(proposed.underlying, 0.0)
                <= self.max_underlying_gross_value,
                "underlying concentration limit",
            ),
        ]
        failed = [reason for passed, reason in checks if not passed]
        return RiskDecision(
            approved=not failed,
            reason="approved" if not failed else "; ".join(failed),
            projected=projected,
        )
