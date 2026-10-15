"""Pareto dominance relations for multi-objective optimization."""

from typing import Sequence, Union

from .evaluator import ObjectiveValues


def dominates(
    a: Union[ObjectiveValues, Sequence[float]],
    b: Union[ObjectiveValues, Sequence[float]],
) -> bool:
    """Check if objective vector a Pareto-dominates objective vector b in minimization.

    Vector a dominates b iff:
        1. a_i <= b_i for all objectives i, and
        2. a_j < b_j for at least one objective j.

    Args:
        a: First objective vector (ObjectiveValues or sequence of floats).
        b: Second objective vector (ObjectiveValues or sequence of floats).

    Returns:
        True if a dominates b, False otherwise.
    """
    a_vals = (a.makespan, a.tardiness, a.energy) if isinstance(a, ObjectiveValues) else tuple(a)
    b_vals = (b.makespan, b.tardiness, b.energy) if isinstance(b, ObjectiveValues) else tuple(b)
    return all(x <= y for x, y in zip(a_vals, b_vals)) and any(x < y for x, y in zip(a_vals, b_vals))


