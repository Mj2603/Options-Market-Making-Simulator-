from dataclasses import dataclass
from typing import Iterable, Tuple


def compute_net_delta(option_positions: Iterable[Tuple[float, float]]) -> float:
    """Compute the net option delta.

    option_positions: iterable of (delta, size) tuples where `delta` is the
    per-contract delta and `size` is the number of contracts (positive for
    long, negative for short).
    Returns the net delta expressed in underlying shares.
    """
    net = 0.0
    for delta, size in option_positions:
        net += float(delta) * float(size)
    return net


def hedge_quantity_for_underlying(option_positions: Iterable[Tuple[float, float]]) -> float:
    """Return quantity of underlying to trade to neutralize option delta.

    Positive return indicates a buy of underlying, negative indicates a sell.
    """
    net = compute_net_delta(option_positions)
    return -net
