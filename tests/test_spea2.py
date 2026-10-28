"""Unit and integration tests for SPEA2 algorithm and incremental arm (Phase 7 / Entrega C)."""

import math
from pathlib import Path
import random
import sys
from typing import Tuple
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mojssp import (
    AlgorithmBlockResult,
    AlgorithmResult,
    Decoder,
    Evaluator,
    Instance,
    ObjectiveNormalizer,
    ObjectiveValues,
    OptimizationAlgorithm,
    ParetoArchive,
    PortfolioArm,
    Schedule,
    ScheduleValidator,
    Solution,
    SPEA2,
    SPEA2Adapter,
    SPEA2Arm,
    SPEA2Result,
    calculate_spea2_fitness,
    environmental_selection,
    load_dzn,
    spea2,
    validate_schedule,
)
from mojssp.algorithms.spea2 import SPEA2Individual, truncate_archive


class TestSPEA2Components(unittest.TestCase):
    """Test suite for SPEA2 fitness assignment, density estimation, and truncation."""

    def setUp(self) -> None:
        toy_dzn = Path(__file__).resolve().parent.parent / "data" / "validation" / "toy_instance.dzn"
        self.instance = load_dzn(str(toy_dzn), validate=True)
        self.decoder = Decoder()
        self.evaluator = Evaluator()

    def _make_dummy_individual(
        self, cmax: int, tardiness: int, energy: float, norm: Tuple[float, float, float]
    ) -> SPEA2Individual:
        sol = Solution.random(self.instance)
        sched = self.decoder.decode(self.instance, sol)
        objs = ObjectiveValues(makespan=cmax, tardiness=tardiness, energy=energy)
        return SPEA2Individual(
            solution=sol,
            schedule=sched,
            objectives=objs,
            normalized_objectives=norm,
        )

    def test_strength_and_raw_fitness_calculation(self) -> None:
        """Verify S(i) and R(i) calculation on a known dominance hierarchy."""
        # A dominates B and C; D is mutually non-dominated with A; E is dominated by all
        # A: (10, 10, 10.0) -> dominates B(20, 20, 20.0), C(20, 15, 20.0), E(30, 30, 30.0)
        # D: (5, 30, 10.0) -> mutually non-dominated with A, dominates E(30, 30, 30.0)
        ind_a = self._make_dummy_individual(10, 10, 10.0, (0.1, 0.1, 0.1))
        ind_b = self._make_dummy_individual(20, 20, 20.0, (0.3, 0.3, 0.3))
        ind_c = self._make_dummy_individual(20, 15, 20.0, (0.3, 0.2, 0.3))
        ind_d = self._make_dummy_individual(5, 30, 10.0, (0.05, 0.5, 0.1))
        ind_e = self._make_dummy_individual(30, 30, 30.0, (0.6, 0.6, 0.6))

        pop = [ind_a, ind_b, ind_c, ind_d, ind_e]
        calculate_spea2_fitness(pop)

        # Strength S:
        # A dominates B, C, E -> S(A) = 3
        # C dominates B, E -> S(C) = 2
        # B dominates E -> S(B) = 1
        # D dominates E -> S(D) = 1
        # E dominates nobody -> S(E) = 0
        self.assertEqual(ind_a.strength, 3)
        self.assertEqual(ind_c.strength, 2)
        self.assertEqual(ind_b.strength, 1)
        self.assertEqual(ind_d.strength, 1)
        self.assertEqual(ind_e.strength, 0)

        # Raw Fitness R:
        # A is dominated by nobody -> R(A) = 0
        # D is dominated by nobody -> R(D) = 0
        # Non-dominated individuals MUST have raw_fitness == 0.0
        self.assertEqual(ind_a.raw_fitness, 0.0)
        self.assertEqual(ind_d.raw_fitness, 0.0)

        # C is dominated by A -> R(C) = S(A) = 3
        self.assertEqual(ind_c.raw_fitness, 3.0)
        # B is dominated by A and C -> R(B) = S(A) + S(C) = 3 + 2 = 5
        self.assertEqual(ind_b.raw_fitness, 5.0)
        # E is dominated by A, B, C, D -> R(E) = S(A) + S(B) + S(C) + S(D) = 3 + 1 + 2 + 1 = 7
        self.assertEqual(ind_e.raw_fitness, 7.0)

        # Total fitness F = R + D:
        # For non-dominated A and D: F < 1.0 (since R=0 and 0 < D < 1)
        self.assertLess(ind_a.fitness, 1.0)
        self.assertLess(ind_d.fitness, 1.0)
        # For dominated B, C, E: F >= 1.0
        self.assertGreaterEqual(ind_b.fitness, 1.0)
        self.assertGreaterEqual(ind_e.fitness, 1.0)

    def test_density_estimation_kth_nearest_neighbor(self) -> None:
        """Verify density D(i) decreases as distance to k-th neighbor increases."""
        # 3 non-dominated individuals with different crowding
        # ind1 is crowded near ind2, ind3 is isolated
        ind1 = self._make_dummy_individual(10, 20, 30.0, (0.10, 0.20, 0.30))
        ind2 = self._make_dummy_individual(11, 20, 29.0, (0.11, 0.20, 0.29))  # very close to ind1
        ind3 = self._make_dummy_individual(50, 10, 10.0, (0.80, 0.10, 0.10))  # far away

        pop = [ind1, ind2, ind3]
        calculate_spea2_fitness(pop)

        # Crowded ind1 and ind2 have smaller k-th dist, hence higher density D
        # Isolated ind3 has larger k-th dist, hence smaller density D
        self.assertGreater(ind1.density, ind3.density)
        self.assertGreater(ind2.density, ind3.density)

    def test_environmental_selection_exact_and_suboverflow(self) -> None:
        """Verify environmental selection when non-dominated count <= archive_size."""
        # 2 non-dominated, 2 dominated
        ind_nd1 = self._make_dummy_individual(10, 10, 10.0, (0.1, 0.1, 0.1))
        ind_nd2 = self._make_dummy_individual(5, 20, 10.0, (0.05, 0.2, 0.1))
        ind_dom1 = self._make_dummy_individual(15, 15, 15.0, (0.2, 0.2, 0.2))
        ind_dom2 = self._make_dummy_individual(30, 30, 30.0, (0.5, 0.5, 0.5))

        pop = [ind_nd1, ind_nd2, ind_dom1, ind_dom2]
        calculate_spea2_fitness(pop)

        # Target size 2: exact match of non-dominated
        sel_2 = environmental_selection(pop, archive_size=2)
        self.assertEqual(len(sel_2), 2)
        self.assertIn(ind_nd1, sel_2)
        self.assertIn(ind_nd2, sel_2)

        # Target size 3: suboverflow -> fills with best dominated (ind_dom1)
        sel_3 = environmental_selection(pop, archive_size=3)
        self.assertEqual(len(sel_3), 3)
        self.assertIn(ind_nd1, sel_3)
        self.assertIn(ind_nd2, sel_3)
        self.assertIn(ind_dom1, sel_3)

    def test_deterministic_truncation_overflow(self) -> None:
        """Verify deterministic truncation removes most crowded individuals while preserving extremes."""
        # 4 non-dominated individuals on trade-off curve:
        # e1: extreme (0.0, 1.0, 0.0)
        # p1: crowded (0.30, 0.70, 0.0)
        # p2: crowded (0.31, 0.69, 0.0) - very close to p1
        # e2: extreme (1.0, 0.0, 0.0)
        e1 = self._make_dummy_individual(10, 100, 10.0, (0.0, 1.0, 0.0))
        p1 = self._make_dummy_individual(30, 70, 10.0, (0.30, 0.70, 0.0))
        p2 = self._make_dummy_individual(31, 69, 10.0, (0.31, 0.69, 0.0))
        e2 = self._make_dummy_individual(100, 10, 10.0, (1.0, 0.0, 0.0))

        candidates = [e1, p1, p2, e2]
        for c in candidates:
            c.raw_fitness = 0.0

        # Truncate from 4 to 3: should remove one of the crowded pair (p1 or p2), never e1 or e2
        truncated = truncate_archive(candidates, target_size=3)
        self.assertEqual(len(truncated), 3)
        self.assertIn(e1, truncated, "Extremes must be preserved")
        self.assertIn(e2, truncated, "Extremes must be preserved")
        # Exactly one of p1 or p2 should be kept
        self.assertTrue(
            (p1 in truncated and p2 not in truncated) or (p2 in truncated and p1 not in truncated)
        )


class TestSPEA2Execution(unittest.TestCase):
    """Test suite for SPEA2 standalone execution, schedule feasibility, and reproducibility."""

    def setUp(self) -> None:
        toy_dzn = Path(__file__).resolve().parent.parent / "data" / "validation" / "toy_instance.dzn"
        self.instance = load_dzn(str(toy_dzn), validate=True)
        self.validator = ScheduleValidator()

    def test_spea2_standalone_execution_and_schedule_feasibility(self) -> None:
        """Verify standalone SPEA2 produces 100% feasible schedules and valid criteria."""
        algo = SPEA2(
            population_size=12,
            archive_size=12,
            max_evaluations=50,
            seed=42,
        )
        result = algo.run(self.instance)

        self.assertIsInstance(result, SPEA2Result)
        self.assertEqual(result.total_evaluations, 50)
        self.assertGreater(len(result.non_dominated_solutions), 0)
        self.assertEqual(len(result.population), 12)
        self.assertEqual(len(result.archive_population), 12)

        # Audit feasibility of all non-dominated schedules and populations
        for sched in result.non_dominated_schedules:
            self.validator.validate(self.instance, sched)

        for objs in result.non_dominated_objectives:
            self.assertGreaterEqual(objs.makespan, 0)
            self.assertGreaterEqual(objs.tardiness, 0)
            self.assertGreaterEqual(objs.energy, 0.0)

    def test_spea2_convenience_function(self) -> None:
        """Verify spea2() convenience wrapper."""
        res = spea2(self.instance, population_size=10, archive_size=10, max_evaluations=30, seed=123)
        self.assertIsInstance(res, SPEA2Result)
        self.assertEqual(res.total_evaluations, 30)

    def test_spea2_adapter_contract_compatibility(self) -> None:
        """Verify SPEA2Adapter satisfies OptimizationAlgorithm protocol and AlgorithmResult."""
        adapter = SPEA2Adapter(population_size=10, archive_size=10, max_evaluations=35, seed=88)
        self.assertTrue(isinstance(adapter, OptimizationAlgorithm))
        self.assertEqual(adapter.algorithm_name, "SPEA2")

        res = adapter.run(self.instance)
        self.assertIsInstance(res, AlgorithmResult)
        self.assertEqual(res.algorithm_name, "SPEA2")
        self.assertEqual(res.total_evaluations, 35)
        self.assertEqual(res.seed, 88)
        self.assertIsInstance(res.archive, ParetoArchive)
        self.assertGreater(len(res.archive), 0)

    def test_spea2_seed_bitwise_reproducibility(self) -> None:
        """Verify identical seed produces identical results bit for bit."""
        algo1 = SPEA2(population_size=12, archive_size=12, max_evaluations=45, seed=777)
        res1 = algo1.run(self.instance)

        algo2 = SPEA2(population_size=12, archive_size=12, max_evaluations=45, seed=777)
        res2 = algo2.run(self.instance)

        self.assertEqual(res1.total_evaluations, res2.total_evaluations)
        self.assertEqual(len(res1.archive), len(res2.archive))

        objs1 = [e.objectives.to_tuple() for e in res1.archive.entries]
        objs2 = [e.objectives.to_tuple() for e in res2.archive.entries]
        self.assertEqual(objs1, objs2)

        pop_seq1 = [s.sequence for s in res1.population]
        pop_seq2 = [s.sequence for s in res2.population]
        self.assertEqual(pop_seq1, pop_seq2)


class TestSPEA2ArmIncrementalExecution(unittest.TestCase):
    """Test suite for SPEA2Arm stateful pause/resume, exact budget, and zero overshoot."""

    def setUp(self) -> None:
        toy_dzn = Path(__file__).resolve().parent.parent / "data" / "validation" / "toy_instance.dzn"
        self.instance = load_dzn(str(toy_dzn), validate=True)

    def test_arm_protocol_and_properties(self) -> None:
        """Verify SPEA2Arm satisfies PortfolioArm protocol."""
        arm = SPEA2Arm(self.instance, population_size=15, archive_size=15, seed=42)
        self.assertTrue(isinstance(arm, PortfolioArm))
        self.assertEqual(arm.arm_name, "SPEA2")
        self.assertEqual(arm.total_evaluations, 0)
        self.assertFalse(arm.is_completed)

    def test_arm_exact_budget_and_zero_overshoot(self) -> None:
        """Verify arm strictly consumes budget and halts with zero overshoot."""
        arm = SPEA2Arm(self.instance, population_size=20, archive_size=20, max_evaluations=100, seed=42)

        # Block 1: budget 25 (initializes 20 P0 + 5 offspring)
        res1 = arm.run(25)
        self.assertEqual(res1.evaluations_used, 25)
        self.assertEqual(arm.total_evaluations, 25)
        self.assertFalse(res1.completed)

        # Block 2: budget 50
        res2 = arm.run(50)
        self.assertEqual(res2.evaluations_used, 50)
        self.assertEqual(arm.total_evaluations, 75)
        self.assertFalse(res2.completed)

        # Block 3: budget 50 (only 25 remaining until max_evaluations=100)
        res3 = arm.run(50)
        self.assertEqual(res3.evaluations_used, 25)
        self.assertEqual(arm.total_evaluations, 100)
        self.assertTrue(res3.completed)
        self.assertTrue(arm.is_completed)

        # Block 4: call after completion
        res4 = arm.run(50)
        self.assertEqual(res4.evaluations_used, 0)
        self.assertTrue(res4.completed)

    def test_sub_generation_budget_cuts(self) -> None:
        """Verify arm pauses cleanly when budget is less than a single generation."""
        arm = SPEA2Arm(self.instance, population_size=20, archive_size=20, max_evaluations=80, seed=55)

        increments = [7, 11, 13, 17, 20, 12]  # sum = 80
        total_accum = 0

        for inc in increments:
            res = arm.run(inc)
            total_accum += res.evaluations_used
            self.assertEqual(arm.total_evaluations, total_accum)
            self.assertEqual(res.evaluations_used, inc)

        self.assertEqual(arm.total_evaluations, 80)
        self.assertTrue(arm.is_completed)

    def test_trajectory_continuity_identical_to_uninterrupted(self) -> None:
        """Verify piecemeal execution produces exact bit-for-bit results as single-shot."""
        seed = 987
        budget = 90
        pop_size = 15

        # Run 1: Single block of 90 FE
        arm_continuous = SPEA2Arm(
            self.instance,
            population_size=pop_size,
            archive_size=pop_size,
            max_evaluations=budget,
            seed=seed,
        )
        res_cont = arm_continuous.run(budget)

        # Run 2: Fragmented into 6 blocks of 15 FE
        arm_piecemeal = SPEA2Arm(
            self.instance,
            population_size=pop_size,
            archive_size=pop_size,
            max_evaluations=budget,
            seed=seed,
        )
        for _ in range(6):
            res_piece = arm_piecemeal.run(15)

        self.assertEqual(arm_continuous.total_evaluations, budget)
        self.assertEqual(arm_piecemeal.total_evaluations, budget)

        # Check identical population solutions
        cont_pop = [(s.solution.sequence, s.solution.modes) for s in arm_continuous.population]
        piece_pop = [(s.solution.sequence, s.solution.modes) for s in arm_piecemeal.population]
        self.assertEqual(cont_pop, piece_pop)

        # Check identical environmental archives
        cont_arch = [(s.solution.sequence, s.solution.modes) for s in arm_continuous.archive_population]
        piece_arch = [(s.solution.sequence, s.solution.modes) for s in arm_piecemeal.archive_population]
        self.assertEqual(cont_arch, piece_arch)

        # Check identical external archives
        cont_objs = [e.objectives.to_tuple() for e in res_cont.solutions.entries]
        piece_objs = [e.objectives.to_tuple() for e in res_piece.solutions.entries]
        self.assertEqual(cont_objs, piece_objs)

    def test_arm_reset(self) -> None:
        """Verify arm reset clears state and reproduces exact execution."""
        arm = SPEA2Arm(self.instance, population_size=15, archive_size=15, max_evaluations=50, seed=202)
        res1 = arm.run(50)

        arm.reset()
        self.assertEqual(arm.total_evaluations, 0)
        self.assertFalse(arm.is_completed)
        self.assertEqual(len(arm.population), 0)
        self.assertEqual(len(arm.archive_population), 0)
        self.assertEqual(len(arm.current_archive), 0)

        res2 = arm.run(50)
        self.assertEqual(res1.evaluations_used, res2.evaluations_used)
        objs1 = [e.objectives.to_tuple() for e in res1.solutions.entries]
        objs2 = [e.objectives.to_tuple() for e in res2.solutions.entries]
        self.assertEqual(objs1, objs2)


if __name__ == "__main__":
    unittest.main()
