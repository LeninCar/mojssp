"""Convert configured fixed budget shares to exact evaluation quotas."""

from fractions import Fraction
import math


def evaluation_quotas(total_budget, shares):
    """Use largest remainders to allocate every evaluation exactly once."""
    if isinstance(total_budget, bool) or not isinstance(total_budget, int) or total_budget <= 0:
        raise ValueError("Total budget must be a positive integer")
    if not shares or any(not math.isfinite(value) or value <= 0 for value in shares.values()):
        raise ValueError("Shares must be finite and positive")
    if not math.isclose(sum(shares.values()), 1, rel_tol=0, abs_tol=1e-12):
        raise ValueError("Shares must sum to one")
    fractions = {name: Fraction(str(value)) for name, value in shares.items()}
    total = sum(fractions.values())
    exact = {name: total_budget * value / total for name, value in fractions.items()}
    quotas = {name: value.numerator // value.denominator for name, value in exact.items()}
    order = sorted(shares, key=lambda name: exact[name] - quotas[name], reverse=True)
    for name in order[: total_budget - sum(quotas.values())]:
        quotas[name] += 1
    return quotas
