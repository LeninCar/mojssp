"""Unit tests for IGD metric and empirical reference front builder (Phase 8.2)."""

import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mojssp import (
    Instance,
    Job,
    ObjectiveBounds,
    ObjectiveNormalizer,
    ObjectiveValues,
    Operation,
    ParetoArchive,
    ProcessingMode,
    Schedule,
    ScheduledOperation,
    Solution,
    build_empirical_reference_front,
    compute_archive_igd,
    compute_euclidean_distance,
    compute_igd,
    filter_non_dominated_points,
)


class TestIGD(unittest.TestCase):
    """Test suite for Euclidean distance, IGD computation, and empirical reference front."""

    def test_euclidean_distance(self):
        self.assertAlmostEqual(compute_euclidean_distance((0.0, 0.0), (3.0, 4.0)), 5.0)
        self.assertAlmostEqual(compute_euclidean_distance((1.0, 2.0, 3.0), (1.0, 2.0, 3.0)), 0.0)
        with self.assertRaises(ValueError):
            compute_euclidean_distance((1.0, 2.0), (1.0, 2.0, 3.0))

    def test_igd_validation(self):
        # Empty reference front raises ValueError
        with self.assertRaises(ValueError):
            compute_igd([(0.5, 0.5)], [])

        # Empty obtained front returns inf
        ref = [(0.0, 1.0), (1.0, 0.0)]
        self.assertEqual(compute_igd([], ref), float("inf"))

    def test_igd_perfect_coverage(self):
        ref = [(0.0, 1.0, 0.5), (1.0, 0.0, 0.5), (0.5, 0.5, 0.5)]
        # When obtained is identical to reference, IGD must be exactly 0.0
        self.assertAlmostEqual(compute_igd(ref, ref), 0.0)

    def test_igd_known_values(self):
        ref = [(0.0, 1.0), (1.0, 0.0)]
        # Obtained has a single point (0.5, 0.5)
        # Distance from (0, 1) to (0.5, 0.5) is sqrt(0.25 + 0.25) = sqrt(0.5)
        # Distance from (1, 0) to (0.5, 0.5) is sqrt(0.5)
        # IGD = (sqrt(0.5) + sqrt(0.5)) / 2 = sqrt(0.5)
        expected = math.sqrt(0.5)
        self.assertAlmostEqual(compute_igd([(0.5, 0.5)], ref), expected)

    def test_filter_non_dominated_points(self):
        # Points: (10, 10, 10), (12, 12, 12) [dominated by 1st], (10, 10, 10) [duplicate], (5, 20, 10) [trade-off]
        pts = [
            (10.0, 10.0, 10.0),
            (12.0, 12.0, 12.0),
            (10.0, 10.0, 10.0),
            (5.0, 20.0, 10.0),
        ]
        filtered = filter_non_dominated_points(pts)
        self.assertEqual(len(filtered), 2)
        self.assertIn((10.0, 10.0, 10.0), filtered)
        self.assertIn((5.0, 20.0, 10.0), filtered)
        self.assertNotIn((12.0, 12.0, 12.0), filtered)

    def test_compute_archive_igd_and_empirical_reference(self):
        bounds = ObjectiveBounds(
            cmax_min=10.0, cmax_max=30.0,
            tardiness_min=0.0, tardiness_max=20.0,
            energy_min=50.0, energy_max=150.0,
        )
        normalizer = ObjectiveNormalizer(bounds)

        # Build dummy solutions and schedules with matching makespan
        sol1 = Solution(sequence=(1,), modes=(1,))
        sched_op1 = ScheduledOperation(job_id=1, op_id=0, machine_id=0, mode_id=1, start=0, completion=10, duration=10, energy=50.0)
        sched1 = Schedule([sched_op1])
        objs1 = ObjectiveValues(makespan=10, tardiness=0, energy=50.0)

        sol2 = Solution(sequence=(1,), modes=(1,))
        sched_op2 = ScheduledOperation(job_id=1, op_id=0, machine_id=0, mode_id=1, start=0, completion=30, duration=30, energy=150.0)
        sched2 = Schedule([sched_op2])
        objs2 = ObjectiveValues(makespan=30, tardiness=20, energy=150.0)

        arch1 = ParetoArchive()
        arch1.add(sol1, sched1, objs1)  # normalized (0, 0, 0)

        arch2 = ParetoArchive()
        arch2.add(sol2, sched2, objs2)  # normalized (1, 1, 1)

        # Empirical reference front in normalized space
        ref_norm = build_empirical_reference_front([arch1, arch2], normalizer=normalizer)
        # Note: arch1 strictly dominates arch2 (0,0,0 vs 1,1,1), so ref_norm should only have (0,0,0)
        self.assertEqual(len(ref_norm), 1)
        self.assertEqual(ref_norm[0], (0.0, 0.0, 0.0))

        # IGD of arch1 against ref_norm should be 0.0
        igd_arch1 = compute_archive_igd(arch1, ref_norm, normalizer)
        self.assertAlmostEqual(igd_arch1, 0.0)

        # IGD of arch2 against ref_norm should be sqrt(1^2 + 1^2 + 1^2) = sqrt(3)
        igd_arch2 = compute_archive_igd(arch2, ref_norm, normalizer)
        self.assertAlmostEqual(igd_arch2, math.sqrt(3.0))

        # Empty archive gives inf
        empty_arch = ParetoArchive()
        self.assertEqual(compute_archive_igd(empty_arch, ref_norm, normalizer), float("inf"))


if __name__ == "__main__":
    unittest.main()
