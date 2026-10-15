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

    Extracts all objective vectors across all provided archives, removes duplicates within
    numerical tolerance, and discards any vector dominated by another pooled vector.

    Note:
        This front represents an empirical reference front (the best known approximation
        pool), and should not be characterized as the true global Pareto front.

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


def compute_modified_distance(
    u: Sequence[float], v: Sequence[float]
) -> float:
    """Compute the modified distance d+(u, v) for minimization problems (Ishibuchi et al., 2015).

    d+(u, v) measures the distance from obtained point u to reference point v, penalizing
    only components where u is worse (greater) than v:
        d+(u, v) = sqrt(sum_{i=1}^M (max(0, u_i - v_i))^2)

    If u weakly dominates v (u_i <= v_i for all i), d+(u, v) = 0.0.

    Args:
        u: Obtained point coordinates.
        v: Reference point coordinates.

    Returns:
        Non-negative scalar modified distance d+(u, v).

    Raises:
        ValueError: If u and v have different dimensionalities.
    """
    if len(u) != len(v):
        raise ValueError(
            f"Point dimensions must match: got {len(u)} and {len(v)}"
        )
    return math.sqrt(sum((max(0.0, float(a) - float(b))) ** 2 for a, b in zip(u, v)))


def compute_igd_plus(
    obtained_points: Sequence[Sequence[float]],
    reference_points: Sequence[Sequence[float]],
) -> float:
    """Compute Inverted Generational Distance Plus (IGD+) (Ishibuchi et al., 2015).

    IGD+ is weakly Pareto compliant, satisfying the property that if set A dominates
    set B, then IGD+(A, P*) <= IGD+(B, P*).

    Formula:
        IGD+(A, P*) = (1 / |P*|) * sum_{v in P*} min_{u in A} d+(u, v)

    Args:
        obtained_points: Collection of non-dominated objective points discovered by an algorithm.
        reference_points: Non-empty collection of reference Pareto front points.

    Returns:
        Scalar IGD+ value >= 0.0.

    Raises:
        ValueError: If reference_points is empty.
    """
    if not reference_points:
        raise ValueError("reference_points must be a non-empty sequence")

    if not obtained_points:
        return float("inf")

    total_min_distance = 0.0
    for ref_pt in reference_points:
        min_dist = min(compute_modified_distance(obt_pt, ref_pt) for obt_pt in obtained_points)
        total_min_distance += min_dist

    return float(total_min_distance / len(reference_points))


def compute_archive_igd_plus(
    archive: ParetoArchive,
    reference_points: Sequence[Tuple[float, float, float]],
    normalizer: ObjectiveNormalizer,
) -> float:
    """Compute normalized IGD+ of a ParetoArchive against a normalized reference front.

    Args:
        archive: ParetoArchive containing non-dominated solutions.
        reference_points: Reference front points in normalized [0, 1]^3 space.
        normalizer: ObjectiveNormalizer configured with instance bounds.

    Returns:
        Scalar IGD+ in normalized space [0, 1]^3.
    """
    if len(archive) == 0:
        return float("inf")

    normalized_obtained = normalizer.normalize_archive(archive)
    return compute_igd_plus(normalized_obtained, reference_points)


def compute_contribution_rate(
    obtained_points: Sequence[Sequence[float]],
    reference_points: Sequence[Sequence[float]],
    tolerance: float = 1e-6,
) -> float:
    """Compute the Contribution Rate (CR) of an obtained front to the reference front.

    CR measures the percentage of reference front points that are matched (within numerical
    tolerance across all objectives) by at least one solution in the obtained front:
        CR(A, P*) = (|{ v in P* : exists u in A with ||u - v||_inf <= tolerance }| / |P*|) * 100%

    Args:
        obtained_points: Collection of non-dominated objective points.
        reference_points: Non-empty collection of reference Pareto front points.
        tolerance: Numerical tolerance for floating-point equality (default: 1e-6).

    Returns:
        Percentage in [0.0, 100.0] representing the contribution rate.

    Raises:
        ValueError: If reference_points is empty or tolerance < 0.
    """
    if not reference_points:
        raise ValueError("reference_points must be a non-empty sequence")

    if tolerance < 0.0:
        raise ValueError(f"tolerance must be non-negative, got {tolerance}")

    if not obtained_points:
        return 0.0

    matched = 0
    for ref_pt in reference_points:
        is_matched = any(
            all(abs(float(u_i) - float(v_i)) <= tolerance for u_i, v_i in zip(obt_pt, ref_pt))
            for obt_pt in obtained_points
        )
        if is_matched:
            matched += 1

    return float((matched / len(reference_points)) * 100.0)


def compute_archive_contribution_rate(
    archive: ParetoArchive,
    reference_points: Sequence[Tuple[float, float, float]],
    normalizer: ObjectiveNormalizer,
    tolerance: float = 1e-6,
) -> float:
    """Compute the normalized Contribution Rate (CR) of a ParetoArchive.

    Args:
        archive: ParetoArchive containing non-dominated solutions.
        reference_points: Reference front points in normalized [0, 1]^3 space.
        normalizer: ObjectiveNormalizer configured with instance bounds.
        tolerance: Numerical tolerance for floating-point equality in normalized space.

    Returns:
        Percentage in [0.0, 100.0] representing the contribution rate.
    """
    if len(archive) == 0:
        return 0.0

    normalized_obtained = normalizer.normalize_archive(archive)
    return compute_contribution_rate(normalized_obtained, reference_points, tolerance=tolerance)

