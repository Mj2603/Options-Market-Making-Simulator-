import pandas as pd
from options_mm.data.loader import load_option_ticks_csv


def test_load_sample():
    path = "data/sample_ticks.csv"
    df = load_option_ticks_csv(path)
    assert isinstance(df, pd.DataFrame)
    assert "mid" in df.columns
    assert df["time_to_expiry"].min() >= 0.0
