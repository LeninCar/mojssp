"""Unit tests for exact 3D Hypervolume computation (Phase 4.2)."""

from pathlib import Path
import sys
import unittest

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mojssp import (
    ArchiveEntry,
    DEFAULT_REFERENCE_POINT,
    ObjectiveBounds,
    ObjectiveNormalizer,
    ObjectiveValues,
    ParetoArchive,
    Schedule,
    ScheduledOperation,
    Solution,
    compute_archive_hypervolume,
    compute_hypervolume,
    load_dzn,
)


class TestHypervolume(unittest.TestCase):
    """Test suite for exact 3D Hypervolume computation."""

    def test_empty_points(self) -> None:
        """Hypervolume of an empty set is 0.0."""
        self.assertEqual(compute_hypervolume([]), 0.0)

    def test_points_outside_reference_region(self) -> None:
        """Points outside useful region (point[i] > ref[i]) contribute 0.0."""
        # A point with one coordinate strictly greater than reference
        hv = compute_hypervolume([(1.2, 0.5, 0.5)], reference_point=(1.1, 1.1, 1.1))
        self.assertEqual(hv, 0.0)

        # Mix of valid and invalid points: only valid point contributes
        hv_mixed = compute_hypervolume([(0.0, 0.0, 0.0), (1.5, 0.5, 0.5)], reference_point=(1.0, 1.0, 1.0))
        self.assertAlmostEqual(hv_mixed, 1.0, places=7)

    def test_single_point_origin(self) -> None:
        """Origin point with reference (1.1, 1.1, 1.1) produces 1.1^3."""
        hv = compute_hypervolume([(0.0, 0.0, 0.0)], reference_point=(1.1, 1.1, 1.1))
        self.assertAlmostEqual(hv, 1.1**3, places=7)

    def test_single_point_corner(self) -> None:
        """Point (1.0, 1.0, 1.0) with reference (1.1, 1.1, 1.1) produces 0.1^3."""
        hv = compute_hypervolume([(1.0, 1.0, 1.0)], reference_point=(1.1, 1.1, 1.1))
        self.assertAlmostEqual(hv, 0.1**3, places=7)

    def test_point_on_reference_boundary(self) -> None:
        """Point with point[i] == reference_point[i] produces 0.0 volume."""
        hv = compute_hypervolume([(1.1, 0.5, 0.5)], reference_point=(1.1, 1.1, 1.1))
        self.assertEqual(hv, 0.0)

    def test_analytical_two_points_with_overlap(self) -> None:
        """Analytical verification of 3D volume for two points with overlap."""
        # Point A: (0.2, 0.6, 0.6) -> box [0.2, 1]x[0.6, 1]x[0.6, 1] = 0.8 * 0.4 * 0.4 = 0.128
        # Point B: (0.6, 0.2, 0.6) -> box [0.6, 1]x[0.2, 1]x[0.6, 1] = 0.4 * 0.8 * 0.4 = 0.128
        # Intersection: [0.6, 1]x[0.6, 1]x[0.6, 1] = 0.4 * 0.4 * 0.4 = 0.064
        # Union volume = 0.128 + 0.128 - 0.064 = 0.192
        ref = (1.0, 1.0, 1.0)
        pts = [(0.2, 0.6, 0.6), (0.6, 0.2, 0.6)]
        hv = compute_hypervolume(pts, reference_point=ref)
        self.assertAlmostEqual(hv, 0.192, places=7)

    def test_analytical_two_points_distinct_coordinates(self) -> None:
        """Analytical verification with distinct coordinates on all 3 axes."""
        # Point A: (0.2, 0.4, 0.8) -> 0.8 * 0.6 * 0.2 = 0.096
        # Point B: (0.5, 0.2, 0.4) -> 0.5 * 0.8 * 0.6 = 0.240
        # Intersection: [0.5, 1]x[0.4, 1]x[0.8, 1] = 0.5 * 0.6 * 0.2 = 0.060
        # Union volume = 0.096 + 0.240 - 0.060 = 0.276
        ref = (1.0, 1.0, 1.0)
        pts = [(0.2, 0.4, 0.8), (0.5, 0.2, 0.4)]
        hv = compute_hypervolume(pts, reference_point=ref)
        self.assertAlmostEqual(hv, 0.276, places=7)

    def test_internally_dominated_point_ignored(self) -> None:
        """Points dominated by another point in the set must not inflate the volume."""
        ref = (1.0, 1.0, 1.0)
        # Point A dominates Point B
        pt_a = (0.2, 0.2, 0.2)
        pt_b = (0.5, 0.5, 0.5)

        hv_a_only = compute_hypervolume([pt_a], reference_point=ref)
        hv_both = compute_hypervolume([pt_a, pt_b], reference_point=ref)

        self.assertAlmostEqual(hv_both, hv_a_only, places=7)
        self.assertAlmostEqual(hv_both, 0.8**3, places=7)

    def test_duplicate_points_do_not_inflate_volume(self) -> None:
        """Duplicated points must yield identical volume."""
        ref = (1.1, 1.1, 1.1)
        pt = (0.3, 0.4, 0.5)
        hv_single = compute_hypervolume([pt], reference_point=ref)
        hv_duplicate = compute_hypervolume([pt, pt, pt], reference_point=ref)
        self.assertAlmostEqual(hv_duplicate, hv_single, places=7)

    def test_monotonicity(self) -> None:
        """Adding a non-dominated point must weakly increase hypervolume."""
        ref = (1.1, 1.1, 1.1)
        pts = [(0.2, 0.5, 0.5), (0.5, 0.2, 0.5)]
        hv_base = compute_hypervolume(pts, reference_point=ref)

        # Add a third non-dominated point
        pts_extended = pts + [(0.5, 0.5, 0.2)]
        hv_extended = compute_hypervolume(pts_extended, reference_point=ref)

        self.assertGreater(hv_extended, hv_base)

    def test_input_dimension_validation(self) -> None:
        """Points or reference with dimension != 3 must raise ValueError."""
        with self.assertRaises(ValueError):
            compute_hypervolume([(0.1, 0.2)], reference_point=(1.1, 1.1, 1.1))

        with self.assertRaises(ValueError):
            compute_hypervolume([(0.1, 0.2, 0.3)], reference_point=(1.1, 1.1))  # type: ignore

    def test_compute_archive_hypervolume_integration(self) -> None:
        """Test integration of ParetoArchive, ObjectiveNormalizer and compute_archive_hypervolume."""
        from mojssp import compute_instance_bounds, decode, evaluate

        toy_dzn = Path(__file__).resolve().parent.parent / "data" / "validation" / "toy_instance.dzn"
        instance = load_dzn(str(toy_dzn))

        bounds = compute_instance_bounds(instance)
        normalizer = ObjectiveNormalizer(bounds)
        archive = ParetoArchive()

        sol1 = Solution(sequence=(1, 2, 1, 2), modes=(1, 1, 1, 1))
        sched1 = decode(instance, sol1)
        objs1 = evaluate(instance, sched1)

        sol2 = Solution(sequence=(2, 1, 2, 1), modes=(2, 2, 2, 2))
        sched2 = decode(instance, sol2)
        objs2 = evaluate(instance, sched2)

        archive.add(sol1, sched1, objs1)
        archive.add(sol2, sched2, objs2)

        # Archive size before HV computation
        size_before = len(archive)

        hv = compute_archive_hypervolume(archive, normalizer)

        # Archive must NOT be modified by the HV calculation
        self.assertEqual(len(archive), size_before)
        self.assertGreater(hv, 0.0)


if __name__ == "__main__":
    unittest.main()
