"""Exact 3D Hypervolume computation for MO-JSSP Pareto fronts."""

from typing import List, Sequence, Tuple, Union

from .dominance import dominates
from .normalization import ObjectiveNormalizer
from .pareto_archive import ParetoArchive

# Canonical fixed reference point in normalized space [0, 1]^3
DEFAULT_REFERENCE_POINT: Tuple[float, float, float] = (1.1, 1.1, 1.1)


def _compute_2d_hypervolume(
    points_2d: Sequence[Tuple[float, float]], reference_2d: Tuple[float, float]
) -> float:
    """Compute the exact 2D hypervolume (dominated area) for minimization.

    Each 2D point (y1, y2) with y1 <= R1 and y2 <= R2 dominates the box
    [y1, R1] x [y2, R2]. The union area is computed using an exact sweeping line.

    Args:
        points_2d: Sequence of 2D points (y1, y2).
        reference_2d: The 2D reference point (R1, R2).

    Returns:
        Exact dominated area as a float.
    """
    r1, r2 = reference_2d

    # Discard points outside the 2D bounding region
    valid_points = [
        (p[0], p[1])
        for p in points_2d
        if p[0] < r1 and p[1] < r2
    ]
    if not valid_points:
        return 0.0

    # Sort primarily by y1 ascending, secondarily by y2 ascending
    sorted_points = sorted(valid_points, key=lambda p: (p[0], p[1]))

    # Filter to 2D non-dominated points: y2 must strictly decrease as y1 increases
    nd_2d: List[Tuple[float, float]] = []
    min_y2 = float("inf")
    for y1, y2 in sorted_points:
        if y2 < min_y2:
            nd_2d.append((y1, y2))
            min_y2 = y2

    if not nd_2d:
        return 0.0

    # Compute union area of staircase rectangles
    area = 0.0
    for j in range(len(nd_2d) - 1):
        width = nd_2d[j + 1][0] - nd_2d[j][0]
        height = r2 - nd_2d[j][1]
        area += width * height

    # Final rectangle to reference boundary
    last_u, last_v = nd_2d[-1]
    area += (r1 - last_u) * (r2 - last_v)

    return float(area)


def compute_hypervolume(
    points: Sequence[Union[Tuple[float, float, float], Sequence[float]]],
    reference_point: Tuple[float, float, float] = DEFAULT_REFERENCE_POINT,
) -> float:
    """Compute the exact 3D Hypervolume for a set of objective points in minimization.

    Algorithm: Dimension Sweeping / 2D Slicing.
    1. Filter out points outside the useful region: any(point[i] > reference_point[i]).
    2. Deduplicate points.
    3. Filter out internally dominated points using the common dominates() function.
    4. Slice along the first objective coordinate and integrate the exact 2D dominated area.

    Args:
        points: Collection of 3D objective vectors (normalized or original).
        reference_point: Fixed reference point in the same objective space (default: (1.1, 1.1, 1.1)).

    Returns:
        The exact hypervolume enclosed by the non-dominated points and the reference point.
    """
    if len(reference_point) != 3:
        raise ValueError(
            f"Reference point must have 3 dimensions, got {len(reference_point)}"
        )

    r0, r1, r2 = (
        float(reference_point[0]),
        float(reference_point[1]),
        float(reference_point[2]),
    )
    ref = (r0, r1, r2)

    # 1. Filter points in the useful region: discard any point where point[i] > ref[i]
    useful_points: List[Tuple[float, float, float]] = []
    for p in points:
        if len(p) != 3:
            raise ValueError(f"Each objective point must have 3 coordinates, got {len(p)}")
        pt = (float(p[0]), float(p[1]), float(p[2]))
        if not any(pt[i] > ref[i] for i in range(3)):
            useful_points.append(pt)

    if not useful_points:
        return 0.0

    # 2. Deduplicate points
    unique_points = list(set(useful_points))

    # 3. Discard points that are dominated by other points in the set
    non_dominated: List[Tuple[float, float, float]] = []
    for p in unique_points:
        if not any(dominates(q, p) for q in unique_points if q != p):
            non_dominated.append(p)

    if not non_dominated:
        return 0.0

    # Fast path for single point
    if len(non_dominated) == 1:
        p = non_dominated[0]
        return float(max(0.0, r0 - p[0]) * max(0.0, r1 - p[1]) * max(0.0, r2 - p[2]))

    # 4. Dimension Sweeping (2D Slicing) along coordinate 0
    x_coords = sorted(
        set(p[0] for p in non_dominated if p[0] < r0).union({r0})
    )

    total_volume = 0.0
    ref_2d = (r1, r2)

    for i in range(len(x_coords) - 1):
        x_start = x_coords[i]
        x_end = x_coords[i + 1]
        dx = x_end - x_start
        if dx <= 0.0:
            continue

        # Points active throughout [x_start, x_end] are those with p[0] <= x_start
        active_2d = [
            (p[1], p[2])
            for p in non_dominated
            if p[0] <= x_start
        ]

        if not active_2d:
            continue

        area_2d = _compute_2d_hypervolume(active_2d, ref_2d)
        total_volume += area_2d * dx

    return float(total_volume)


def compute_archive_hypervolume(
    archive: ParetoArchive,
    normalizer: ObjectiveNormalizer,
    reference_point: Tuple[float, float, float] = DEFAULT_REFERENCE_POINT,
) -> float:
    """Compute the exact hypervolume of a ParetoArchive in normalized objective space.

    Extracts and normalizes the objective values of all archive entries, then
    evaluates their 3D hypervolume against reference_point without modifying the archive.

    Args:
        archive: The ParetoArchive containing non-dominated solutions.
        normalizer: ObjectiveNormalizer configured with instance bounds.
        reference_point: The reference point in normalized space (default: (1.1, 1.1, 1.1)).

    Returns:
        The exact normalized hypervolume of the archive.
    """
    normalized_points = normalizer.normalize_archive(archive)
    return compute_hypervolume(normalized_points, reference_point=reference_point)

