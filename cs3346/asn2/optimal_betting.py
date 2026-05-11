
import random
import statistics

WIN_PROB    = 1 / 6
ROUNDS      = 5
START       = 100.0

# Let V(r, w) = maximum expected assets with r rounds left and assets w.
#
# Base case:  V(0, w) = w
#
# Recursive:  V(r, w) = max_{0 <= x <= w}
#                 (1/6) * V(r-1, w + 9x)  +  (5/6) * V(r-1, w - x)
#
# CLAIM: V(r, w) = (5/3)^r * w,  achieved by x* = w (bet everything).
#
# Proof by induction:
#
#   Base (r=0): V(0, w) = w = (5/3)^0 * w.  ✓
#
#   Inductive step: assume V(r-1, w) = c * w where c = (5/3)^(r-1).
#   For bet x in [0, w], the one-step expected value is:
#
#     f(x) = (1/6)*V(r-1, w+9x) + (5/6)*V(r-1, w-x)
#           = (1/6)*c*(w+9x)    + (5/6)*c*(w-x)        
#           = c * [ w + x*(9/6 - 5/6) ]
#           = c * [ w + (2/3)*x ]
#
#   f(x) is strictly increasing in x (coefficient 2c/3 > 0), so the maximum
#   on [0, w] is attained at x* = w:
#
#     V(r, w) = c * [w + (2/3)*w] = c * (5/3) * w = (5/3)^r * w.  ✓
#
# Therefore the OPTIMAL STRATEGY is: bet your entire assets every round.
# Expected final assets = (5/3)^5 * $100 ≈ $1,286.01

def dp_value(rounds=ROUNDS, start=START):
    return (5/3)**rounds * start

def print_proof():
    W = 68
    print("=" * W)
    print("  DYNAMIC PROGRAMMING PROOF")
    print("=" * W)
    print()
    print("  V(r, w) = (5/3)^r * w    [optimal value function]")
    print("  x*(r, w) = w             [optimal bet: all assets]")
    print()
    print(f"  {'Rounds left':>12}  {'Multiplier (5/3)^r':>20}  {'E[assets] from $100':>20}")
    print("  " + "-" * (W-2))
    for r in range(ROUNDS + 1):
        mult = (5/3)**r
        ev   = mult * START
        print(f"  {r:>12}  {mult:>20.6f}  ${ev:>19.2f}")
    print()
    print(f"  Optimal E[final assets] = (5/3)^5 * $100 = ${dp_value():.2f}")
    print()
    print("  Proof sketch:")
    print("    f(x) = (1/6)*c*(w+9x) + (5/6)*c*(w-x)")
    print("         = c*[w + (2/3)*x]")
    print("    Strictly increasing in x => x* = w for all rounds.")
    print()


def simulate(strategy_fn, n, seed=42):
    rng = random.Random(seed)
    results = []
    for _ in range(n):
        assets = START
        for rnd in range(ROUNDS):
            if assets <= 0:
                break
            bet = min(max(strategy_fn(assets, rnd), 0), assets)
            if rng.randint(1, 6) == 3:
                assets += 9 * bet
            else:
                assets -= bet
        results.append(assets)
    return results

def report(label, results):
    n      = len(results)
    mean   = sum(results) / n
    med    = sorted(results)[n // 2]
    bust   = sum(1 for r in results if r <= 0) / n * 100
    mx     = max(results)
    print(f"  {label:<26}  mean={mean:>9.2f}  median={med:>9.2f}"
          f"  bust={bust:>5.1f}%  max={mx:>12.2f}")
    return mean

def kelly_fraction():
    return (9 * WIN_PROB - (1 - WIN_PROB)) / 9   # ~0.0741

STRATEGIES = [
    ("Bet ALL (optimal)",    lambda w, _: w),
    ("Bet 50%",              lambda w, _: w * 0.50),
    ("Bet 25%",              lambda w, _: w * 0.25),
    ("Bet 10%",              lambda w, _: w * 0.10),
    ("Kelly (~7.4%)",        lambda w, _: w * kelly_fraction()),
    ("Fixed $10",            lambda w, _: min(10, w)),
    ("Never bet",            lambda w, _: 0),
]

def print_simulation(n_small=500_000, n_large=5_000_000):
    W = 68
    print("=" * W)
    print(f"  SIMULATION  (n={n_small:,} runs — all strategies)")
    print("=" * W)
    print()
    print(f"  {'Strategy':<26}  {'Mean':>9}  {'Median':>9}"
          f"  {'Bust%':>6}  {'Max':>12}")
    print("  " + "-" * (W-2))

    means = {}
    for label, fn in STRATEGIES:
        n = n_large if "ALL" in label else n_small
        res = simulate(fn, n)
        means[label] = report(label, res)

    print()
    best = max(means, key=means.get)
    print(f"  Best simulated mean : {best}  (${means[best]:.2f})")
    print(f"  Theoretical optimum : ${dp_value():.2f}")
    print()
    print("  The gap between simulated and theoretical mean for 'Bet ALL'")
    print("  reflects the extreme rarity of winning streaks: only (1/6)^5")
    print(f"  = {(1/6)**5*100:.4f}% of runs win all 5 rolls, but each such run")
    print(f"  yields $100 * 10^5 = $10,000,000, dominating the expectation.")
    print()
    print("  Practical takeaway:")
    print("  - Bet ALL maximises E[assets] (provably optimal)")
    print("  - Bust rate is (5/6)^1 = 83.3% per round cumulatively high")
    print("  - Kelly (~7.4%) gives best risk-adjusted (log-wealth) growth")
    print("  - Betting 50% is a reasonable middle ground: decent E, no bust")
    print("=" * W)

if __name__ == "__main__":
    print_proof()
    print_simulation()