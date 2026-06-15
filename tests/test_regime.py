from options_mm.experiments.regime import RegimeDetector
import numpy as np


def test_regime_low_and_high():
    det = RegimeDetector(threshold=0.01)
    low_returns = np.random.normal(0.0, 0.005, size=100)
    high_returns = np.random.normal(0.0, 0.02, size=100)
    assert det.detect(low_returns) == "low"
    assert det.detect(high_returns) == "high"
