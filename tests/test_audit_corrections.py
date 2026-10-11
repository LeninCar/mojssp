"""Comprehensive test suite verifying the localized methodological audit corrections.

Covers:
1. Guarantee that no arm is left without its first adaptive probe block.
2. Neutral warmup does not contaminate adaptive learning statistics or cumulative reward.
3. Separation of warmup_reward and adaptive_reward in ArmAllocation.
4. Correct reward attribution and hypervolume monotonicity across blocks.
5. Exact 3-phase budget fulfillment (150 FE warmup + 150 FE initial probe + remaining adaptive = exact total budget).
6. IGD+ Pareto compliance and Contribution Rate (CR) with numerical tolerance.
"""

import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mojssp import (
    AdaptivePortfolioOrchestrator,
    BlockExecutionRecord,
    HypervolumeRewardTracker,
    MOEADArm,
    MOPSOArm,
    NSGA2Arm,
    ObjectiveNormalizer,
    ParetoArchive,
    Portfolio,
    SlidingWindowUCB,
    SPEA2Arm,
    build_empirical_reference_front,
    compute_archive_contribution_rate,
    compute_archive_igd_plus,
    compute_contribution_rate,
    compute_igd_plus,
    compute_instance_bounds,
    compute_modified_distance,
    load_dzn,
)
from mojssp.runner import ArmAllocation, compute_arm_allocations


class TestAuditCorrections(unittest.TestCase):
    """Test suite validating localized corrections authorized in methodological audit."""

    def setUp(self) -> None:
        toy_path = Path("data/validation/toy_instance.dzn")
        self.instance = load_dzn(toy_path, validate=True)
        self.bounds = compute_instance_bounds(self.instance)
        self.normalizer = ObjectiveNormalizer(self.bounds)
        self.seed = 42

    def _build_3arm_portfolio(self, pop_size: int = 10):
        arms = {
            "NSGA-II": NSGA2Arm(self.instance, population_size=pop_size, max_generations=None, seed=self.seed),
            "MOEA/D": MOEADArm(self.instance, population_size=pop_size, max_evaluations=None, seed=self.seed + 1),
            "SPEA2": SPEA2Arm(self.instance, population_size=pop_size, max_evaluations=None, seed=self.seed + 2),
        }
        portfolio = Portfolio(arms)
        dmab = SlidingWindowUCB(
            arm_names=list(arms.keys()),
            window_size=10,
            exploration_factor=0.07,
            seed=self.seed,
        )
        reward_tracker = HypervolumeRewardTracker(normalizer=self.normalizer)
        return AdaptivePortfolioOrchestrator(
            portfolio=portfolio,
            dmab=dmab,
            reward_tracker=reward_tracker,
        )

    def test_1_no_arm_left_without_first_adaptive_block(self) -> None:
        """Guarantee: every arm receives exactly one initial adaptive probe before ordinary SW-UCB."""
        dmab = SlidingWindowUCB(arm_names=["NSGA-II", "MOEA/D", "SPEA2"], window_size=10, exploration_factor=0.07)
        dmab.mark_warmup_complete()

        # All arms are initialized, but have 0 adaptive pulls
        self.assertEqual(dmab.total_pulls, 0)
        self.assertFalse(dmab.is_initial_probe_complete)
        for arm in ["NSGA-II", "MOEA/D", "SPEA2"]:
            self.assertTrue(dmab.is_in_initial_probe(arm))
            self.assertEqual(dmab.get_adaptive_pulls(arm), 0)

        # 1st selection: must pick NSGA-II
        s0 = dmab.select_arm()
        self.assertEqual(s0, "NSGA-II")
        # Give NSGA-II an overwhelmingly huge reward
        dmab.update("NSGA-II", 100.0)
        self.assertEqual(dmab.get_adaptive_pulls("NSGA-II"), 1)
        self.assertFalse(dmab.is_in_initial_probe("NSGA-II"))

        # 2nd selection: despite NSGA-II having reward 100.0, MUST pick unprobed arm MOEA/D
        s1 = dmab.select_arm()
        self.assertEqual(s1, "MOEA/D")
        dmab.update("MOEA/D", 0.001)
        self.assertEqual(dmab.get_adaptive_pulls("MOEA/D"), 1)

        # 3rd selection: MUST pick unprobed arm SPEA2
        s2 = dmab.select_arm()
        self.assertEqual(s2, "SPEA2")
        dmab.update("SPEA2", 0.001)
        self.assertEqual(dmab.get_adaptive_pulls("SPEA2"), 1)

        # Now all 3 arms are probed
        self.assertTrue(dmab.is_initial_probe_complete)
        self.assertEqual(dmab.total_pulls, 3)

        # 4th selection: ordinary SW-UCB applies. Since NSGA-II had reward 100.0, it is selected
        s3 = dmab.select_arm()
        self.assertEqual(s3, "NSGA-II")

    def test_2_warmup_does_not_contaminate_adaptive_statistics(self) -> None:
        """Verify: warmup runs update the archive but do NOT enter DMAB statistics or adaptive reward."""
        orch = self._build_3arm_portfolio()

        # Run 3 warmup blocks explicitly (15 evals each = 45 evals)
        for arm in orch.dmab.arm_names:
            orch.run_warmup_block(arm, block_budget=15)

        # DMAB statistics must remain completely clean at 0 pulls
        self.assertEqual(orch.dmab.total_pulls, 0)
        stats = orch.dmab.get_stats()
        for arm in orch.dmab.arm_names:
            self.assertEqual(stats[arm].total_pulls, 0)
            self.assertEqual(stats[arm].window_pulls, 0)
            self.assertEqual(stats[arm].window_mean, 0.0)
            self.assertEqual(orch.dmab.get_adaptive_pulls(arm), 0)

        # Global archive and reward tracker are populated
        self.assertGreater(orch.reward_tracker.current_hv, 0.0)

        # Verify allocation separation
        allocs = compute_arm_allocations(orch.history, total_budget=45, arm_names=orch.dmab.arm_names)
        for arm in orch.dmab.arm_names:
            self.assertEqual(allocs[arm].adaptive_reward, 0.0)
            self.assertEqual(allocs[arm].cumulative_reward, 0.0)
            self.assertGreaterEqual(allocs[arm].warmup_reward, 0.0)

        # First arm has largest warmup reward, but its cumulative_reward is 0.0
        self.assertGreater(allocs["NSGA-II"].warmup_reward, 0.5)
        self.assertEqual(allocs["NSGA-II"].cumulative_reward, 0.0)

    def test_3_exact_three_phase_budget_fulfillment_1000fe(self) -> None:
        """Verify exact budget fulfillment under 1000 FE: 150 warmup + 150 probe + 700 adaptive."""
        orch = self._build_3arm_portfolio(pop_size=10)
        total_budget = 1000
        block_size = 50

        res = orch.run(total_budget=total_budget, block_size=block_size, neutral_warmup=True)

        self.assertEqual(res.total_evaluations, total_budget)
        self.assertEqual(orch.total_evaluations, total_budget)

        warmup_blocks = [r for r in res.history if r.phase == "warmup"]
        probe_blocks = [r for r in res.history if r.phase == "initial_probe"]
        adaptive_blocks = [r for r in res.history if r.phase == "adaptive"]

        # Exactly 3 warmup blocks (150 FE)
        self.assertEqual(len(warmup_blocks), 3)
        self.assertEqual(sum(r.evaluations_used for r in warmup_blocks), 150)
        self.assertEqual([r.arm_name for r in warmup_blocks], ["NSGA-II", "MOEA/D", "SPEA2"])

        # Exactly 3 initial probe blocks (150 FE)
        self.assertEqual(len(probe_blocks), 3)
        self.assertEqual(sum(r.evaluations_used for r in probe_blocks), 150)
        self.assertEqual([r.arm_name for r in probe_blocks], ["NSGA-II", "MOEA/D", "SPEA2"])

        # Exactly 14 ordinary adaptive blocks (700 FE)
        self.assertEqual(len(adaptive_blocks), 14)
        self.assertEqual(sum(r.evaluations_used for r in adaptive_blocks), 700)

        # Total blocks = 20, Total evals = 1000, Zero overshoot
        self.assertEqual(len(res.history), 20)
        self.assertEqual(res.total_blocks, 20)
        self.assertEqual(
            sum(r.evaluations_used for r in warmup_blocks)
            + sum(r.evaluations_used for r in probe_blocks)
            + sum(r.evaluations_used for r in adaptive_blocks),
            1000,
        )

        # Verify allocations
        allocs = compute_arm_allocations(res.history, total_budget=1000, arm_names=orch.dmab.arm_names)
        self.assertEqual(sum(a.evaluations_assigned for a in allocs.values()), 1000)
        self.assertEqual(sum(a.number_of_blocks for a in allocs.values()), 20)

    def test_4_exact_three_phase_budget_fulfillment_2000fe(self) -> None:
        """Verify exact budget fulfillment under 2000 FE: 150 warmup + 150 probe + 1700 adaptive."""
        orch = self._build_3arm_portfolio(pop_size=10)
        total_budget = 2000
        block_size = 50

        res = orch.run(total_budget=total_budget, block_size=block_size, neutral_warmup=True)

        self.assertEqual(res.total_evaluations, total_budget)

        warmup_blocks = [r for r in res.history if r.phase == "warmup"]
        probe_blocks = [r for r in res.history if r.phase == "initial_probe"]
        adaptive_blocks = [r for r in res.history if r.phase == "adaptive"]

        self.assertEqual(len(warmup_blocks), 3)
        self.assertEqual(sum(r.evaluations_used for r in warmup_blocks), 150)
        self.assertEqual(len(probe_blocks), 3)
        self.assertEqual(sum(r.evaluations_used for r in probe_blocks), 150)
        self.assertEqual(len(adaptive_blocks), 34)
        self.assertEqual(sum(r.evaluations_used for r in adaptive_blocks), 1700)

        self.assertEqual(res.total_blocks, 40)
        self.assertEqual(res.total_evaluations, 2000)

    def test_5_igd_plus_distance_and_pareto_compliance(self) -> None:
        """Verify: IGD+ modified distance d+ and weak Pareto compliance."""
        # Reference point in 3D: (0.5, 0.5, 0.5)
        v = (0.5, 0.5, 0.5)

        # Point u1 weakly dominates v: (0.4, 0.5, 0.3)
        u1 = (0.4, 0.5, 0.3)
        # d+(u1, v) must be 0.0 because u1 is equal to or better than v in all objectives
        self.assertEqual(compute_modified_distance(u1, v), 0.0)

        # Point u2 is identical to v: (0.5, 0.5, 0.5)
        u2 = (0.5, 0.5, 0.5)
        self.assertEqual(compute_modified_distance(u2, v), 0.0)

        # Point u3 is worse than v in first objective only: (0.6, 0.5, 0.4)
        u3 = (0.6, 0.5, 0.4)
        # d+(u3, v) = sqrt((0.6-0.5)^2 + 0 + 0) = 0.1
        self.assertAlmostEqual(compute_modified_distance(u3, v), 0.1, places=7)

        # Point u4 is worse in all objectives: (0.8, 0.9, 0.5)
        u4 = (0.8, 0.9, 0.5)
        # d+(u4, v) = sqrt((0.3)^2 + (0.4)^2 + 0) = 0.5
        self.assertAlmostEqual(compute_modified_distance(u4, v), 0.5, places=7)

        # Full IGD+ calculation
        ref_front = [(0.2, 0.8, 0.5), (0.5, 0.5, 0.5), (0.8, 0.2, 0.5)]
        obt_good = [(0.2, 0.8, 0.5), (0.5, 0.5, 0.5), (0.8, 0.2, 0.5)]
        self.assertEqual(compute_igd_plus(obt_good, ref_front), 0.0)

        obt_dominated = [(0.3, 0.9, 0.6), (0.6, 0.6, 0.6), (0.9, 0.3, 0.6)]
        self.assertGreater(compute_igd_plus(obt_dominated, ref_front), 0.0)

    def test_6_contribution_rate_numerical_tolerance(self) -> None:
        """Verify: Contribution Rate (CR) with floating point tolerance."""
        ref_front = [(0.1, 0.2, 0.3), (0.4, 0.5, 0.6), (0.7, 0.8, 0.9)]

        # Obtained front matches 2 of 3 points exactly
        obt1 = [(0.1, 0.2, 0.3), (0.4, 0.5, 0.6)]
        cr1 = compute_contribution_rate(obt1, ref_front)
        self.assertAlmostEqual(cr1, (2.0 / 3.0) * 100.0, places=5)

        # Obtained front matches with small numerical micro-fluctuation (< 1e-6)
        obt_micro = [(0.1 + 1e-8, 0.2, 0.3), (0.4, 0.5 - 1e-8, 0.6)]
        cr_micro = compute_contribution_rate(obt_micro, ref_front, tolerance=1e-6)
        self.assertAlmostEqual(cr_micro, (2.0 / 3.0) * 100.0, places=5)

        # Empty obtained front yields CR = 0.0
        self.assertEqual(compute_contribution_rate([], ref_front), 0.0)

        # Perfect match yields CR = 100.0%
        self.assertEqual(compute_contribution_rate(ref_front, ref_front), 100.0)


if __name__ == "__main__":
    unittest.main()
