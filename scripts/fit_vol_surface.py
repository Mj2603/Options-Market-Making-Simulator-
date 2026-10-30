"""Fit raw-SVI slices from a vendor-provided implied-volatility CSV."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path

import pandas as pd

from options_mm.pricing.vol_surface import SVIVolatilitySurface


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("reports/svi_surface.json"))
    parser.add_argument("--min-points", type=int, default=5)
    args = parser.parse_args()
    frame = pd.read_csv(args.input)
    required = {"expiry_years", "forward", "strike", "implied_volatility"}
    missing = required.difference(frame.columns)
    if missing:
        parser.error(f"input missing columns: {sorted(missing)}")
    surface = SVIVolatilitySurface.fit(
        frame["expiry_years"], frame["forward"], frame["strike"],
        frame["implied_volatility"], min_points=args.min_points,
    )
    payload = {
        "diagnostics": surface.diagnostics(),
        "slices": [asdict(item) for item in surface.slices],
        "arbitrage_free_guarantee": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {len(surface.slices)} SVI slices to {args.output}")
    print("Raw-SVI fit is not guaranteed to be calendar- or butterfly-arbitrage-free.")


if __name__ == "__main__":
    main()
