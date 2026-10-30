import numpy as np
import pandas as pd
import pytest

from options_mm.calibration import calibrate_exponential_arrivals


def test_poisson_arrival_calibration_recovers_positive_parameters():
    rng = np.random.default_rng(7)
    distance = np.tile(np.linspace(0.01, 0.20, 30), 10)
    exposure = np.full_like(distance, 60.0)
    expected = 4.0 * np.exp(-18.0 * distance) * exposure
    count = rng.poisson(expected)
    frame = pd.DataFrame({
        "quote_distance": distance,
        "arrival_count": count,
        "exposure_seconds": exposure,
    })
    fit = calibrate_exponential_arrivals(frame)
    assert fit.intensity_at_zero > 0.0
    assert fit.price_sensitivity > 0.0
    assert fit.observations == len(frame)
    assert fit.total_arrivals == int(count.sum())


@pytest.mark.parametrize(
    "frame",
    [
        pd.DataFrame({"quote_distance": [0.1], "arrival_count": [1]}),
        pd.DataFrame({"quote_distance": [0.1], "arrival_count": [1], "exposure_seconds": [1]}),
        pd.DataFrame({"quote_distance": [0.1, 0.1], "arrival_count": [1, 2], "exposure_seconds": [1, 1]}),
        pd.DataFrame({"quote_distance": [0.1, 0.2], "arrival_count": [0, 0], "exposure_seconds": [1, 1]}),
    ],
)
def test_calibration_rejects_unidentifiable_or_invalid_panels(frame):
    with pytest.raises(ValueError):
        calibrate_exponential_arrivals(frame)
