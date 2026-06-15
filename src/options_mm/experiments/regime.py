from typing import Iterable
import numpy as np


class RegimeDetector:
    """Very small volatility regime detector for experiments (Phase 8).

    Uses sample standard deviation of returns and compares to a threshold to
    label the regime as 'low' or 'high' volatility.
    """

    def __init__(self, threshold: float = 0.02):
        self.threshold = float(threshold)

    def detect(self, returns: Iterable[float]) -> str:
        arr = np.asarray(list(returns), dtype=float)
        if arr.size == 0:
            return "low"
        vol = float(np.std(arr, ddof=0))
        return "high" if vol >= self.threshold else "low"
