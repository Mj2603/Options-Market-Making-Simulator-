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
    once. Delta is reported in underlying-share equivalents. Gamma is the
    second derivative exposure per 1% squared spot move, vega per 1 volatility
    point, and theta per calendar day when the caller supplies those units.
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
