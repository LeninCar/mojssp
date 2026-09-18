"""Pareto dominance relations for multi-objective optimization."""

from .evaluator import ObjectiveValues


def dominates(a: ObjectiveValues, b: ObjectiveValues) -> bool:
    """Check if objective vector a Pareto-dominates objective vector b in minimization.

    Vector a dominates b iff:
        1. a_i <= b_i for all objectives i in {makespan, tardiness, energy}, and
        2. a_j < b_j for at least one objective j.

    Args:
        a: First ObjectiveValues vector.
        b: Second ObjectiveValues vector.

    Returns:
        True if a dominates b, False otherwise.
    """
    a_vals = (a.makespan, a.tardiness, a.energy)
    b_vals = (b.makespan, b.tardiness, b.energy)
    return all(x <= y for x, y in zip(a_vals, b_vals)) and any(x < y for x, y in zip(a_vals, b_vals))

