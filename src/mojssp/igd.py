"""Inverted Generational Distance (IGD) metric and reference front builder.

Phase 8.2 implementation for multi-objective performance assessment in MO-JSSP.
IGD measures both convergence towards a reference Pareto front and diversity/coverage
of the non-dominated objective space.
"""

import math
from typing import Iterable, List, Optional, Sequence, Tuple, Union

from .dominance import dominates
from .normalization import ObjectiveNormalizer
from .pareto_archive import ArchiveEntry, ParetoArchive


def compute_euclidean_distance(
    p1: Sequence[float], p2: Sequence[float]
) -> float:
    """Compute standard Euclidean distance between two points in M-dimensional space.

    Args:
        p1: First point coordinates.
        p2: Second point coordinates.

    Returns:
        Euclidean distance sqrt(sum((p1_i - p2_i)^2)).

    Raises:
        ValueError: If points have different dimensionalities.
    """
    if len(p1) != len(p2):
        raise ValueError(
            f"Point dimensions must match: got {len(p1)} and {len(p2)}"
        )
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(p1, p2)))


def compute_igd(
    obtained_points: Sequence[Sequence[float]],
    reference_points: Sequence[Sequence[float]],
) -> float:
    """Compute Inverted Generational Distance (IGD) from obtained points to reference front.

    IGD formula:
        IGD(A, P*) = (1 / |P*|) * sum_{v in P*} min_{u in A} d(v, u)

    Where:
        - P* is the set of reference points.
        - A is the set of obtained non-dominated points.
        - d(v, u) is the Euclidean distance in (usually normalized) objective space.

    Properties:
        - IGD = 0.0 indicates that obtained_points covers every point in reference_points.
        - Lower values indicate better combined convergence and diversity.
        - If obtained_points is empty, returns float("inf").

    Args:
        obtained_points: Collection of non-dominated objective points discovered by an algorithm.
        reference_points: Non-empty collection of reference Pareto front points.

    Returns:
        Scalar IGD value >= 0.0.

    Raises:
        ValueError: If reference_points is empty.
    """
    if not reference_points:
        raise ValueError("reference_points must be a non-empty sequence")

    if not obtained_points:
        return float("inf")

    total_min_distance = 0.0
    for ref_pt in reference_points:
        min_dist = min(compute_euclidean_distance(ref_pt, obt_pt) for obt_pt in obtained_points)
        total_min_distance += min_dist

    return float(total_min_distance / len(reference_points))


def compute_archive_igd(
    archive: ParetoArchive,
    reference_points: Sequence[Tuple[float, float, float]],
    normalizer: ObjectiveNormalizer,
) -> float:
    """Compute normalized IGD of a ParetoArchive against a normalized reference front.

    Args:
        archive: ParetoArchive containing non-dominated solutions.
        reference_points: Reference front points in normalized [0, 1]^3 space.
        normalizer: ObjectiveNormalizer configured with instance bounds.

    Returns:
        Scalar IGD in normalized space [0, 1]^3.
    """
    if len(archive) == 0:
        return float("inf")

    normalized_obtained = normalizer.normalize_archive(archive)
    return compute_igd(normalized_obtained, reference_points)


def filter_non_dominated_points(
    points: Iterable[Tuple[float, float, float]]
) -> List[Tuple[float, float, float]]:
    """Filter an arbitrary collection of 3D objective points to retain only non-dominated points.

    Assumes minimization across all three objectives (cmax, tardiness, energy).
    Removes exact duplicates and dominated points.

    Args:
        points: Iterable of (cmax, tardiness, energy) tuples.

    Returns:
        Sorted, non-dominated list of unique 3D points.
    """
    unique_points = sorted(set(tuple(p) for p in points))
    if not unique_points:
        return []

    non_dominated: List[Tuple[float, float, float]] = []
    for p in unique_points:
        is_dominated = False
        for other in unique_points:
            if other == p:
                continue
            # check dominance for minimization: other dominates p if other <= p for all and other < p for at least one
            if (
                other[0] <= p[0]
                and other[1] <= p[1]
                and other[2] <= p[2]
                and (other[0] < p[0] or other[1] < p[1] or other[2] < p[2])
            ):
                is_dominated = True
                break
        if not is_dominated:
            non_dominated.append(p)

    return non_dominated


def build_empirical_reference_front(
    archives: Iterable[Union[ParetoArchive, Iterable[ArchiveEntry]]],
    normalizer: Optional[ObjectiveNormalizer] = None,
) -> List[Tuple[float, float, float]]:
    """Construct an empirical Pareto reference front by pooling and filtering multiple archives.

    Extracts all objective vectors across all provided archives, removes duplicates,
    and discards any vector dominated by another pooled vector.

    Args:
        archives: Collection of ParetoArchive instances or collections of ArchiveEntry.
        normalizer: Optional ObjectiveNormalizer. If provided, returns points normalized
            in [0, 1]^3; otherwise returns points in original objective scale.

    Returns:
        List of non-dominated 3-tuples representing the empirical reference front.
    """
    raw_points: List[Tuple[float, float, float]] = []

    for arch in archives:
        entries = arch.entries if isinstance(arch, ParetoArchive) else arch
        for entry in entries:
            objs = entry.objectives
            raw_points.append(
                (float(objs.makespan), float(objs.tardiness), float(objs.energy))
            )

    filtered_raw = filter_non_dominated_points(raw_points)

    if normalizer is not None:
        return [normalizer.normalize_tuple(p) for p in filtered_raw]
    return filtered_raw
