"""Unit and integration tests for MOEA/D algorithm and incremental arm (Phase 7 / Entrega B)."""

import math
from pathlib import Path
import random
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mojssp import (
    AlgorithmBlockResult,
    AlgorithmResult,
    Decoder,
    Evaluator,
    Instance,
    MOEAD,
    MOEADAdapter,
    MOEADArm,
    MOEADResult,
    ObjectiveNormalizer,
    OptimizationAlgorithm,
    ParetoArchive,
    PortfolioArm,
    ScheduleValidator,
    compute_instance_bounds,
    generate_simplex_lattice_weights,
    generate_uniform_weights,
    load_dzn,
    moead,
    tchebycheff_scalarizing,
    validate_schedule,
)
from mojssp.algorithms.moead import compute_neighborhoods


class TestMOEADComponents(unittest.TestCase):
    """Test suite for MOEA/D algorithmic components: weights, neighborhoods, Tchebycheff."""

    def setUp(self) -> None:
        toy_dzn = Path(__file__).resolve().parent.parent / "data" / "validation" / "toy_instance.dzn"
        self.instance = load_dzn(str(toy_dzn), validate=True)

    def test_simplex_lattice_weights_generation(self) -> None:
        """Verify simplex lattice generates exact Das-Dennis counts, positive weights, sum=1.0."""
        # For H=3, m=3: (3+1)*(3+2)/2 = 10 weights
        weights_h3 = generate_simplex_lattice_weights(divisions=3, num_objectives=3)
        self.assertEqual(len(weights_h3), 10)

        # For H=6: (7*8)/2 = 28 weights
        weights_h6 = generate_simplex_lattice_weights(divisions=6, num_objectives=3)
        self.assertEqual(len(weights_h6), 28)

        # For H=7: (8*9)/2 = 36 weights
        weights_h7 = generate_simplex_lattice_weights(divisions=7, num_objectives=3)
        self.assertEqual(len(weights_h7), 36)

        # Check invariants on every weight vector
        for w in weights_h6:
            self.assertEqual(len(w), 3)
            self.assertAlmostEqual(sum(w), 1.0, places=6)
            for val in w:
                self.assertGreater(val, 0.0, "Weights must be strictly positive (no zero weights)")

    def test_arbitrary_n_uniform_weights_generation(self) -> None:
        """Verify generate_uniform_weights returns requested count with high diversity."""
        for target_n in [10, 20, 30, 36, 40]:
            weights = generate_uniform_weights(num_subproblems=target_n, num_objectives=3)
            self.assertEqual(len(weights), target_n)
            for w in weights:
                self.assertEqual(len(w), 3)
                self.assertAlmostEqual(sum(w), 1.0, places=6)
                for val in w:
                    self.assertGreater(val, 0.0)

    def test_neighborhood_construction(self) -> None:
        """Verify topological neighborhoods B(i) have correct size and order."""
        weights = generate_uniform_weights(num_subproblems=20, num_objectives=3)
        t_size = 5
        neighborhoods = compute_neighborhoods(weights, neighborhood_size=t_size)

        self.assertEqual(len(neighborhoods), 20)
        for i, nb in enumerate(neighborhoods):
            self.assertEqual(len(nb), t_size)
            # The closest neighbor to weight i must be i itself (distance 0)
            self.assertEqual(nb[0], i)
            # Neighborhood indices must be unique
            self.assertEqual(len(set(nb)), t_size)
            # Distances must be non-decreasing
            dists = [math.dist(weights[i], weights[j]) for j in nb]
            for k in range(len(dists) - 1):
                self.assertLessEqual(dists[k], dists[k + 1] + 1e-9)

    def test_tchebycheff_scalarizing_behavior(self) -> None:
        """Verify Tchebycheff function behavior with respect to ideal point and weights."""
        ideal = (0.1, 0.2, 0.15)
        w = (0.5, 0.3, 0.2)

        # Point exactly matching ideal should evaluate to 0.0
        tch_zero = tchebycheff_scalarizing(ideal, w, ideal)
        self.assertEqual(tch_zero, 0.0)

        # Point farther from ideal must have strictly larger Tchebycheff value
        p_near = (0.2, 0.3, 0.25)
        p_far = (0.5, 0.6, 0.55)
        tch_near = tchebycheff_scalarizing(p_near, w, ideal)
        tch_far = tchebycheff_scalarizing(p_far, w, ideal)
        self.assertLess(tch_near, tch_far)

        # Objective with larger weight dominates scalar value
        w_skewed = (0.9, 0.05, 0.05)
        p_diff = (0.3, 0.2, 0.15)  # Delta in obj 0: 0.2 * 0.9 = 0.18
        tch_skewed = tchebycheff_scalarizing(p_diff, w_skewed, ideal)
        self.assertAlmostEqual(tch_skewed, 0.18, places=6)


class TestMOEADExecution(unittest.TestCase):
    """Test suite for MOEAD execution, feasibility, contracts, and reproducibility."""

    def setUp(self) -> None:
        toy_dzn = Path(__file__).resolve().parent.parent / "data" / "validation" / "toy_instance.dzn"
        self.instance = load_dzn(str(toy_dzn), validate=True)
        self.validator = ScheduleValidator()

    def test_moead_standalone_execution_and_schedule_feasibility(self) -> None:
        """Verify standalone MOEAD produces 100% feasible schedules and valid objectives."""
        algo = MOEAD(
            population_size=15,
            neighborhood_size=4,
            max_evaluations=60,
            seed=42,
        )
        result = algo.run(self.instance)

        self.assertIsInstance(result, MOEADResult)
        self.assertEqual(result.total_evaluations, 60)
        self.assertGreater(len(result.non_dominated_solutions), 0)
        self.assertEqual(len(result.population), 15)

        # Verify feasibility of every schedule in non-dominated set and population
        for sched in result.non_dominated_schedules:
            self.validator.validate(self.instance, sched)

        # Verify objectives validity
        for objs in result.non_dominated_objectives:
            self.assertGreaterEqual(objs.makespan, 0)
            self.assertGreaterEqual(objs.tardiness, 0)
            self.assertGreaterEqual(objs.energy, 0.0)

    def test_moead_convenience_function(self) -> None:
        """Verify moead() convenience wrapper."""
        res = moead(self.instance, population_size=10, max_evaluations=30, seed=123)
        self.assertIsInstance(res, MOEADResult)
        self.assertEqual(res.total_evaluations, 30)

    def test_moead_adapter_contract_compatibility(self) -> None:
        """Verify MOEADAdapter satisfies OptimizationAlgorithm protocol and AlgorithmResult."""
        adapter = MOEADAdapter(population_size=12, max_evaluations=40, seed=77)
        self.assertTrue(isinstance(adapter, OptimizationAlgorithm))
        self.assertEqual(adapter.algorithm_name, "MOEA/D")

        res = adapter.run(self.instance)
        self.assertIsInstance(res, AlgorithmResult)
        self.assertEqual(res.algorithm_name, "MOEA/D")
        self.assertEqual(res.total_evaluations, 40)
        self.assertEqual(res.seed, 77)
        self.assertIsInstance(res.archive, ParetoArchive)
        self.assertGreater(len(res.archive), 0)

    def test_moead_seed_bitwise_reproducibility(self) -> None:
        """Verify identical seed produces identical results bit for bit."""
        algo1 = MOEAD(population_size=12, max_evaluations=50, seed=999)
        res1 = algo1.run(self.instance)

        algo2 = MOEAD(population_size=12, max_evaluations=50, seed=999)
        res2 = algo2.run(self.instance)

        self.assertEqual(res1.total_evaluations, res2.total_evaluations)
        self.assertEqual(len(res1.archive), len(res2.archive))

        objs1 = [e.objectives.to_tuple() for e in res1.archive.entries]
        objs2 = [e.objectives.to_tuple() for e in res2.archive.entries]
        self.assertEqual(objs1, objs2)

        pop_seq1 = [s.sequence for s in res1.population]
        pop_seq2 = [s.sequence for s in res2.population]
        self.assertEqual(pop_seq1, pop_seq2)


class TestMOEADArmIncrementalExecution(unittest.TestCase):
    """Test suite for MOEADArm stateful pause/resume, exact budget, and zero overshoot."""

    def setUp(self) -> None:
        toy_dzn = Path(__file__).resolve().parent.parent / "data" / "validation" / "toy_instance.dzn"
        self.instance = load_dzn(str(toy_dzn), validate=True)

    def test_arm_protocol_and_properties(self) -> None:
        """Verify MOEADArm satisfies PortfolioArm protocol."""
        arm = MOEADArm(self.instance, population_size=15, seed=42)
        self.assertTrue(isinstance(arm, PortfolioArm))
        self.assertEqual(arm.arm_name, "MOEA/D")
        self.assertEqual(arm.total_evaluations, 0)
        self.assertFalse(arm.is_completed)

    def test_arm_exact_budget_and_zero_overshoot(self) -> None:
        """Verify arm strictly consumes budget and halts with zero overshoot."""
        arm = MOEADArm(self.instance, population_size=20, max_evaluations=100, seed=42)

        # Block 1: budget 25 (initializes 20 subproblems + 5 offspring)
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
        # Population size 20; step by arbitrary prime increments (7, 11, 13, 17)
        arm = MOEADArm(self.instance, population_size=20, max_evaluations=80, seed=55)

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
        seed = 789
        budget = 90
        pop_size = 15

        # Run 1: Single block of 90 FE
        arm_continuous = MOEADArm(
            self.instance,
            population_size=pop_size,
            max_evaluations=budget,
            seed=seed,
        )
        res_cont = arm_continuous.run(budget)

        # Run 2: Fragmented into 6 blocks of 15 FE
        arm_piecemeal = MOEADArm(
            self.instance,
            population_size=pop_size,
            max_evaluations=budget,
            seed=seed,
        )
        for _ in range(6):
            res_piece = arm_piecemeal.run(15)

        self.assertEqual(arm_continuous.total_evaluations, budget)
        self.assertEqual(arm_piecemeal.total_evaluations, budget)

        # Check identical ideal point
        self.assertEqual(arm_continuous.ideal_point, arm_piecemeal.ideal_point)

        # Check identical subproblem solutions
        cont_subs = [(s.solution.sequence, s.solution.modes) for s in arm_continuous.subproblems]
        piece_subs = [(s.solution.sequence, s.solution.modes) for s in arm_piecemeal.subproblems]
        self.assertEqual(cont_subs, piece_subs)

        # Check identical archives
        cont_objs = [e.objectives.to_tuple() for e in res_cont.solutions.entries]
        piece_objs = [e.objectives.to_tuple() for e in res_piece.solutions.entries]
        self.assertEqual(cont_objs, piece_objs)

    def test_arm_reset(self) -> None:
        """Verify arm reset clears state and reproduces exact execution."""
        arm = MOEADArm(self.instance, population_size=15, max_evaluations=50, seed=101)
        res1 = arm.run(50)

        arm.reset()
        self.assertEqual(arm.total_evaluations, 0)
        self.assertFalse(arm.is_completed)
        self.assertEqual(len(arm.subproblems), 0)
        self.assertEqual(len(arm.current_archive), 0)

        res2 = arm.run(50)
        self.assertEqual(res1.evaluations_used, res2.evaluations_used)
        objs1 = [e.objectives.to_tuple() for e in res1.solutions.entries]
        objs2 = [e.objectives.to_tuple() for e in res2.solutions.entries]
        self.assertEqual(objs1, objs2)


if __name__ == "__main__":
    unittest.main()
