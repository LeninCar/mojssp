"""Unit tests for objective normalization and instance bounds computation (Phase 4.2)."""

from dataclasses import FrozenInstanceError
from pathlib import Path
import sys
import unittest

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mojssp import (
    ArchiveEntry,
    Instance,
    Job,
    NormalizationBoundError,
    ObjectiveBounds,
    ObjectiveNormalizer,
    ObjectiveValues,
    Operation,
    ParetoArchive,
    ProcessingMode,
    Schedule,
    ScheduledOperation,
    Solution,
    compute_instance_bounds,
    load_dzn,
)


class TestNormalization(unittest.TestCase):
    """Test suite for ObjectiveBounds and ObjectiveNormalizer."""

    def setUp(self) -> None:
        self.toy_dzn_path = Path(__file__).resolve().parent.parent / "data" / "validation" / "toy_instance.dzn"
        self.instance = load_dzn(str(self.toy_dzn_path))

    def test_bounds_computation_toy_instance(self) -> None:
        """Test analytical bounds on toy_instance.dzn."""
        bounds = compute_instance_bounds(self.instance)

        # Expected analytical values:
        # Job 1 min time: 3 + 4 = 7; Job 2 min time: 2 + 5 = 7 -> Cmin = 7.0
        self.assertEqual(bounds.cmax_min, 7.0)

        # Max duration sum: 5 + 6 + 4 + 7 = 22; max release = 0 -> Cmax_bound = 22.0
        self.assertEqual(bounds.cmax_max, 22.0)

        # Min energy sum: 10 + 15 + 10 + 18 = 53.0
        self.assertEqual(bounds.energy_min, 53.0)

        # Max energy sum: 20 + 25 + 20 + 28 = 93.0
        self.assertEqual(bounds.energy_max, 93.0)

        # Tardiness bounds: Tmin = 0, Tmax = max(0, 22-10) + max(0, 22-10) = 24.0
        self.assertEqual(bounds.tardiness_min, 0.0)
        self.assertEqual(bounds.tardiness_max, 24.0)

    def test_cmax_min_with_differing_operation_releases(self) -> None:
        """Test that cmax_min is a valid lower bound (does not exceed feasible makespan)

        when operations of a job have different release dates.
        """
        from mojssp import decode, evaluate

        # Case 1: Op 0 runs [0, 10], Op 1 released at 10 and runs [10, 15] -> makespan 15
        # Old formula would compute: max(0, 10) + (10 + 5) = 25 > 15 (invalid)
        # Corrected formula computes: max(0 + 15, 10 + 5) = 15 <= 15 (valid)
        mode1 = ProcessingMode(mode_id=1, duration=10, energy=20.0)
        mode2 = ProcessingMode(mode_id=1, duration=5, energy=15.0)

        op1 = Operation(job_id=1, op_id=0, machine_id=1, modes=(mode1,), release_date=0)
        op2 = Operation(job_id=1, op_id=1, machine_id=2, modes=(mode2,), release_date=10)

        job1 = Job(job_id=1, operations=(op1, op2), due_date=30)
        instance1 = Instance(name="inst1", num_jobs=1, num_machines=2, jobs=(job1,))

        bounds1 = compute_instance_bounds(instance1)
        self.assertEqual(bounds1.cmax_min, 15.0)

        sol1 = Solution(sequence=(1, 1), modes=(1, 1))
        sched1 = decode(instance1, sol1)
        res1 = evaluate(instance1, sched1)

        self.assertEqual(sched1.makespan, 15)
        self.assertLessEqual(bounds1.cmax_min, res1.makespan)

        # Case 2: Op 0 runs [0, 4], Op 1 released at 10 and runs [10, 13] -> makespan 13
        # LB_0 = 0 + 7 = 7, LB_1 = 10 + 3 = 13 -> cmax_min = 13 <= 13
        # Old formula would compute: 10 + 7 = 17 > 13 (invalid)
        mode3 = ProcessingMode(mode_id=1, duration=4, energy=10.0)
        mode4 = ProcessingMode(mode_id=1, duration=3, energy=10.0)

        op3 = Operation(job_id=1, op_id=0, machine_id=1, modes=(mode3,), release_date=0)
        op4 = Operation(job_id=1, op_id=1, machine_id=2, modes=(mode4,), release_date=10)

        job2 = Job(job_id=1, operations=(op3, op4), due_date=30)
        instance2 = Instance(name="inst2", num_jobs=1, num_machines=2, jobs=(job2,))

        bounds2 = compute_instance_bounds(instance2)
        self.assertEqual(bounds2.cmax_min, 13.0)

        sol2 = Solution(sequence=(1, 1), modes=(1, 1))
        sched2 = decode(instance2, sol2)
        res2 = evaluate(instance2, sched2)

        self.assertEqual(sched2.makespan, 13)
        self.assertLessEqual(bounds2.cmax_min, res2.makespan)


    def test_bounds_post_init_validation(self) -> None:
        """Test that invalid bounds raise ValueError."""
        # Lower > upper
        with self.assertRaises(ValueError):
            ObjectiveBounds(
                cmax_min=20.0,
                cmax_max=10.0,
                tardiness_min=0.0,
                tardiness_max=10.0,
                energy_min=0.0,
                energy_max=10.0,
            )
        # Negative lower
        with self.assertRaises(ValueError):
            ObjectiveBounds(
                cmax_min=-1.0,
                cmax_max=10.0,
                tardiness_min=0.0,
                tardiness_max=10.0,
                energy_min=0.0,
                energy_max=10.0,
            )

    def test_bounds_immutability(self) -> None:
        """Test that ObjectiveBounds is frozen."""
        bounds = compute_instance_bounds(self.instance)
        with self.assertRaises(FrozenInstanceError):
            bounds.cmax_min = 10.0  # type: ignore

    def test_normalize_extreme_and_midpoint(self) -> None:
        """Test mapping of minimum, maximum, and midpoint values to [0, 1]."""
        bounds = ObjectiveBounds(
            cmax_min=10.0,
            cmax_max=20.0,
            tardiness_min=0.0,
            tardiness_max=10.0,
            energy_min=100.0,
            energy_max=200.0,
        )
        normalizer = ObjectiveNormalizer(bounds)

        # Minimum point -> (0.0, 0.0, 0.0)
        min_norm = normalizer.normalize_tuple((10.0, 0.0, 100.0))
        self.assertEqual(min_norm, (0.0, 0.0, 0.0))

        # Maximum point -> (1.0, 1.0, 1.0)
        max_norm = normalizer.normalize_tuple((20.0, 10.0, 200.0))
        self.assertEqual(max_norm, (1.0, 1.0, 1.0))

        # Midpoint -> (0.5, 0.5, 0.5)
        mid_norm = normalizer.normalize_tuple((15.0, 5.0, 150.0))
        self.assertEqual(mid_norm, (0.5, 0.5, 0.5))

    def test_normalize_objective_values_object(self) -> None:
        """Test normalizing an ObjectiveValues instance."""
        bounds = ObjectiveBounds(
            cmax_min=10.0,
            cmax_max=20.0,
            tardiness_min=0.0,
            tardiness_max=10.0,
            energy_min=100.0,
            energy_max=200.0,
        )
        normalizer = ObjectiveNormalizer(bounds)
        obj = ObjectiveValues(makespan=15, tardiness=5, energy=150.0)
        norm = normalizer.normalize_tuple(obj)
        self.assertEqual(norm, (0.5, 0.5, 0.5))

    def test_denormalize_tuple(self) -> None:
        """Test denormalizing back to the original scale."""
        bounds = ObjectiveBounds(
            cmax_min=10.0,
            cmax_max=20.0,
            tardiness_min=0.0,
            tardiness_max=10.0,
            energy_min=100.0,
            energy_max=200.0,
        )
        normalizer = ObjectiveNormalizer(bounds)
        denorm = normalizer.denormalize_tuple((0.5, 0.5, 0.5))
        self.assertEqual(denorm, (15.0, 5.0, 150.0))

    def test_normalization_bound_error_on_violation(self) -> None:
        """Test that out-of-bounds values raise NormalizationBoundError."""
        bounds = ObjectiveBounds(
            cmax_min=10.0,
            cmax_max=20.0,
            tardiness_min=0.0,
            tardiness_max=10.0,
            energy_min=100.0,
            energy_max=200.0,
        )
        normalizer = ObjectiveNormalizer(bounds)

        # Makespan too low
        with self.assertRaises(NormalizationBoundError):
            normalizer.normalize_tuple((9.0, 5.0, 150.0))

        # Makespan too high
        with self.assertRaises(NormalizationBoundError):
            normalizer.normalize_tuple((21.0, 5.0, 150.0))

        # Tardiness too low
        with self.assertRaises(NormalizationBoundError):
            normalizer.normalize_tuple((15.0, -1.0, 150.0))

        # Energy too high
        with self.assertRaises(NormalizationBoundError):
            normalizer.normalize_tuple((15.0, 5.0, 201.0))

    def test_no_silent_clipping(self) -> None:
        """Confirm that out-of-bounds values are NOT silently clipped to 0.0 or 1.0."""
        bounds = ObjectiveBounds(
            cmax_min=10.0,
            cmax_max=20.0,
            tardiness_min=0.0,
            tardiness_max=10.0,
            energy_min=100.0,
            energy_max=200.0,
        )
        normalizer = ObjectiveNormalizer(bounds)
        # An arbitrary large value must strictly raise an exception, not return 1.0
        with self.assertRaises(NormalizationBoundError):
            normalizer.normalize_tuple((100.0, 5.0, 150.0))

    def test_tolerance_boundaries(self) -> None:
        """Test behavior near boundary within and beyond numerical tolerance."""
        bounds = ObjectiveBounds(
            cmax_min=10.0,
            cmax_max=20.0,
            tardiness_min=0.0,
            tardiness_max=10.0,
            energy_min=100.0,
            energy_max=200.0,
        )
        normalizer = ObjectiveNormalizer(bounds, tolerance=1e-7)

        # Slightly below lower bound within tolerance -> maps coherently to 0.0
        res_low = normalizer.normalize_tuple((10.0 - 1e-9, 0.0, 100.0))
        self.assertEqual(res_low[0], 0.0)

        # Slightly above upper bound within tolerance -> maps coherently to 1.0
        res_high = normalizer.normalize_tuple((20.0 + 1e-9, 10.0, 200.0))
        self.assertEqual(res_high[0], 1.0)

        # Beyond tolerance -> raises NormalizationBoundError
        with self.assertRaises(NormalizationBoundError):
            normalizer.normalize_tuple((10.0 - 1e-5, 0.0, 100.0))

    def test_degenerate_equal_bounds(self) -> None:
        """Test behavior when lower == upper bound."""
        bounds = ObjectiveBounds(
            cmax_min=10.0,
            cmax_max=10.0,
            tardiness_min=0.0,
            tardiness_max=10.0,
            energy_min=100.0,
            energy_max=200.0,
        )
        normalizer = ObjectiveNormalizer(bounds)
        norm = normalizer.normalize_tuple((10.0, 5.0, 150.0))
        self.assertEqual(norm[0], 0.0)

        with self.assertRaises(NormalizationBoundError):
            normalizer.normalize_tuple((11.0, 5.0, 150.0))

    def test_normalize_archive(self) -> None:
        """Test normalizing an entire ParetoArchive."""
        from mojssp import decode, evaluate

        bounds = compute_instance_bounds(self.instance)
        normalizer = ObjectiveNormalizer(bounds)
        archive = ParetoArchive()

        sol = Solution(sequence=(1, 2, 1, 2), modes=(1, 1, 1, 1))
        sched = decode(self.instance, sol)
        objs = evaluate(self.instance, sched)

        archive.add(sol, sched, objs)

        norm_list = normalizer.normalize_archive(archive)
        self.assertEqual(len(norm_list), 1)
        cmax_norm, t_norm, e_norm = norm_list[0]
        self.assertTrue(0.0 <= cmax_norm <= 1.0)
        self.assertTrue(0.0 <= t_norm <= 1.0)
        self.assertTrue(0.0 <= e_norm <= 1.0)


if __name__ == "__main__":
    unittest.main()
