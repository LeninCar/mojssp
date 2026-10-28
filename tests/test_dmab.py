"""Unit and integration tests for DMABSelector and SlidingWindowUCB (Phase 7.4)."""

import math
from pathlib import Path
import sys
import unittest

# Add src directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mojssp import (
    ArmStats,
    DMABSelector,
    MOPSOArm,
    NSGA2Arm,
    NSGA2LSArm,
    Portfolio,
    SlidingWindowUCB,
    load_dzn,
)


class TestDMAB(unittest.TestCase):
    """Test suite for Dynamic Multi-Armed Bandit (DMAB) selector."""

    def setUp(self) -> None:
        self.arm_names = ("NSGA-II", "MOPSO", "NSGA-II+LS")
        toy_path = Path(__file__).resolve().parent.parent / "data" / "validation" / "toy_instance.dzn"
        self.instance = load_dzn(toy_path)
        self.seed = 42

    def test_protocol_conformance(self) -> None:
        """Test 1: Verify protocol conformance, default parameters, and initial stats."""
        dmab = SlidingWindowUCB(arm_names=self.arm_names)

        self.assertIsInstance(dmab, DMABSelector)
        self.assertEqual(dmab.arm_names, self.arm_names)
        self.assertEqual(dmab.total_pulls, 0)
        self.assertEqual(dmab.window_size, 10)
        self.assertAlmostEqual(dmab.exploration_factor, math.sqrt(2), places=6)

        stats = dmab.get_stats()
        self.assertEqual(len(stats), 3)
        for name in self.arm_names:
            self.assertIn(name, stats)
            s = stats[name]
            self.assertIsInstance(s, ArmStats)
            self.assertEqual(s.arm_name, name)
            self.assertEqual(s.total_pulls, 0)
            self.assertEqual(s.window_pulls, 0)
            self.assertEqual(s.window_mean, 0.0)
            self.assertEqual(s.ucb, float("inf"))

    def test_validation(self) -> None:
        """Test 2: Verify rigorous validation of constructor and update inputs."""
        # Empty arm_names
        with self.assertRaises(ValueError):
            SlidingWindowUCB(arm_names=[])

        # Duplicate arm_names
        with self.assertRaises(ValueError):
            SlidingWindowUCB(arm_names=["A", "B", "A"])

        # Non-string or empty arm names
        with self.assertRaises(ValueError):
            SlidingWindowUCB(arm_names=["A", "  ", "B"])
        with self.assertRaises(ValueError):
            SlidingWindowUCB(arm_names=["A", 123, "B"])  # type: ignore

        # Invalid window_size
        with self.assertRaises(ValueError):
            SlidingWindowUCB(arm_names=["A", "B"], window_size=0)
        with self.assertRaises(ValueError):
            SlidingWindowUCB(arm_names=["A", "B"], window_size=-5)
        with self.assertRaises(ValueError):
            SlidingWindowUCB(arm_names=["A", "B"], window_size="10")  # type: ignore
        with self.assertRaises(ValueError):
            SlidingWindowUCB(arm_names=["A", "B"], window_size=True)  # type: ignore

        # Invalid exploration_factor
        with self.assertRaises(ValueError):
            SlidingWindowUCB(arm_names=["A", "B"], exploration_factor=-0.1)
        with self.assertRaises(ValueError):
            SlidingWindowUCB(arm_names=["A", "B"], exploration_factor=float("nan"))
        with self.assertRaises(ValueError):
            SlidingWindowUCB(arm_names=["A", "B"], exploration_factor=float("inf"))
        with self.assertRaises(ValueError):
            SlidingWindowUCB(arm_names=["A", "B"], exploration_factor="1.0")  # type: ignore

        # Invalid update calls
        dmab = SlidingWindowUCB(arm_names=["A", "B"])
        with self.assertRaises(KeyError):
            dmab.update("NON_EXISTENT", 1.0)
        with self.assertRaises(ValueError):
            dmab.update("A", float("nan"))
        with self.assertRaises(ValueError):
            dmab.update("A", float("inf"))
        with self.assertRaises(ValueError):
            dmab.update("A", "high")  # type: ignore
        with self.assertRaises(ValueError):
            dmab.update("A", True)  # type: ignore

    def test_warmup(self) -> None:
        """Test 3: Warm-up selects all arms in registration order before UCB rule applies."""
        dmab = SlidingWindowUCB(arm_names=self.arm_names)

        # First arm
        self.assertEqual(dmab.select_arm(), "NSGA-II")
        # Idempotence: calling select_arm without update keeps selecting the same unpulled arm
        self.assertEqual(dmab.select_arm(), "NSGA-II")
        dmab.update("NSGA-II", 0.5)

        # Second arm
        self.assertEqual(dmab.select_arm(), "MOPSO")
        self.assertEqual(dmab.select_arm(), "MOPSO")
        dmab.update("MOPSO", 0.8)

        # Third arm
        self.assertEqual(dmab.select_arm(), "NSGA-II+LS")
        self.assertEqual(dmab.select_arm(), "NSGA-II+LS")
        dmab.update("NSGA-II+LS", 0.2)

        # Warm-up complete
        self.assertEqual(dmab.total_pulls, 3)
        stats = dmab.get_stats()
        for name in self.arm_names:
            self.assertEqual(stats[name].total_pulls, 1)
            self.assertEqual(stats[name].window_pulls, 1)

    def test_update(self) -> None:
        """Test 4: Verify update increments counters, sliding window, and computes means."""
        dmab = SlidingWindowUCB(arm_names=["A", "B"], window_size=5)

        dmab.update("A", 1.0)
        self.assertEqual(dmab.total_pulls, 1)
        s_a = dmab.get_stats()["A"]
        self.assertEqual(s_a.total_pulls, 1)
        self.assertEqual(s_a.window_pulls, 1)
        self.assertAlmostEqual(s_a.window_mean, 1.0)

        dmab.update("A", 3.0)
        self.assertEqual(dmab.total_pulls, 2)
        s_a = dmab.get_stats()["A"]
        self.assertEqual(s_a.total_pulls, 2)
        self.assertEqual(s_a.window_pulls, 2)
        self.assertAlmostEqual(s_a.window_mean, 2.0)

    def test_sliding_window_eviction(self) -> None:
        """Test 5: Observations beyond window_size are evicted and affect mean and UCB."""
        dmab = SlidingWindowUCB(arm_names=["A", "B"], window_size=3)

        dmab.update("A", 10.0)  # [ (A, 10) ]
        dmab.update("B", 1.0)  # [ (A, 10), (B, 1) ]
        dmab.update("B", 2.0)  # [ (A, 10), (B, 1), (B, 2) ]

        stats = dmab.get_stats()
        self.assertEqual(stats["A"].window_pulls, 1)
        self.assertAlmostEqual(stats["A"].window_mean, 10.0)
        self.assertEqual(stats["B"].window_pulls, 2)
        self.assertAlmostEqual(stats["B"].window_mean, 1.5)

        # 4th update evicts the oldest observation (A, 10.0)
        dmab.update("B", 3.0)  # [ (B, 1), (B, 2), (B, 3) ]

        stats = dmab.get_stats()
        self.assertEqual(stats["A"].total_pulls, 1)
        self.assertEqual(stats["A"].window_pulls, 0)
        self.assertEqual(stats["A"].window_mean, 0.0)
        self.assertEqual(stats["A"].ucb, float("inf"))

        self.assertEqual(stats["B"].total_pulls, 3)
        self.assertEqual(stats["B"].window_pulls, 3)
        self.assertAlmostEqual(stats["B"].window_mean, 2.0)

    def test_ucb_calculation(self) -> None:
        """Test 6: Verify exact analytical calculation of UCB values."""
        c = 1.5
        W = 5
        dmab = SlidingWindowUCB(arm_names=["A", "B"], window_size=W, exploration_factor=c)

        # Warm up
        dmab.update("A", 1.0)
        dmab.update("B", 0.5)
        # Additional pull on A
        dmab.update("A", 2.0)

        # total_pulls = 3
        # t_eff = min(3, 5) = 3
        # Arm A: rewards [1.0, 2.0], N_{A,W} = 2, mean = 1.5
        # Arm B: rewards [0.5], N_{B,W} = 1, mean = 0.5
        expected_ucb_a = 1.5 + c * math.sqrt(math.log(3) / 2)
        expected_ucb_b = 0.5 + c * math.sqrt(math.log(3) / 1)

        stats = dmab.get_stats()
        self.assertAlmostEqual(stats["A"].ucb, expected_ucb_a, places=6)
        self.assertAlmostEqual(stats["B"].ucb, expected_ucb_b, places=6)

    def test_exploration_unobserved_arm(self) -> None:
        """Test 7: Any arm with 0 pulls in the window has UCB = inf and is chosen for exploration."""
        dmab = SlidingWindowUCB(arm_names=["A", "B"], window_size=2)

        # Warm up both
        dmab.update("A", 1.0)
        dmab.update("B", 1.0)

        # Pull B twice so A is completely evicted from window
        dmab.update("B", 2.0)
        dmab.update("B", 2.0)

        stats = dmab.get_stats()
        self.assertEqual(stats["A"].window_pulls, 0)
        self.assertEqual(stats["A"].ucb, float("inf"))
        self.assertNotEqual(stats["B"].ucb, float("inf"))

        # Must select A due to infinite UCB
        self.assertEqual(dmab.select_arm(), "A")

    def test_non_stationarity(self) -> None:
        """Test 8: Adapts to regime shift when reward distributions invert."""
        # Arm A initially excellent (1.0), Arm B initially poor (0.1)
        dmab = SlidingWindowUCB(arm_names=["A", "B"], window_size=4, exploration_factor=0.2)

        # Warm up
        dmab.update("A", 1.0)
        dmab.update("B", 0.1)

        # Regime 1: A dominates while both arms are in the window (steps 0 to 3)
        for _ in range(4):
            arm = dmab.select_arm()
            self.assertEqual(arm, "A")
            dmab.update("A", 1.0)

        # After 4 pulls of A in a window of size 4, B is evicted and its UCB becomes inf
        self.assertEqual(dmab.get_stats()["B"].window_pulls, 0)
        self.assertEqual(dmab.get_stats()["B"].ucb, float("inf"))

        # Re-exploration of B is triggered
        re_explored = dmab.select_arm()
        self.assertEqual(re_explored, "B")

        # Regime shift: B now yields 5.0 (high) while A yields 0.0 (low)
        dmab.update("B", 5.0)
        self.assertEqual(dmab.select_arm(), "B")
        dmab.update("B", 5.0)

        # Now B dominates the window with mean 5.0 vs A's older rewards
        stats = dmab.get_stats()
        self.assertGreater(stats["B"].ucb, stats["A"].ucb)
        self.assertEqual(dmab.select_arm(), "B")

    def test_determinism_same_seed(self) -> None:
        """Test 9: Two instances with identical seed and updates produce identical selections."""
        dmab1 = SlidingWindowUCB(arm_names=self.arm_names, seed=123)
        dmab2 = SlidingWindowUCB(arm_names=self.arm_names, seed=123)

        selections1 = []
        selections2 = []

        # Synthetic rewards with ties
        rewards = [0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5]
        for r in rewards:
            arm1 = dmab1.select_arm()
            arm2 = dmab2.select_arm()
            selections1.append(arm1)
            selections2.append(arm2)
            dmab1.update(arm1, r)
            dmab2.update(arm2, r)

        self.assertEqual(selections1, selections2)

    def test_different_seeds_tie_breaking(self) -> None:
        """Test 10: Different seeds can break ties differently."""
        # If multiple arms have the same UCB, tie-breaking uses RNG.
        # Run across multiple seeds until different choices are observed.
        choices_seed1 = []
        choices_seed2 = []

        dmab1 = SlidingWindowUCB(arm_names=("A", "B", "C"), seed=1)
        dmab2 = SlidingWindowUCB(arm_names=("A", "B", "C"), seed=999)

        # Warm-up (deterministic registration order)
        for name in ("A", "B", "C"):
            dmab1.update(name, 1.0)
            dmab2.update(name, 1.0)

        # All arms have equal window_pulls (1), equal window_mean (1.0), equal UCB
        for _ in range(10):
            c1 = dmab1.select_arm()
            c2 = dmab2.select_arm()
            choices_seed1.append(c1)
            choices_seed2.append(c2)
            dmab1.update(c1, 1.0)
            dmab2.update(c2, 1.0)

        # Because seeds differ, the tie-breaking trajectories should diverge
        self.assertNotEqual(choices_seed1, choices_seed2)

    def test_reset(self) -> None:
        """Test 11: reset() restores initial state and produces identical trajectory."""
        dmab = SlidingWindowUCB(arm_names=self.arm_names, seed=777)

        history_before = []
        rewards = [0.1, 0.9, 0.4, 0.7, 0.3, 0.8, 0.2]
        for r in rewards:
            arm = dmab.select_arm()
            history_before.append(arm)
            dmab.update(arm, r)

        dmab.reset()

        self.assertEqual(dmab.total_pulls, 0)
        stats = dmab.get_stats()
        for name in self.arm_names:
            self.assertEqual(stats[name].total_pulls, 0)
            self.assertEqual(stats[name].window_pulls, 0)
            self.assertEqual(stats[name].ucb, float("inf"))

        history_after = []
        for r in rewards:
            arm = dmab.select_arm()
            history_after.append(arm)
            dmab.update(arm, r)

        self.assertEqual(history_before, history_after)

    def test_integration_with_portfolio(self) -> None:
        """Test 12: End-to-end integration loop between Portfolio and SlidingWindowUCB."""
        arm1 = NSGA2Arm(self.instance, population_size=10, seed=self.seed)
        arm2 = MOPSOArm(self.instance, population_size=10, seed=self.seed)
        arm3 = NSGA2LSArm(self.instance, population_size=10, seed=self.seed)

        portfolio = Portfolio(arms=[arm1, arm2, arm3])
        dmab = SlidingWindowUCB(arm_names=portfolio.arm_names, window_size=5, seed=self.seed)

        block_budget = 15
        total_blocks = 6

        executed_arms = []
        evaluations_per_block = []

        for _ in range(total_blocks):
            # 1. DMAB selects arm
            selected = dmab.select_arm()
            executed_arms.append(selected)

            prev_archive_size = len(portfolio.global_archive)

            # 2. Portfolio runs the selected arm
            result = portfolio.run_arm(selected, budget=block_budget)
            evaluations_per_block.append(result.evaluations_used)

            # 3. Compute reward (e.g. expansion of global archive)
            curr_archive_size = len(portfolio.global_archive)
            reward = float(curr_archive_size - prev_archive_size)

            # 4. DMAB updates with scalar reward
            dmab.update(selected, reward)

        # Invariants verification
        self.assertEqual(dmab.total_pulls, total_blocks)
        self.assertEqual(len(executed_arms), total_blocks)

        # Warm-up guaranteed all 3 registered arms ran at least once
        self.assertIn("NSGA-II", executed_arms[:3])
        self.assertIn("MOPSO", executed_arms[:3])
        self.assertIn("NSGA-II+LS", executed_arms[:3])

        # Global evaluations and archive
        self.assertEqual(portfolio.total_evaluations, sum(evaluations_per_block))
        self.assertGreater(len(portfolio.global_archive), 0)

        # Arm evaluations bounded by budget
        for evals in evaluations_per_block:
            self.assertLessEqual(evals, block_budget)


if __name__ == "__main__":
    unittest.main()
