"""Multi-instance smoke test suite for MO-JSSP arms and adaptive portfolio (Phase 7.7).

Validates that NSGA2Arm, MOPSOArm, NSGA2LSArm, and AdaptivePortfolioOrchestrator
operate consistently across multiple problem instances of varying dimensions without
instance-specific coupling or regressions.
"""

from pathlib import Path
import sys
import unittest

# Add src directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mojssp import (
    AdaptivePortfolioOrchestrator,
    AlgorithmBlockResult,
    HypervolumeRewardTracker,
    Instance,
    MOPSOArm,
    NSGA2Arm,
    NSGA2LSArm,
    ObjectiveNormalizer,
    Portfolio,
    PortfolioArm,
    SlidingWindowUCB,
    compute_instance_bounds,
    decode,
    dominates,
    load_dzn,
    validate_schedule,
)


class TestSmokeMultiInstance(unittest.TestCase):
    """Smoke test suite across multiple instances (toy_instance, small_3x2, small_3x3)."""

    def setUp(self) -> None:
        data_dir = Path(__file__).resolve().parent.parent / "data"
        self.instance_files = [
            ("toy_instance", data_dir / "validation" / "toy_instance.dzn"),
            ("small_3x2", data_dir / "validation" / "small_3x2.dzn"),
            ("small_3x3", data_dir / "validation" / "small_3x3.dzn"),
        ]
        self.instances = {
            name: load_dzn(path, validate=True)
            for name, path in self.instance_files
        }
        self.arm_classes = [NSGA2Arm, MOPSOArm, NSGA2LSArm]
        self.seed = 42

    def test_instances_loading_and_bounds(self) -> None:
        """Smoke 1: All instances load with valid dimensions and positive bounds."""
        for name, inst in self.instances.items():
            with self.subTest(instance=name):
                self.assertGreater(inst.num_jobs, 0)
                self.assertGreater(inst.num_machines, 0)
                self.assertGreater(inst.total_operations, 0)

                bounds = compute_instance_bounds(inst)
                self.assertGreater(bounds.cmax_max, bounds.cmax_min)
                self.assertGreaterEqual(bounds.tardiness_max, bounds.tardiness_min)
                self.assertGreater(bounds.energy_max, bounds.energy_min)

    def test_individual_arms_execution_and_validity(self) -> None:
        """Smoke 2: Each Arm executes cleanly and yields valid feasible schedules on every instance."""
        budget = 20
        for inst_name, inst in self.instances.items():
            for ArmCls in self.arm_classes:
                with self.subTest(instance=inst_name, arm=ArmCls.__name__):
                    arm = ArmCls(inst, population_size=10, seed=self.seed)
                    self.assertIsInstance(arm, PortfolioArm)

                    result: AlgorithmBlockResult = arm.run(budget=budget)
                    self.assertIsInstance(result, AlgorithmBlockResult)
                    self.assertLessEqual(result.evaluations_used, budget)
                    self.assertGreater(result.evaluations_used, 0)
                    self.assertEqual(arm.total_evaluations, result.evaluations_used)

                    # Validate that returned solutions decode into valid feasible schedules
                    archive = result.solutions
                    self.assertGreater(len(archive), 0)
                    for entry in archive.entries:
                        sched = decode(inst, entry.solution)
                        errors = validate_schedule(inst, sched)
                        self.assertEqual(
                            errors,
                            [],
                            f"Invalid schedule for {inst_name} {arm.arm_name}: {errors}",
                        )

    def test_individual_arms_reproducibility(self) -> None:
        """Smoke 3: Each Arm reproduces exact evaluations and solutions with same seed across instances."""
        budget = 25
        for inst_name, inst in self.instances.items():
            for ArmCls in self.arm_classes:
                with self.subTest(instance=inst_name, arm=ArmCls.__name__):
                    arm1 = ArmCls(inst, population_size=10, seed=self.seed)
                    res1 = arm1.run(budget=budget)

                    arm2 = ArmCls(inst, population_size=10, seed=self.seed)
                    res2 = arm2.run(budget=budget)

                    self.assertEqual(res1.evaluations_used, res2.evaluations_used)
                    self.assertEqual(res1.completed, res2.completed)
                    self.assertEqual(len(res1.solutions), len(res2.solutions))

                    objs1 = sorted(e.objectives.to_tuple() for e in res1.solutions.entries)
                    objs2 = sorted(e.objectives.to_tuple() for e in res2.solutions.entries)
                    self.assertEqual(objs1, objs2)

    def test_adaptive_pipeline_multi_instance(self) -> None:
        """Smoke 4: Adaptive orchestrator executes seamlessly across all instances."""
        total_budget = 45
        block_size = 15

        for inst_name, inst in self.instances.items():
            with self.subTest(instance=inst_name):
                bounds = compute_instance_bounds(inst)
                normalizer = ObjectiveNormalizer(bounds)

                arms = [
                    NSGA2Arm(inst, population_size=10, seed=self.seed),
                    MOPSOArm(inst, population_size=10, seed=self.seed),
                    NSGA2LSArm(inst, population_size=10, seed=self.seed),
                ]
                portfolio = Portfolio(arms=arms)
                dmab = SlidingWindowUCB(portfolio.arm_names, window_size=5, seed=self.seed)
                tracker = HypervolumeRewardTracker(normalizer)
                orchestrator = AdaptivePortfolioOrchestrator(portfolio, dmab, tracker)

                res = orchestrator.run(total_budget=total_budget, block_size=block_size)

                # 1. Budget enforcement & accounting
                self.assertLessEqual(res.total_evaluations, total_budget)
                self.assertEqual(
                    sum(rec.evaluations_used for rec in res.history),
                    res.total_evaluations,
                )

                # 2. Block validation
                for rec in res.history:
                    self.assertLessEqual(rec.evaluations_used, rec.budget_allocated)
                    self.assertAlmostEqual(
                        rec.hv_before + rec.reward,
                        rec.hv_after,
                        places=9,
                    )
                    self.assertGreaterEqual(rec.hv_after, rec.hv_before - 1e-12)
                    self.assertGreaterEqual(rec.reward, 0.0)

                # 3. DMAB update count matches adaptive blocks
                self.assertEqual(
                    dmab.total_pulls,
                    sum(1 for rec in res.history if rec.phase == "adaptive"),
                )

                # 4. Global Archive properties
                archive = res.global_archive
                self.assertGreater(len(archive), 0)
                entries = list(archive.entries)
                # Pairwise non-dominance
                for i in range(len(entries)):
                    for j in range(len(entries)):
                        if i != j:
                            self.assertFalse(
                                dominates(entries[i].objectives, entries[j].objectives)
                            )
                # Unique genotypes
                seen = set()
                for e in entries:
                    key = (e.solution.sequence, e.solution.modes)
                    self.assertNotIn(key, seen)
                    seen.add(key)

    def test_adaptive_pipeline_reproducibility(self) -> None:
        """Smoke 5: Adaptive orchestrator produces bitwise identical trajectories on multiple runs."""
        total_budget = 45
        block_size = 15

        for inst_name, inst in self.instances.items():
            with self.subTest(instance=inst_name):
                bounds = compute_instance_bounds(inst)

                def _run_orch():
                    norm = ObjectiveNormalizer(bounds)
                    p = Portfolio([
                        NSGA2Arm(inst, population_size=10, seed=777),
                        MOPSOArm(inst, population_size=10, seed=777),
                        NSGA2LSArm(inst, population_size=10, seed=777),
                    ])
                    d = SlidingWindowUCB(p.arm_names, window_size=5, seed=777)
                    t = HypervolumeRewardTracker(norm)
                    o = AdaptivePortfolioOrchestrator(p, d, t)
                    return o.run(total_budget=total_budget, block_size=block_size)

                res1 = _run_orch()
                res2 = _run_orch()

                self.assertEqual(res1.total_evaluations, res2.total_evaluations)
                self.assertEqual(res1.total_blocks, res2.total_blocks)
                for r1, r2 in zip(res1.history, res2.history):
                    self.assertEqual(r1.arm_name, r2.arm_name)
                    self.assertEqual(r1.evaluations_used, r2.evaluations_used)
                    self.assertAlmostEqual(r1.reward, r2.reward, places=9)
                    self.assertAlmostEqual(r1.hv_before, r2.hv_before, places=9)
                    self.assertAlmostEqual(r1.hv_after, r2.hv_after, places=9)

    def test_adaptive_pipeline_partial_budget(self) -> None:
        """Smoke 6: Partial budgets are correctly allocated across instances."""
        total_budget = 37
        block_size = 15

        for inst_name, inst in self.instances.items():
            with self.subTest(instance=inst_name):
                bounds = compute_instance_bounds(inst)
                norm = ObjectiveNormalizer(bounds)
                p = Portfolio([
                    NSGA2Arm(inst, population_size=10, seed=self.seed),
                    MOPSOArm(inst, population_size=10, seed=self.seed),
                    NSGA2LSArm(inst, population_size=10, seed=self.seed),
                ])
                d = SlidingWindowUCB(p.arm_names, seed=self.seed)
                t = HypervolumeRewardTracker(norm)
                o = AdaptivePortfolioOrchestrator(p, d, t)

                res = o.run(total_budget=total_budget, block_size=block_size)

                self.assertLessEqual(res.total_evaluations, total_budget)
                allocated = [rec.budget_allocated for rec in res.history]
                self.assertEqual(allocated, [15, 15, 7])


if __name__ == "__main__":
    unittest.main()
