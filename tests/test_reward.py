"""Unit tests for HypervolumeRewardTracker and reward invariants (Phase 7.5)."""

from pathlib import Path
import sys
import unittest

# Add src directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mojssp import (
    HypervolumeRewardTracker,
    ObjectiveNormalizer,
    ObjectiveValues,
    ParetoArchive,
    RewardInvariantError,
    Schedule,
    ScheduledOperation,
    Solution,
    compute_archive_hypervolume,
    compute_instance_bounds,
    decode,
    evaluate,
    load_dzn,
)


class TestReward(unittest.TestCase):
    """Test suite for HypervolumeRewardTracker and ΔHV reward calculation."""

    def setUp(self) -> None:
        toy_path = Path(__file__).resolve().parent.parent / "data" / "validation" / "toy_instance.dzn"
        self.instance = load_dzn(toy_path)
        self.bounds = compute_instance_bounds(self.instance)
        self.normalizer = ObjectiveNormalizer(self.bounds)

        # Build two distinct non-dominated solutions for controlled archive states
        self.sol1 = Solution(sequence=(1, 2, 1, 2), modes=(1, 1, 1, 1))
        self.sched1 = decode(self.instance, self.sol1)
        self.objs1 = evaluate(self.instance, self.sched1)

        self.sol2 = Solution(sequence=(2, 1, 2, 1), modes=(2, 2, 2, 2))
        self.sched2 = decode(self.instance, self.sol2)
        self.objs2 = evaluate(self.instance, self.sched2)

    def test_first_reward_empty_then_positive(self) -> None:
        """Test 1: Initial reward is 0.0 on empty archive, and HV_after on first populated archive."""
        tracker = HypervolumeRewardTracker(self.normalizer)
        self.assertEqual(tracker.current_hv, 0.0)

        empty_archive = ParetoArchive()
        r0 = tracker.compute_reward(empty_archive)
        self.assertEqual(r0, 0.0)
        self.assertEqual(tracker.current_hv, 0.0)

        # Add sol1
        archive = ParetoArchive()
        archive.add(self.sol1, self.sched1, self.objs1)
        expected_hv = compute_archive_hypervolume(archive, self.normalizer)
        self.assertGreater(expected_hv, 0.0)

        r1 = tracker.compute_reward(archive)
        self.assertAlmostEqual(r1, expected_hv, places=9)
        self.assertAlmostEqual(tracker.current_hv, expected_hv, places=9)

    def test_positive_delta_hv(self) -> None:
        """Test 2: Sequential improvements produce exact reward = HV2 - HV1."""
        tracker = HypervolumeRewardTracker(self.normalizer)

        archive = ParetoArchive()
        archive.add(self.sol1, self.sched1, self.objs1)
        hv1 = compute_archive_hypervolume(archive, self.normalizer)
        r1 = tracker.compute_reward(archive)
        self.assertAlmostEqual(r1, hv1, places=9)

        # Add sol2 to expand the front
        archive.add(self.sol2, self.sched2, self.objs2)
        hv2 = compute_archive_hypervolume(archive, self.normalizer)
        self.assertGreater(hv2, hv1)

        r2 = tracker.compute_reward(archive)
        self.assertAlmostEqual(r2, hv2 - hv1, places=9)
        self.assertAlmostEqual(tracker.current_hv, hv2, places=9)

    def test_zero_reward_without_improvement(self) -> None:
        """Test 3: Evaluating the same archive state produces exactly reward = 0.0."""
        tracker = HypervolumeRewardTracker(self.normalizer)

        archive = ParetoArchive()
        archive.add(self.sol1, self.sched1, self.objs1)
        r1 = tracker.compute_reward(archive)
        self.assertGreater(r1, 0.0)

        # Second evaluation with unchanged archive
        r2 = tracker.compute_reward(archive)
        self.assertEqual(r2, 0.0)

        # Third evaluation with identical archive
        r3 = tracker.compute_reward(archive)
        self.assertEqual(r3, 0.0)

    def test_monotonicity(self) -> None:
        """Test 4: Adding non-dominated solutions strictly satisfies HV_after >= HV_before."""
        tracker = HypervolumeRewardTracker(self.normalizer)

        archive = ParetoArchive()
        prev_hv = 0.0

        for sol, sched, objs in [
            (self.sol1, self.sched1, self.objs1),
            (self.sol2, self.sched2, self.objs2),
        ]:
            archive.add(sol, sched, objs)
            r = tracker.compute_reward(archive)
            self.assertGreaterEqual(r, 0.0)
            self.assertGreaterEqual(tracker.current_hv, prev_hv)
            prev_hv = tracker.current_hv

    def test_reset(self) -> None:
        """Test 5: Resetting the tracker restores previous_hv = 0.0 and reproduces first reward."""
        tracker = HypervolumeRewardTracker(self.normalizer)

        archive = ParetoArchive()
        archive.add(self.sol1, self.sched1, self.objs1)
        r1 = tracker.compute_reward(archive)
        self.assertGreater(r1, 0.0)

        tracker.reset()
        self.assertEqual(tracker.current_hv, 0.0)

        r1_after_reset = tracker.compute_reward(archive)
        self.assertAlmostEqual(r1_after_reset, r1, places=9)

    def test_archive_not_mutated(self) -> None:
        """Test 6: compute_reward treats archive as read-only and does not mutate it."""
        tracker = HypervolumeRewardTracker(self.normalizer)

        archive = ParetoArchive()
        archive.add(self.sol1, self.sched1, self.objs1)
        entries_before = tuple(archive.entries)
        len_before = len(archive)

        tracker.compute_reward(archive)

        self.assertEqual(len(archive), len_before)
        self.assertEqual(archive.entries, entries_before)

    def test_numerical_tolerance_and_invariant_violation(self) -> None:
        """Test 7: Micro-fluctuations within tolerance yield 0.0; real drops raise RewardInvariantError."""
        tracker = HypervolumeRewardTracker(self.normalizer, tolerance=1e-8)

        archive = ParetoArchive()
        archive.add(self.sol1, self.sched1, self.objs1)
        tracker.compute_reward(archive)
        original_hv = tracker.current_hv

        # Simulate micro downward fluctuation by manually setting previous_hv slightly higher (within tolerance)
        tracker._previous_hv = original_hv + 1e-10
        r_micro = tracker.compute_reward(archive)
        self.assertEqual(r_micro, 0.0)

        # Simulate significant downward violation (> tolerance)
        tracker._previous_hv = original_hv + 0.1
        with self.assertRaises(RewardInvariantError):
            tracker.compute_reward(archive)

    def test_validation(self) -> None:
        """Test 8: Constructor and compute_reward parameter validation."""
        with self.assertRaises(TypeError):
            HypervolumeRewardTracker("not_a_normalizer")  # type: ignore

        with self.assertRaises(ValueError):
            HypervolumeRewardTracker(self.normalizer, reference_point=(1.1, 1.1))  # type: ignore

        with self.assertRaises(ValueError):
            HypervolumeRewardTracker(self.normalizer, tolerance=-1e-5)

        tracker = HypervolumeRewardTracker(self.normalizer)
        with self.assertRaises(TypeError):
            tracker.compute_reward("not_an_archive")  # type: ignore


if __name__ == "__main__":
    unittest.main()
