"""Transparent L1 queue, latency, and adverse-selection sensitivity models.

This module does not claim to reconstruct an exchange matching engine. Queue
position is approximated from displayed size at the same NBBO price. It should
only be used with quote-size and trade-print data whose timestamps and units
are documented.
"""
from dataclasses import dataclass
import math


@dataclass
class QueuePosition:
    price: float
    queue_ahead: float
    active_after: float
    remaining_size: float


@dataclass(frozen=True)
class QueueFill:
    filled_size: float
    remaining_queue: float
    remaining_order: float


class L1QueueModel:
    def __init__(self, latency_seconds: float = 0.0):
        latency = float(latency_seconds)
        if not math.isfinite(latency) or latency < 0.0:
            raise ValueError("latency_seconds must be finite and non-negative")
        self.latency_seconds = latency

    def place(
        self,
        timestamp: float,
        price: float,
        displayed_size_ahead: float,
        order_size: float,
    ) -> QueuePosition:
        values = [timestamp, price, displayed_size_ahead, order_size]
        if not all(math.isfinite(float(value)) for value in values):
            raise ValueError("queue order inputs must be finite")
        if price < 0.0 or displayed_size_ahead < 0.0 or order_size <= 0.0:
            raise ValueError("price/queue must be non-negative and order size positive")
        return QueuePosition(
            price=float(price),
            queue_ahead=float(displayed_size_ahead),
            active_after=float(timestamp) + self.latency_seconds,
            remaining_size=float(order_size),
        )

    @staticmethod
    def process_trade(
        order: QueuePosition,
        timestamp: float,
        trade_price: float,
        trade_size: float,
        aggressor_side: str,
        order_side: str,
    ) -> QueueFill:
        """Consume queue only when the trade reaches the resting price.

        A buy aggressor can fill an ask; a sell aggressor can fill a bid.
        The trade must execute at or through the resting price. Trades before
        active_after cannot fill the order.
        """
        values = (timestamp, trade_price, trade_size)
        if not all(math.isfinite(float(value)) for value in values):
            raise ValueError("trade inputs must be finite")
        if trade_size < 0.0:
            raise ValueError("trade_size must be non-negative")
        if order_side not in ("buy", "sell") or aggressor_side not in ("buy", "sell"):
            raise ValueError("side must be 'buy' or 'sell'")
        eligible_side = (
            (order_side == "sell" and aggressor_side == "buy" and trade_price >= order.price)
            or (order_side == "buy" and aggressor_side == "sell" and trade_price <= order.price)
        )
        if timestamp < order.active_after or not eligible_side or trade_size == 0.0:
            return QueueFill(0.0, order.queue_ahead, order.remaining_size)

        volume_after_queue = max(0.0, trade_size - order.queue_ahead)
        consumed_ahead = min(order.queue_ahead, trade_size)
        order.queue_ahead -= consumed_ahead
        fill = min(order.remaining_size, volume_after_queue)
        order.remaining_size -= fill
        return QueueFill(fill, order.queue_ahead, order.remaining_size)


def signed_markout(fill_side: str, fill_price: float, future_mid: float) -> float:
    """Return maker-side markout per unit; negative means adverse selection."""
    if fill_side not in ("buy", "sell"):
        raise ValueError("fill_side must be 'buy' or 'sell'")
    if not all(math.isfinite(float(x)) for x in (fill_price, future_mid)):
        raise ValueError("markout prices must be finite")
    sign = 1.0 if fill_side == "buy" else -1.0
    return sign * (float(future_mid) - float(fill_price))
