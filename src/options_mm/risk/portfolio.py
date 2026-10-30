"""Portfolio-level option Greeks, concentration, and pre-trade controls."""
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


@dataclass(frozen=True)
class RiskDecision:
    approved: bool
    reason: str
    projected: PortfolioExposure


class PortfolioRiskManager:
    """Reject trades that breach portfolio Greeks or gross concentration.

    Greeks are per option unit; quantity and contract multiplier are applied
    once. Delta is in underlying-share equivalents; gamma is currency P&L per
    squared one-unit spot move; vega is currency P&L per 1.00 absolute volatility
    change; theta is currency P&L per calendar day. Supply Greeks in these
    units consistently across all contracts.
    """

    def __init__(
        self,
        max_abs_delta: float = math.inf,
        max_abs_gamma: float = math.inf,
        max_abs_vega: float = math.inf,
        max_gross_market_value: float = math.inf,
        max_underlying_gross_value: float = math.inf,
    ):
        limits = {
            "max_abs_delta": max_abs_delta,
            "max_abs_gamma": max_abs_gamma,
            "max_abs_vega": max_abs_vega,
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
        for position in positions:
            cls._validate_position(position)
            scale = position.quantity * position.multiplier
            delta += scale * position.delta
            gamma += scale * position.gamma
            vega += scale * position.vega
            theta += scale * position.theta
            signed_value = scale * position.market_value
            gross += abs(signed_value)
            net += signed_value
            by_underlying[position.underlying] = (
                by_underlying.get(position.underlying, 0.0) + abs(signed_value)
            )
        return PortfolioExposure(
            delta=delta, gamma=gamma, vega=vega, theta=theta,
            gross_market_value=gross, net_market_value=net,
            by_underlying=by_underlying,
        )

    def delta_hedge_quantity(
        self, positions: Iterable[OptionRiskPosition]
    ) -> float:
        """Return underlying units required to neutralize aggregate option delta."""
        return -self.aggregate(positions).delta

    @staticmethod
    def scenario_pnl(
        exposure: PortfolioExposure,
        spot_change: float,
        volatility_change: float,
        days_elapsed: float = 0.0,
    ) -> float:
        """Second-order delta/gamma plus vega/theta scenario approximation."""
        shocks = (spot_change, volatility_change, days_elapsed)
        if not all(math.isfinite(float(value)) for value in shocks):
            raise ValueError("scenario shocks must be finite")
        if days_elapsed < 0.0:
            raise ValueError("days_elapsed must be non-negative")
        delta_pnl = exposure.delta * spot_change
        gamma_pnl = 0.5 * exposure.gamma * spot_change**2
        vega_pnl = exposure.vega * volatility_change
        theta_pnl = exposure.theta * days_elapsed
        return delta_pnl + gamma_pnl + vega_pnl + theta_pnl

    def pre_trade_check(
        self,
        positions: Iterable[OptionRiskPosition],
        proposed: OptionRiskPosition,
    ) -> RiskDecision:
        current = list(positions)
        self._validate_position(proposed)
        projected = self.aggregate(current + [proposed])
        checks = [
            (abs(projected.delta) <= self.max_abs_delta, "portfolio delta limit"),
            (abs(projected.gamma) <= self.max_abs_gamma, "portfolio gamma limit"),
            (abs(projected.vega) <= self.max_abs_vega, "portfolio vega limit"),
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
