"""End-to-end integration test suite for the Adaptive Portfolio (Phase 7.6).

Validates the complete closed-loop workflow:
DMAB -> select_arm() -> Portfolio.run_arm(B) -> Arm -> Global Pareto Archive
     -> ObjectiveNormalizer -> Hypervolume -> ΔHV -> DMAB.update() -> next block
using real domain implementations (no mocks) on toy_instance.dzn.
"""

from pathlib import Path
import sys
import unittest

# Add src directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

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
    dominates,
    load_dzn,
)


class TestAdaptiveIntegration(unittest.TestCase):
    """End-to-end integration tests for the full Adaptive Portfolio system."""

    def setUp(self) -> None:
        toy_path = Path(__file__).resolve().parent.parent / "data" / "validation" / "toy_instance.dzn"
        self.instance = load_dzn(toy_path)
        self.bounds = compute_instance_bounds(self.instance)
        self.normalizer = ObjectiveNormalizer(self.bounds)
        self.seed = 42

    def _create_real_pipeline(
        self,
        seed: int = 42,
        pop_size: int = 10,
        window_size: int = 5,
    ) -> AdaptivePortfolioOrchestrator:
        """Instantiate the real end-to-end pipeline with concrete arms and collaborators."""
        arm1 = NSGA2Arm(self.instance, population_size=pop_size, seed=seed)
        arm2 = MOPSOArm(self.instance, population_size=pop_size, seed=seed)
        arm3 = NSGA2LSArm(self.instance, population_size=pop_size, seed=seed)

        portfolio = Portfolio(arms=[arm1, arm2, arm3])
        dmab = SlidingWindowUCB(
            arm_names=portfolio.arm_names,
            window_size=window_size,
            seed=seed,
        )
        reward_tracker = HypervolumeRewardTracker(self.normalizer)

        return AdaptivePortfolioOrchestrator(
            portfolio=portfolio,
            dmab=dmab,
            reward_tracker=reward_tracker,
        )

    def test_full_cycle_end_to_end_pipeline(self) -> None:
        """Validation 1: Complete end-to-end execution obeys budget and records history."""
        orchestrator = self._create_real_pipeline(seed=self.seed)
        total_budget = 60
        block_size = 15

        result: AdaptiveExecutionResult = orchestrator.run(
            total_budget=total_budget,
            block_size=block_size,
        )

        # Budget constraints
        self.assertLessEqual(result.total_evaluations, total_budget)
        self.assertEqual(
            sum(rec.evaluations_used for rec in result.history),
            result.total_evaluations,
        )
        self.assertEqual(result.total_blocks, len(result.history))
        self.assertEqual(result.total_blocks, 4)

        # Verify all three arms were selected (warm-up guarantees first 3 blocks)
        selected_arms = [rec.arm_name for rec in result.history]
        self.assertIn("NSGA-II", selected_arms[:3])
        self.assertIn("MOPSO", selected_arms[:3])
        self.assertIn("NSGA-II+LS", selected_arms[:3])

        # Global Archive populated
        self.assertGreater(len(result.global_archive), 0)

    def test_block_traceability_and_reward_coherence(self) -> None:
        """Validation 2: Every block record satisfies HV_before + reward == HV_after within tolerance."""
        orchestrator = self._create_real_pipeline(seed=self.seed)
        result = orchestrator.run(total_budget=60, block_size=15)

        for i, rec in enumerate(result.history):
            self.assertEqual(rec.block_index, i)
            self.assertIn(rec.arm_name, orchestrator.portfolio.arm_names)
            self.assertEqual(rec.budget_allocated, 15)
            self.assertGreater(rec.evaluations_used, 0)
            self.assertLessEqual(rec.evaluations_used, rec.budget_allocated)

            # Continuity between records
            if i == 0:
                self.assertEqual(rec.hv_before, 0.0)
            else:
                self.assertEqual(rec.hv_before, result.history[i - 1].hv_after)

            # Mathematical coherence: HV_before + reward == HV_after
            self.assertAlmostEqual(
                rec.hv_before + rec.reward,
                rec.hv_after,
                places=9,
                msg=f"Block {i} failed HV_before + reward == HV_after",
            )

    def test_hypervolume_monotonicity_across_blocks(self) -> None:
        """Validation 3: Hypervolume is strictly monotonic non-decreasing across all blocks."""
        orchestrator = self._create_real_pipeline(seed=self.seed)
        result = orchestrator.run(total_budget=75, block_size=15)

        prev_hv = 0.0
        for rec in result.history:
            self.assertGreaterEqual(
                rec.hv_after,
                prev_hv - 1e-12,
                msg=f"Monotonicity violated at block {rec.block_index}",
            )
            self.assertGreaterEqual(rec.reward, 0.0)
            self.assertAlmostEqual(rec.reward, rec.hv_after - prev_hv, places=9)
            prev_hv = rec.hv_after

    def test_global_archive_accumulation_and_non_dominance(self) -> None:
        """Validation 4: Global Archive accumulates non-dominated solutions across multiple arms."""
        orchestrator = self._create_real_pipeline(seed=self.seed)
        result = orchestrator.run(total_budget=60, block_size=15)

        global_archive = result.global_archive
        self.assertGreater(len(global_archive), 0)

        # Check pairwise non-dominance in the global archive
        entries = list(global_archive.entries)
        for i in range(len(entries)):
            for j in range(len(entries)):
                if i != j:
                    self.assertFalse(
                        dominates(entries[i].objectives, entries[j].objectives),
                        f"Entry {i} dominates entry {j} in Global Archive!",
                    )

        # Check genotype uniqueness (no duplicate solutions)
        seen_genotypes = set()
        for entry in entries:
            key = (entry.solution.sequence, entry.solution.modes)
            self.assertNotIn(key, seen_genotypes)
            seen_genotypes.add(key)

    def test_arm_continuity_across_multiple_blocks(self) -> None:
        """Validation 5: Arms continue evolution across multiple block invocations."""
        orchestrator = self._create_real_pipeline(seed=self.seed)
        # Run 6 blocks of 15 evals (total 90 evals)
        result = orchestrator.run(total_budget=90, block_size=15)

        # Verify that arm evaluations accumulated across blocks match arm.total_evaluations
        evals_by_arm = {}
        for rec in result.history:
            evals_by_arm[rec.arm_name] = evals_by_arm.get(rec.arm_name, 0) + rec.evaluations_used

        for arm_name, total_used in evals_by_arm.items():
            arm = orchestrator.portfolio.get_arm(arm_name)
            self.assertEqual(arm.total_evaluations, total_used)

    def test_dmab_update_count_matches_block_count(self) -> None:
        """Validation 6: Exactly one DMAB update occurs per executed block when neutral_warmup=False."""
        orchestrator = self._create_real_pipeline(seed=self.seed)
        result = orchestrator.run(total_budget=60, block_size=15, neutral_warmup=False)

        # Total pulls matches block count
        self.assertEqual(orchestrator.dmab.total_pulls, result.total_blocks)

        # Per-arm pulls in DMAB match arm occurrences in history
        stats = orchestrator.dmab.get_stats()
        for arm_name in orchestrator.portfolio.arm_names:
            expected_pulls = sum(1 for rec in result.history if rec.arm_name == arm_name)
            self.assertEqual(stats[arm_name].total_pulls, expected_pulls)

    def test_neutral_warmup_end_to_end_behavior(self) -> None:
        """Validation 8: Neutral warm-up isolates initialization rewards from DMAB learning."""
        orchestrator = self._create_real_pipeline(seed=self.seed)
        result = orchestrator.run(total_budget=60, block_size=15, neutral_warmup=True)

        self.assertEqual(result.total_blocks, 4)
        warmup_recs = [r for r in result.history if r.phase == "warmup"]
        adaptive_recs = [r for r in result.history if r.phase in ("initial_probe", "adaptive")]

        self.assertEqual(len(warmup_recs), 3)
        self.assertEqual(len(adaptive_recs), 1)
        self.assertEqual(adaptive_recs[0].phase, "initial_probe")

        # DMAB learning statistics only reflect adaptive blocks
        self.assertEqual(orchestrator.dmab.total_pulls, 1)
        active_arm = adaptive_recs[0].arm_name
        stats = orchestrator.dmab.get_stats()
        self.assertEqual(stats[active_arm].total_pulls, 1)
        for arm in orchestrator.portfolio.arm_names:
            if arm != active_arm:
                self.assertEqual(stats[arm].total_pulls, 0)

    def test_reproducibility_deterministic_pipeline(self) -> None:
        """Validation 7: Same instance, seeds, budget, and block size yield identical trajectory."""
        orch1 = self._create_real_pipeline(seed=12345)
        orch2 = self._create_real_pipeline(seed=12345)

        res1 = orch1.run(total_budget=60, block_size=15)
        res2 = orch2.run(total_budget=60, block_size=15)

        self.assertEqual(res1.total_blocks, res2.total_blocks)
        self.assertEqual(res1.total_evaluations, res2.total_evaluations)

        for rec1, rec2 in zip(res1.history, res2.history):
            self.assertEqual(rec1.block_index, rec2.block_index)
            self.assertEqual(rec1.arm_name, rec2.arm_name)
            self.assertEqual(rec1.budget_allocated, rec2.budget_allocated)
            self.assertEqual(rec1.evaluations_used, rec2.evaluations_used)
            self.assertAlmostEqual(rec1.reward, rec2.reward, places=9)
            self.assertAlmostEqual(rec1.hv_before, rec2.hv_before, places=9)
            self.assertAlmostEqual(rec1.hv_after, rec2.hv_after, places=9)
            self.assertEqual(rec1.completed, rec2.completed)

        # Final archives identical
        self.assertEqual(len(res1.global_archive), len(res2.global_archive))
        objs1 = sorted([e.objectives.to_tuple() for e in res1.global_archive.entries])
        objs2 = sorted([e.objectives.to_tuple() for e in res2.global_archive.entries])
        self.assertEqual(objs1, objs2)

    def test_partial_budget_truncation(self) -> None:
        """Validation 8: Non-multiple budget (e.g. 47 with block_size=15) allocates 15, 15, 15, 2."""
        orchestrator = self._create_real_pipeline(seed=self.seed)
        total_budget = 47
        block_size = 15

        result = orchestrator.run(total_budget=total_budget, block_size=block_size)

        self.assertLessEqual(result.total_evaluations, total_budget)
        allocated = [rec.budget_allocated for rec in result.history]
        self.assertEqual(allocated, [15, 15, 15, 2])
        self.assertEqual(sum(rec.evaluations_used for rec in result.history), result.total_evaluations)

    def test_early_termination_when_arms_complete(self) -> None:
        """Validation 9: Clean termination without infinite loop if all arms complete early."""
        # NSGA-II and NSGA-II+LS configured with max_generations=1, MOPSO with max_iterations=1
        arm1 = NSGA2Arm(self.instance, population_size=10, max_generations=1, seed=self.seed)
        arm2 = MOPSOArm(self.instance, population_size=10, max_evaluations=20, seed=self.seed)
        arm3 = NSGA2LSArm(self.instance, population_size=10, max_generations=1, seed=self.seed)

        portfolio = Portfolio(arms=[arm1, arm2, arm3])
        dmab = SlidingWindowUCB(arm_names=portfolio.arm_names, seed=self.seed)
        tracker = HypervolumeRewardTracker(self.normalizer)
        orchestrator = AdaptivePortfolioOrchestrator(portfolio, dmab, tracker)

        # Run with large budget (5000), but arms only have ~1 generation each
        result = orchestrator.run(total_budget=5000, block_size=50)

        # Must terminate cleanly and consume significantly less than 5000 evals
        self.assertLess(result.total_evaluations, 5000)
        self.assertTrue(all(arm.is_completed for arm in portfolio.arms.values()))


if __name__ == "__main__":
    unittest.main()
