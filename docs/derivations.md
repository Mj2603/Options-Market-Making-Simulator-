# Mathematical Derivations

## Black-Scholes Formula

For a European call option with underlying price $S$, strike $K$, risk-free rate $r$, volatility $\sigma$, and time to expiration $T$:

$$
C = S\Phi(d_1) - K e^{-rT}\Phi(d_2)
$$

Where:

$$
d_1 = \frac{\ln(S/K) + (r + \frac{1}{2}\sigma^2)T}{\sigma\sqrt{T}}\\
 d_2 = d_1 - \sigma\sqrt{T}
$$

The put price is given by put-call parity:

$$
P = C - S + K e^{-rT}
$$

## Greeks

- Delta (call): $\Delta = \Phi(d_1)$
- Gamma: $\Gamma = \frac{\phi(d_1)}{S\sigma\sqrt{T}}$
- Vega: $V = S\phi(d_1)\sqrt{T}$
- Theta (call):

$$
\Theta = -\frac{S\phi(d_1)\sigma}{2\sqrt{T}} - r K e^{-rT} \Phi(d_2)
$$

Where $\Phi$ is the standard normal CDF and $\phi$ is the standard normal PDF.

## Inventory and Risk

The simulator tracks inventory to enforce a maximal notional exposure per ticker. A hedger can neutralize option delta by selling $\Delta$ shares of the underlying.

## Execution Model

- Market buy fills at ask.
- Market sell fills at bid.
- Limit buy fills only if the limit price is at or above ask.
- Limit sell fills only if the limit price is at or below bid.
