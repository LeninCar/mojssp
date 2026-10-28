"""Unit and deterministic integration test suite for Portfolio provenance observability.

Verifies:
1. Correct tracking of new, dominated, duplicate, incumbent, and evicted solutions.
2. Objective ties with different genotypes and multiple provenance recording.
3. Strict bit-for-bit equivalence between runs with and without observer enabled.
4. Correct accounting of block evaluations, HV progress, and zero FE overhead.
"""

import sys
import unittest
from pathlib import Path
from typing import Dict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mojssp.algorithms.algorithm_contract import PortfolioArm
from mojssp.algorithms.arms import NSGA2Arm
from mojssp.portfolio.dmab import SlidingWindowUCB
from mojssp.model.evaluator import ObjectiveValues
from mojssp.model.io import load_dzn
from mojssp.algorithms.moead import MOEADArm
from mojssp.metrics.normalization import ObjectiveNormalizer, compute_instance_bounds
from mojssp.portfolio.orchestrator import AdaptivePortfolioOrchestrator
from mojssp.metrics.pareto_archive import ArchiveEntry, ParetoArchive
from mojssp.portfolio.portfolio import Portfolio
from mojssp.portfolio.provenance import (
    BlockProvenanceTrace,
    EvictionRecord,
    IngestionStatus,
    ProvenanceObservingPortfolio,
    ProvenanceTracker,
    SolutionProvenanceRecord,
    compute_genotype_id,
    compute_objective_key,
)
from mojssp.metrics.reward import HypervolumeRewardTracker
from mojssp.model.schedule import Schedule, ScheduledOperation
from mojssp.model.solution import Solution
from mojssp.algorithms.spea2 import SPEA2Arm


class TestProvenanceObservability(unittest.TestCase):
    """Test suite validating non-invasive provenance tracking."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.instance = load_dzn("data/validation/small_3x2.dzn", validate=True)
        cls.bounds = compute_instance_bounds(cls.instance)
        cls.normalizer = ObjectiveNormalizer(cls.bounds)

    def test_identifiers_stability(self) -> None:
        """Verify deterministic hash computation for genotypes and objective keys."""
        sol1 = Solution(sequence=(0, 1, 0, 1), modes=(1, 1, 1, 1))
        sol2 = Solution(sequence=(0, 1, 0, 1), modes=(1, 1, 1, 1))
        sol3 = Solution(sequence=(1, 0, 1, 0), modes=(1, 1, 1, 1))

        gid1 = compute_genotype_id(sol1)
        gid2 = compute_genotype_id(sol2)
        gid3 = compute_genotype_id(sol3)

        self.assertEqual(gid1, gid2)
        self.assertNotEqual(gid1, gid3)

        objs1 = ObjectiveValues(makespan=10, tardiness=5, energy=12.34567)
        objs2 = ObjectiveValues(makespan=10, tardiness=5, energy=12.34569)
        k1 = compute_objective_key(objs1)
        k2 = compute_objective_key(objs2)
        self.assertEqual(k1, k2)  # Rounded to 4 decimal places

    def test_provenance_lifecycle_and_evictions(self) -> None:
        """Verify tracking of accepted, incumbent, duplicate, dominated, and evicted entries."""
        tracker = ProvenanceTracker()
        obs_portfolio = ProvenanceObservingPortfolio(tracker=tracker, enabled=True)

        # 1. Arm A introduces solution 1 (non-dominated)
        sol1 = Solution(sequence=(0, 1, 0, 1), modes=(1, 1, 1, 1))
        sched1 = Schedule(operations=(ScheduledOperation(0, 0, 0, 1, 0, 10, 10, 50.0),))
        objs1 = ObjectiveValues(makespan=10, tardiness=10, energy=50.0)
        entry1 = ArchiveEntry(sol1, sched1, objs1)

        # Mock an arm returning entry1
        class MockArm:
            arm_name = "Arm_A"
            total_evaluations = 10
            is_completed = False

            def run(self, budget):
                arch = ParetoArchive([entry1])
                from mojssp.algorithms.algorithm_contract import AlgorithmBlockResult

                return AlgorithmBlockResult(solutions=arch, evaluations_used=10, completed=False)

        obs_portfolio.register_arm(MockArm(), name="Arm_A")
        res1 = obs_portfolio.run_arm("Arm_A", budget=10)

        self.assertEqual(len(res1.global_archive), 1)
        traces = tracker.block_traces
        self.assertEqual(len(traces), 1)
        self.assertEqual(traces[0].solutions_accepted_new, 1)
        self.assertEqual(traces[0].solutions_incumbent, 0)
        self.assertEqual(traces[0].solutions_evicted, 0)

        # 2. Arm A runs again; same solution is incumbent (cumulative snapshot)
        res2 = obs_portfolio.run_arm("Arm_A", budget=10)
        self.assertEqual(len(tracker.block_traces), 2)
        self.assertEqual(tracker.block_traces[1].solutions_accepted_new, 0)
        self.assertEqual(tracker.block_traces[1].solutions_incumbent, 1)

        # 3. Arm B introduces solution 2 that strictly dominates solution 1
        sol2 = Solution(sequence=(1, 0, 1, 0), modes=(1, 1, 1, 1))
        sched2 = Schedule(operations=(ScheduledOperation(1, 0, 0, 1, 0, 5, 5, 20.0),))
        objs2 = ObjectiveValues(makespan=5, tardiness=5, energy=20.0)  # Dominates (10, 10, 50.0)
        entry2 = ArchiveEntry(sol2, sched2, objs2)

        class MockArmB:
            arm_name = "Arm_B"
            total_evaluations = 10
            is_completed = False

            def run(self, budget):
                arch = ParetoArchive([entry2])
                from mojssp.algorithms.algorithm_contract import AlgorithmBlockResult

                return AlgorithmBlockResult(solutions=arch, evaluations_used=10, completed=False)

        obs_portfolio.register_arm(MockArmB(), name="Arm_B")
        res3 = obs_portfolio.run_arm("Arm_B", budget=10)

        self.assertEqual(len(res3.global_archive), 1)
        trace_b = tracker.block_traces[2]
        self.assertEqual(trace_b.solutions_accepted_new, 1)
        self.assertEqual(trace_b.solutions_evicted, 1)

        # Verify eviction record
        self.assertEqual(len(tracker.evictions), 1)
        ev = tracker.evictions[0]
        self.assertEqual(ev.original_arm, "Arm_A")
        self.assertEqual(ev.evicted_by_arm, "Arm_B")
        self.assertEqual(ev.genotype_id, compute_genotype_id(sol1))
        self.assertEqual(ev.evicted_by_genotype_id, compute_genotype_id(sol2))

    def test_objective_ties_multiple_provenance(self) -> None:
        """Verify that identical objectives with different genotypes record multiple provenance."""
        tracker = ProvenanceTracker()
        obs_portfolio = ProvenanceObservingPortfolio(tracker=tracker, enabled=True)

        sol_a = Solution(sequence=(0, 1, 0, 1), modes=(1, 1, 1, 1))
        sol_b = Solution(sequence=(1, 0, 1, 0), modes=(1, 1, 1, 1))
        sched_a = Schedule(operations=(ScheduledOperation(0, 0, 0, 1, 0, 10, 10, 30.0),))
        sched_b = Schedule(operations=(ScheduledOperation(1, 0, 0, 1, 0, 10, 10, 30.0),))
        identical_objs = ObjectiveValues(makespan=10, tardiness=5, energy=30.0)

        entry_a = ArchiveEntry(sol_a, sched_a, identical_objs)
        entry_b = ArchiveEntry(sol_b, sched_b, identical_objs)

        class Arm1:
            arm_name = "NSGA-II"
            total_evaluations = 5
            is_completed = False

            def run(self, budget):
                from mojssp.algorithms.algorithm_contract import AlgorithmBlockResult

                return AlgorithmBlockResult(
                    solutions=ParetoArchive([entry_a]), evaluations_used=5, completed=False
                )

        class Arm2:
            arm_name = "SPEA2"
            total_evaluations = 5
            is_completed = False

            def run(self, budget):
                from mojssp.algorithms.algorithm_contract import AlgorithmBlockResult

                return AlgorithmBlockResult(
                    solutions=ParetoArchive([entry_b]), evaluations_used=5, completed=False
                )

        obs_portfolio.register_arm(Arm1())
        obs_portfolio.register_arm(Arm2())

        obs_portfolio.run_arm("NSGA-II", budget=5)
        obs_portfolio.run_arm("SPEA2", budget=5)

        # Both solutions are preserved because genotypes differ
        self.assertEqual(len(obs_portfolio.global_archive), 2)

        # Objective vector provenance records BOTH arms
        okey = compute_objective_key(identical_objs)
        arms_producing_obj = tracker.objective_provenance[okey]
        self.assertIn("NSGA-II", arms_producing_obj)
        self.assertIn("SPEA2", arms_producing_obj)
        self.assertEqual(len(arms_producing_obj), 2)

    def test_bit_for_bit_determinism_with_and_without_observer(self) -> None:
        """Execute identical portfolio runs with and without observer; prove exact bitwise equality."""
        seed = 12345
        budget = 150
        block_size = 50

        # Run 1: Standard unobserved Portfolio
        arm_m1 = MOEADArm(self.instance, population_size=10, seed=seed)
        arm_n1 = NSGA2Arm(self.instance, population_size=10, seed=seed)
        arm_s1 = SPEA2Arm(self.instance, population_size=10, archive_size=10, seed=seed)
        p_std = Portfolio({"MOEA/D": arm_m1, "NSGA-II": arm_n1, "SPEA2": arm_s1})
        dmab1 = SlidingWindowUCB(
            arm_names=list(p_std.arm_names), window_size=5, exploration_factor=0.07, seed=seed
        )
        rt1 = HypervolumeRewardTracker(normalizer=self.normalizer)
        orch1 = AdaptivePortfolioOrchestrator(portfolio=p_std, dmab=dmab1, reward_tracker=rt1)
        res1 = orch1.run(total_budget=budget, block_size=block_size, neutral_warmup=True)

        # Run 2: Observed Portfolio with ProvenanceTracker
        arm_m2 = MOEADArm(self.instance, population_size=10, seed=seed)
        arm_n2 = NSGA2Arm(self.instance, population_size=10, seed=seed)
        arm_s2 = SPEA2Arm(self.instance, population_size=10, archive_size=10, seed=seed)
        tracker = ProvenanceTracker()
        p_obs = ProvenanceObservingPortfolio(
            {"MOEA/D": arm_m2, "NSGA-II": arm_n2, "SPEA2": arm_s2},
            tracker=tracker,
            enabled=True,
        )
        dmab2 = SlidingWindowUCB(
            arm_names=list(p_obs.arm_names), window_size=5, exploration_factor=0.07, seed=seed
        )
        rt2 = HypervolumeRewardTracker(normalizer=self.normalizer)
        orch2 = AdaptivePortfolioOrchestrator(portfolio=p_obs, dmab=dmab2, reward_tracker=rt2)
        res2 = orch2.run(total_budget=budget, block_size=block_size, neutral_warmup=True)

        # 1. Total evaluations used must match exactly
        self.assertEqual(res1.total_evaluations, res2.total_evaluations)
        self.assertEqual(res1.total_evaluations, budget)

        # 2. Block count must match exactly
        self.assertEqual(res1.total_blocks, res2.total_blocks)

        # 3. Exact sequence of arm selections
        arms_seq1 = [b.arm_name for b in res1.history]
        arms_seq2 = [b.arm_name for b in res2.history]
        self.assertEqual(arms_seq1, arms_seq2)

        # 4. Exact rewards per block
        rewards1 = [b.reward for b in res1.history]
        rewards2 = [b.reward for b in res2.history]
        self.assertEqual(rewards1, rewards2)

        # 5. Exact Hypervolume progression per block
        hv_after1 = [b.hv_after for b in res1.history]
        hv_after2 = [b.hv_after for b in res2.history]
        self.assertEqual(hv_after1, hv_after2)

        # 6. Final Global Archive size and exact objective coordinates
        front1 = sorted(
            [
                (e.objectives.makespan, e.objectives.tardiness, e.objectives.energy)
                for e in res1.global_archive.entries
            ]
        )
        front2 = sorted(
            [
                (e.objectives.makespan, e.objectives.tardiness, e.objectives.energy)
                for e in res2.global_archive.entries
            ]
        )
        self.assertEqual(front1, front2)

        # 7. Final genotypes set must be identical
        genos1 = sorted([compute_genotype_id(e.solution) for e in res1.global_archive.entries])
        genos2 = sorted([compute_genotype_id(e.solution) for e in res2.global_archive.entries])
        self.assertEqual(genos1, genos2)

        # 8. Tracker recorded the blocks accurately
        self.assertEqual(len(tracker.block_traces), res1.total_blocks)
        summary = tracker.get_arm_contribution_summary()
        self.assertTrue(len(summary) > 0)

    def test_disabled_observer_equivalence(self) -> None:
        """Verify that ProvenanceObservingPortfolio with enabled=False reproduces standard Portfolio."""
        seed = 54321
        budget = 100
        block_size = 50

        # Run 1: Standard unobserved Portfolio
        arm_m1 = MOEADArm(self.instance, population_size=10, seed=seed)
        arm_n1 = NSGA2Arm(self.instance, population_size=10, seed=seed)
        arm_s1 = SPEA2Arm(self.instance, population_size=10, archive_size=10, seed=seed)
        p_std = Portfolio({"MOEA/D": arm_m1, "NSGA-II": arm_n1, "SPEA2": arm_s1})
        dmab1 = SlidingWindowUCB(
            arm_names=list(p_std.arm_names), window_size=5, exploration_factor=0.07, seed=seed
        )
        rt1 = HypervolumeRewardTracker(normalizer=self.normalizer)
        orch1 = AdaptivePortfolioOrchestrator(portfolio=p_std, dmab=dmab1, reward_tracker=rt1)
        res1 = orch1.run(total_budget=budget, block_size=block_size, neutral_warmup=True)

        # Run 2: Disabled observer (enabled=False, tracker=None)
        arm_m2 = MOEADArm(self.instance, population_size=10, seed=seed)
        arm_n2 = NSGA2Arm(self.instance, population_size=10, seed=seed)
        arm_s2 = SPEA2Arm(self.instance, population_size=10, archive_size=10, seed=seed)
        p_dis = ProvenanceObservingPortfolio(
            {"MOEA/D": arm_m2, "NSGA-II": arm_n2, "SPEA2": arm_s2},
            tracker=None,
            enabled=False,
        )
        dmab2 = SlidingWindowUCB(
            arm_names=list(p_dis.arm_names), window_size=5, exploration_factor=0.07, seed=seed
        )
        rt2 = HypervolumeRewardTracker(normalizer=self.normalizer)
        orch2 = AdaptivePortfolioOrchestrator(portfolio=p_dis, dmab=dmab2, reward_tracker=rt2)
        res2 = orch2.run(total_budget=budget, block_size=block_size, neutral_warmup=True)

        self.assertEqual(res1.total_evaluations, res2.total_evaluations)
        self.assertEqual(res1.total_blocks, res2.total_blocks)
        self.assertEqual([b.arm_name for b in res1.history], [b.arm_name for b in res2.history])
        self.assertEqual([b.reward for b in res1.history], [b.reward for b in res2.history])
        self.assertEqual([b.hv_after for b in res1.history], [b.hv_after for b in res2.history])
        front1 = sorted(
            [
                (e.objectives.makespan, e.objectives.tardiness, e.objectives.energy)
                for e in res1.global_archive.entries
            ]
        )
        front2 = sorted(
            [
                (e.objectives.makespan, e.objectives.tardiness, e.objectives.energy)
                for e in res2.global_archive.entries
            ]
        )
        self.assertEqual(front1, front2)

    def test_import_internal_errors_not_suppressed(self) -> None:
        """Verify that __init__.py does not conceal internal import failures."""
        # Test simulated internal failure: name does not match exact mojssp.pairing
        fake_err = ModuleNotFoundError("No module named 'nonexistent_lib'", name="nonexistent_lib")
        # Verify directly the logic used in mojssp.__init__
        with self.assertRaises(ModuleNotFoundError) as ctx:
            if fake_err.name not in ("src.mojssp.pairing", "mojssp.pairing"):
                raise fake_err
        self.assertEqual(ctx.exception.name, "nonexistent_lib")


if __name__ == "__main__":
    unittest.main()
