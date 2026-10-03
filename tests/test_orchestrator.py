"""Unit and integration tests for AdaptivePortfolioOrchestrator (Phase 7.5)."""

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
    load_dzn,
)


class TestOrchestrator(unittest.TestCase):
    """Test suite for AdaptivePortfolioOrchestrator."""

    def setUp(self) -> None:
        toy_path = Path(__file__).resolve().parent.parent / "data" / "validation" / "toy_instance.dzn"
        self.instance = load_dzn(toy_path)
        self.bounds = compute_instance_bounds(self.instance)
        self.normalizer = ObjectiveNormalizer(self.bounds)
        self.seed = 42

    def _build_test_orchestrator(
        self,
        pop_size: int = 10,
        window_size: int = 5,
        seed: int = 42,
    ) -> AdaptivePortfolioOrchestrator:
        """Helper to create a wired AdaptivePortfolioOrchestrator with all 3 arms."""
        arm1 = NSGA2Arm(self.instance, population_size=pop_size, seed=seed)
        arm2 = MOPSOArm(self.instance, population_size=pop_size, seed=seed)
        arm3 = NSGA2LSArm(self.instance, population_size=pop_size, seed=seed)

        portfolio = Portfolio(arms=[arm1, arm2, arm3])
        dmab = SlidingWindowUCB(arm_names=portfolio.arm_names, window_size=window_size, seed=seed)
        reward_tracker = HypervolumeRewardTracker(self.normalizer)

        return AdaptivePortfolioOrchestrator(
            portfolio=portfolio,
            dmab=dmab,
            reward_tracker=reward_tracker,
        )

    def test_full_flow_single_step(self) -> None:
        """Test A: Single step flows through DMAB -> Portfolio -> Arm -> Archive -> Reward -> DMAB."""
        orchestrator = self._build_test_orchestrator()

        self.assertEqual(orchestrator.total_evaluations, 0)
        self.assertEqual(orchestrator.dmab.total_pulls, 0)

        record = orchestrator.step(block_budget=15)

        self.assertIsInstance(record, BlockExecutionRecord)
        self.assertEqual(record.block_index, 0)
        self.assertIn(record.arm_name, orchestrator.portfolio.arm_names)
        self.assertLessEqual(record.evaluations_used, 15)
        self.assertGreater(record.evaluations_used, 0)
        self.assertGreaterEqual(record.reward, 0.0)

        # DMAB updated
        self.assertEqual(orchestrator.dmab.total_pulls, 1)

        # Portfolio updated
        self.assertEqual(orchestrator.total_evaluations, record.evaluations_used)
        self.assertGreater(len(orchestrator.portfolio.global_archive), 0)

        # History recorded
        self.assertEqual(len(orchestrator.history), 1)
        self.assertEqual(orchestrator.history[0], record)

    def test_budget_strict_enforcement(self) -> None:
        """Test B: Cumulative evaluations never exceed total_budget across blocks."""
        orchestrator = self._build_test_orchestrator()
        total_budget = 47
        block_size = 15

        res: AdaptiveExecutionResult = orchestrator.run(
            total_budget=total_budget, block_size=block_size
        )

        self.assertLessEqual(res.total_evaluations, total_budget)
        self.assertEqual(orchestrator.total_evaluations, res.total_evaluations)
        self.assertGreater(res.total_evaluations, 0)

    def test_last_block_budget_truncation(self) -> None:
        """Test C: If remaining < block_size, final block receives exactly remaining budget."""
        orchestrator = self._build_test_orchestrator()
        total_budget = 25
        block_size = 10

        res = orchestrator.run(total_budget=total_budget, block_size=block_size)

        # Should execute blocks of sizes 10, 10, and 5 (or fewer if completed)
        allocated_budgets = [r.budget_allocated for r in res.history]
        self.assertEqual(allocated_budgets[0], 10)
        self.assertEqual(allocated_budgets[1], 10)
        self.assertEqual(allocated_budgets[2], 5)

        for rec in res.history:
            self.assertLessEqual(rec.evaluations_used, rec.budget_allocated)

    def test_real_evaluations_accounting(self) -> None:
        """Test D: Total evaluations is exact sum of real evaluations consumed."""
        orchestrator = self._build_test_orchestrator()
        res = orchestrator.run(total_budget=60, block_size=20)

        sum_evals = sum(rec.evaluations_used for rec in res.history)
        self.assertEqual(res.total_evaluations, sum_evals)
        self.assertEqual(orchestrator.total_evaluations, sum_evals)

    def test_dmab_receives_reward_each_block(self) -> None:
        """Test E: DMAB total_pulls increments exactly once per block executed when neutral_warmup=False."""
        orchestrator = self._build_test_orchestrator()
        res = orchestrator.run(total_budget=50, block_size=15, neutral_warmup=False)

        self.assertEqual(orchestrator.dmab.total_pulls, res.total_blocks)
        self.assertEqual(len(res.history), res.total_blocks)

    def test_neutral_warmup_pipeline(self) -> None:
        """Test: Neutral warm-up executes each arm once without feeding DMAB rewards."""
        orchestrator = self._build_test_orchestrator()
        total_budget = 60
        block_size = 15

        res = orchestrator.run(total_budget=total_budget, block_size=block_size, neutral_warmup=True)

        self.assertEqual(res.total_blocks, 4)
        warmup_records = [r for r in res.history if r.phase == "warmup"]
        adaptive_records = [r for r in res.history if r.phase == "adaptive"]

        self.assertEqual(len(warmup_records), 3)
        self.assertEqual(len(adaptive_records), 1)
        self.assertEqual(
            [r.arm_name for r in warmup_records],
            list(orchestrator.dmab.arm_names),
        )
        self.assertEqual(orchestrator.dmab.total_pulls, 1)

    def test_persistent_state_across_blocks(self) -> None:
        """Test F: Stateful algorithm arms continue their internal evolution across blocks."""
        orchestrator = self._build_test_orchestrator()

        # Step twice on the portfolio
        rec1 = orchestrator.step(block_budget=15)
        arm1 = orchestrator.portfolio.get_arm(rec1.arm_name)
        evals_after_first = arm1.total_evaluations

        rec2 = orchestrator.step(block_budget=15)
        # Verify total evals on portfolio equals sum of steps
        self.assertEqual(
            orchestrator.total_evaluations, rec1.evaluations_used + rec2.evaluations_used
        )

    def test_global_archive_accumulation(self) -> None:
        """Test G: Global Pareto Archive accumulates non-dominated solutions across blocks."""
        orchestrator = self._build_test_orchestrator()
        res = orchestrator.run(total_budget=60, block_size=15)

        self.assertGreater(len(res.global_archive), 0)
        # Hypervolume is monotonic non-decreasing across history
        hv_values = [rec.hv_after for rec in res.history]
        for i in range(len(hv_values) - 1):
            self.assertLessEqual(hv_values[i], hv_values[i + 1])

    def test_reproducibility(self) -> None:
        """Test H: Same instance, seeds, budget, and block size yield identical execution trajectory."""
        orch1 = self._build_test_orchestrator(seed=999)
        orch2 = self._build_test_orchestrator(seed=999)

        res1 = orch1.run(total_budget=45, block_size=15)
        res2 = orch2.run(total_budget=45, block_size=15)

        self.assertEqual(res1.total_blocks, res2.total_blocks)
        self.assertEqual(res1.total_evaluations, res2.total_evaluations)

        for rec1, rec2 in zip(res1.history, res2.history):
            self.assertEqual(rec1.arm_name, rec2.arm_name)
            self.assertEqual(rec1.budget_allocated, rec2.budget_allocated)
            self.assertEqual(rec1.evaluations_used, rec2.evaluations_used)
            self.assertAlmostEqual(rec1.reward, rec2.reward, places=9)
            self.assertAlmostEqual(rec1.hv_after, rec2.hv_after, places=9)

    def test_reset(self) -> None:
        """Test reset restores all collaborator states and allows identical re-execution."""
        orch = self._build_test_orchestrator(seed=123)
        res1 = orch.run(total_budget=30, block_size=10)

        orch.reset()
        self.assertEqual(orch.total_evaluations, 0)
        self.assertEqual(orch.dmab.total_pulls, 0)
        self.assertEqual(orch.reward_tracker.current_hv, 0.0)
        self.assertEqual(len(orch.history), 0)

        res2 = orch.run(total_budget=30, block_size=10)
        self.assertEqual(res1.total_blocks, res2.total_blocks)
        self.assertEqual(res1.total_evaluations, res2.total_evaluations)
        for r1, r2 in zip(res1.history, res2.history):
            self.assertEqual(r1.arm_name, r2.arm_name)
            self.assertEqual(r1.evaluations_used, r2.evaluations_used)
            self.assertAlmostEqual(r1.reward, r2.reward, places=9)

    def test_validation(self) -> None:
        """Test validation of constructor and run parameters."""
        orch = self._build_test_orchestrator()

        with self.assertRaises(ValueError):
            orch.step(block_budget=0)
        with self.assertRaises(ValueError):
            orch.step(block_budget=-10)

        with self.assertRaises(ValueError):
            orch.run(total_budget=0, block_size=10)
        with self.assertRaises(ValueError):
            orch.run(total_budget=50, block_size=0)


if __name__ == "__main__":
    unittest.main()
