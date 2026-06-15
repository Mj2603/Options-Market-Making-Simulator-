"""Demo runner: compute theoretical prices for sample ticks."""
from options_mm.data.loader import load_option_ticks_csv
from options_mm.pricing.black_scholes import call_price_greeks, put_price_greeks


def main() -> None:
    path = "data/sample_ticks.csv"
    df = load_option_ticks_csv(path)
    r = 0.01
    for _, row in df.iterrows():
        S = float(row["underlying"])
        K = float(row["strike"])
        T = float(row["time_to_expiry"])
        sigma = float(row.get("iv", 0.2) or 0.2)
        call = call_price_greeks(S, K, r, sigma, T)
        put = put_price_greeks(S, K, r, sigma, T)
        print(f"{row['timestamp']} S={S} K={K} T={T:.4f} sigma={sigma:.3f}")
        print(f"  call price={call.price:.3f} delta={call.delta:.3f} vega={call.vega:.3f}")
        print(f"  put  price={put.price:.3f} delta={put.delta:.3f} vega={put.vega:.3f}")


if __name__ == "__main__":
    main()
