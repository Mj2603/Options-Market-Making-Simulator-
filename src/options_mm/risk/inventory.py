from dataclasses import dataclass, field
from typing import Dict


@dataclass
class InventoryManager:
    """Simple inventory manager that enforces a per-instrument position limit."""

    max_position: float = 1000.0
    positions: Dict[str, float] = field(default_factory=dict)

    def on_fill(self, ticker: str, size: float) -> None:
        """Apply a fill to the inventory for the given ticker."""
        self.positions[ticker] = self.positions.get(ticker, 0.0) + float(size)

    def position(self, ticker: str) -> float:
        return float(self.positions.get(ticker, 0.0))

    def within_limit(self, ticker: str) -> bool:
        return abs(self.position(ticker)) <= float(self.max_position)

    def would_exceed(self, ticker: str, additional: float) -> bool:
        return abs(self.position(ticker) + additional) > float(self.max_position)
