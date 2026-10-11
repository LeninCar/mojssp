"""Test suite verifying neutral warm-up in algorithm portfolio (Phase 8.3.2).

Validates the decoupling of arm initialization from DMAB reward learning statistics:
- Test 1: Each arm runs in warm-up exactly once.
- Test 2: Warm-up does not feed DMAB (total_pulls == 0).
- Test 3: DMAB does not repeat warm-up due to lack of observations.
- Test 4: Only adaptive rewards appear in DMAB statistics.
- Test 5: Global Pareto Archive accumulates warm-up solutions.
- Test 6: Strict budget allocation (e.g. 150 warm-up + 350 adaptive = 500 FE).
- Test 7: Reward invariant (reward == hv_after - hv_before).
"""

import math
from pathlib import Path
import unittest

from mojssp import (
    AdaptiveExecutionResult,
    AdaptivePortfolioOrchestrator,
    BlockExecutionRecord,
    HypervolumeRewardTracker,
    MOPSOArm,
    NSGA2Arm,
    NSGA2LSArm,
    ObjectiveNormalizer,
    Portfolio,
    SlidingWindowUCB,
    compute_instance_bounds,
    load_dzn,
)


class TestNeutralWarmup(unittest.TestCase):
    """Unit and integration tests for Phase 8.3.2 neutral warm-up."""

    def setUp(self) -> None:
        toy_path = Path("data/validation/toy_instance.dzn")
        self.instance = load_dzn(toy_path, validate=True)
        self.bounds = compute_instance_bounds(self.instance)
        self.normalizer = ObjectiveNormalizer(self.bounds)
        self.seed = 42

    def _build_orchestrator(self, window_size: int = 10, pop_size: int = 10):
        seed_nsga2 = (self.seed * 10007 + 11) % (2**31 - 1)
        seed_mopso = (self.seed * 10007 + 23) % (2**31 - 1)
        seed_ls = (self.seed * 10007 + 37) % (2**31 - 1)

        arms = {
            "NSGA-II": NSGA2Arm(self.instance, population_size=pop_size, seed=seed_nsga2),
            "MOPSO": MOPSOArm(self.instance, population_size=pop_size, seed=seed_mopso),
            "NSGA-II+LS": NSGA2LSArm(self.instance, population_size=pop_size, seed=seed_ls, max_ls_iterations=5, max_ls_neighbors=5),
        }
        portfolio = Portfolio(arms)
        dmab = SlidingWindowUCB(
            arm_names=list(arms.keys()),
            window_size=window_size,
            exploration_factor=math.sqrt(2),
            seed=self.seed,
        )
        reward_tracker = HypervolumeRewardTracker(normalizer=self.normalizer)
        orchestrator = AdaptivePortfolioOrchestrator(
            portfolio=portfolio,
            dmab=dmab,
            reward_tracker=reward_tracker,
        )
        return orchestrator

    def test_1_each_arm_initialized_once(self) -> None:
        """Test 1: Each registered arm participates in warm-up exactly once."""
        orch = self._build_orchestrator()
        res = orch.run(total_budget=60, block_size=15, neutral_warmup=True)

        warmup_blocks = [r for r in res.history if r.phase == "warmup"]
        self.assertEqual(len(warmup_blocks), 3)

        warmup_arm_names = [r.arm_name for r in warmup_blocks]
        self.assertEqual(warmup_arm_names, list(orch.dmab.arm_names))

        for arm_name in orch.dmab.arm_names:
            self.assertTrue(orch.dmab.is_arm_initialized(arm_name))

    def test_2_warmup_does_not_feed_dmab(self) -> None:
        """Test 2: Warm-up rewards do not enter DMAB reward statistics."""
        orch = self._build_orchestrator()

        # Run only the warm-up blocks explicitly
        for arm_name in orch.dmab.arm_names:
            orch.run_warmup_block(arm_name, block_budget=15)

        # DMAB statistics must remain clean at 0 pulls
        self.assertEqual(orch.dmab.total_pulls, 0)
        stats = orch.dmab.get_stats()
        for arm_name in orch.dmab.arm_names:
            self.assertEqual(stats[arm_name].total_pulls, 0)
            self.assertEqual(stats[arm_name].window_pulls, 0)
            self.assertEqual(stats[arm_name].window_mean, 0.0)

    def test_3_initial_probe_guarantees_all_arms_pulled(self) -> None:
        """Test 3: Initial adaptive probe guarantees every arm is pulled once before ordinary SW-UCB."""
        dmab = SlidingWindowUCB(arm_names=["A", "B", "C"], window_size=10, seed=42)

        # Mark all arms as initialized via neutral warm-up
        dmab.mark_warmup_complete()

        # All arms are initialized, total_pulls is 0
        self.assertEqual(dmab.total_pulls, 0)
        self.assertFalse(dmab.is_initial_probe_complete)

        # First adaptive selection picks A (first unprobed arm)
        sel0 = dmab.select_arm()
        self.assertEqual(sel0, "A")
        dmab.update("A", 1.0)
        self.assertEqual(dmab.total_pulls, 1)
        self.assertEqual(dmab.get_adaptive_pulls("A"), 1)
        self.assertTrue(dmab.is_in_initial_probe("B"))

        # Second adaptive selection picks B (unprobed, despite A having reward 1.0)
        sel1 = dmab.select_arm()
        self.assertEqual(sel1, "B")
        dmab.update("B", 0.5)
        self.assertEqual(dmab.total_pulls, 2)
        self.assertEqual(dmab.get_adaptive_pulls("B"), 1)
        self.assertTrue(dmab.is_in_initial_probe("C"))

        # Third adaptive selection picks C (last unprobed arm)
        sel2 = dmab.select_arm()
        self.assertEqual(sel2, "C")
        dmab.update("C", 0.2)
        self.assertEqual(dmab.total_pulls, 3)
        self.assertTrue(dmab.is_initial_probe_complete)

        # Fourth selection: all arms probed! Ordinary SW-UCB applies.
        # Arm A has highest mean reward (1.0), so it is selected
        sel3 = dmab.select_arm()
        self.assertEqual(sel3, "A")

    def test_4_first_adaptive_reward(self) -> None:
        """Test 4: After first adaptive block, only that reward appears in DMAB stats."""
        orch = self._build_orchestrator()

        # 3 warm-up blocks (45 FE) + 1 adaptive probe block (15 FE) = 60 FE
        res = orch.run(total_budget=60, block_size=15, neutral_warmup=True)

        probe_blocks = [r for r in res.history if r.phase == "initial_probe"]
        self.assertEqual(len(probe_blocks), 1)

        # DMAB has exactly 1 update
        self.assertEqual(orch.dmab.total_pulls, 1)

        first_adaptive_arm = probe_blocks[0].arm_name
        first_adaptive_reward = probe_blocks[0].reward

        stats = orch.dmab.get_stats()
        self.assertEqual(stats[first_adaptive_arm].total_pulls, 1)
        self.assertEqual(stats[first_adaptive_arm].window_pulls, 1)
        self.assertAlmostEqual(stats[first_adaptive_arm].window_mean, first_adaptive_reward, places=9)

    def test_5_global_archive_populated_by_warmup(self) -> None:
        """Test 5: Global Archive accumulates non-dominated solutions during warm-up."""
        orch = self._build_orchestrator()

        self.assertEqual(len(orch.portfolio.global_archive), 0)

        # Run warm-up
        for arm_name in orch.dmab.arm_names:
            orch.run_warmup_block(arm_name, block_budget=15)

        # Global archive must contain solutions from warm-up
        self.assertGreater(len(orch.portfolio.global_archive), 0)
        self.assertGreater(orch.reward_tracker.current_hv, 0.0)

    def test_6_budget_strict_accounting(self) -> None:
        """Test 6: Budget accounting matches exact split between warm-up, initial probe, and adaptive phases."""
        orch = self._build_orchestrator()
        total_budget = 500
        block_size = 50

        res = orch.run(total_budget=total_budget, block_size=block_size, neutral_warmup=True)

        self.assertEqual(res.total_evaluations, total_budget)

        warmup_evals = sum(r.evaluations_used for r in res.history if r.phase == "warmup")
        probe_evals = sum(r.evaluations_used for r in res.history if r.phase == "initial_probe")
        adaptive_evals = sum(r.evaluations_used for r in res.history if r.phase == "adaptive")

        self.assertEqual(warmup_evals, 3 * block_size)  # 150 FE (3 warmup blocks)
        self.assertEqual(probe_evals, 3 * block_size)   # 150 FE (3 probe blocks)
        self.assertEqual(adaptive_evals, 4 * block_size)  # 200 FE (4 ordinary adaptive blocks)
        self.assertEqual(warmup_evals + probe_evals + adaptive_evals, total_budget)

        # Exactly 3 warm-up blocks + 3 probe blocks + 4 adaptive blocks = 10 blocks
        self.assertEqual(len([r for r in res.history if r.phase == "warmup"]), 3)
        self.assertEqual(len([r for r in res.history if r.phase == "initial_probe"]), 3)
        self.assertEqual(len([r for r in res.history if r.phase == "adaptive"]), 4)
        self.assertEqual(res.total_blocks, 10)

    def test_7_reward_invariant(self) -> None:
        """Test 7: Every block satisfies reward == hv_after - hv_before."""
        orch = self._build_orchestrator()
        res = orch.run(total_budget=100, block_size=20, neutral_warmup=True)

        for rec in res.history:
            expected_rew = rec.hv_after - rec.hv_before
            self.assertAlmostEqual(rec.reward, expected_rew, places=9)
            self.assertGreaterEqual(rec.reward, 0.0)

    def test_warmup_insufficient_budget_handling(self) -> None:
        """Test graceful handling when total_budget is insufficient for full warm-up."""
        orch = self._build_orchestrator()
        # Budget only enough for 2 of 3 arms
        res = orch.run(total_budget=25, block_size=15, neutral_warmup=True)

        self.assertLessEqual(res.total_evaluations, 25)
        # Block 0 got 15, Block 1 got 10 (truncated), Block 2 not reached
        self.assertEqual(len(res.history), 2)
        self.assertEqual(res.history[0].budget_allocated, 15)
        self.assertEqual(res.history[1].budget_allocated, 10)
        self.assertEqual(res.history[0].phase, "warmup")
        self.assertEqual(res.history[1].phase, "warmup")


if __name__ == "__main__":
    unittest.main()
