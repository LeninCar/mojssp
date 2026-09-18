"""Unit and integration tests for NSGA-II on MO-JSSP."""

import random
import sys
import unittest
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mojssp import (
    Decoder,
    Evaluator,
    Instance,
    Job,
    NSGA2,
    ObjectiveValues,
    Operation,
    ProcessingMode,
    Schedule,
    ScheduledOperation,
    Solution,
    load_dzn,
    nsga2,
    validate_schedule,
)
from mojssp.nsga2 import (
    Individual,
    binary_tournament,
    calculate_crowding_distance,
    crossover_pox,
    dominates,
    fast_non_dominated_sort,
    mutate_modes_per_gene,
    mutate_sequence_swap,
)


class TestNSGA2Components(unittest.TestCase):
    """Test suite for individual components of NSGA-II."""

    def setUp(self) -> None:
        toy_path = Path(__file__).resolve().parent.parent / "data" / "toy_instance.dzn"
        self.instance = load_dzn(toy_path)
        self.dummy_sol = Solution(sequence=(1, 2, 1, 2), modes=(1, 1, 1, 1))
        self.dummy_sched = Decoder().decode(self.instance, self.dummy_sol)

    def test_pareto_dominance(self) -> None:
        # A dominates B: all <= and at least one <
        a = ObjectiveValues(makespan=10, tardiness=2, energy=15.0)
        b = ObjectiveValues(makespan=12, tardiness=2, energy=16.0)
        self.assertTrue(dominates(a, b))
        self.assertFalse(dominates(b, a))

        # Incomparable: trade-off between makespan and energy
        c = ObjectiveValues(makespan=9, tardiness=5, energy=20.0)
        d = ObjectiveValues(makespan=11, tardiness=2, energy=12.0)
        self.assertFalse(dominates(c, d))
        self.assertFalse(dominates(d, c))

        # Identical: neither dominates the other
        e = ObjectiveValues(makespan=10, tardiness=2, energy=15.0)
        self.assertFalse(dominates(a, e))
        self.assertFalse(dominates(e, a))

    def test_fast_non_dominated_sort(self) -> None:
        # Create individuals with known dominance
        # ind1: (10, 2, 10) - non-dominated (F1)
        # ind2: (8, 4, 12)  - non-dominated (F1)
        # ind3: (12, 5, 15) - dominated by both ind1 and ind2 (F2)
        # ind4: (15, 8, 20) - dominated by ind3 (F3)
        ind1 = Individual(self.dummy_sol, self.dummy_sched, ObjectiveValues(10, 2, 10.0))
        ind2 = Individual(self.dummy_sol, self.dummy_sched, ObjectiveValues(8, 4, 12.0))
        ind3 = Individual(self.dummy_sol, self.dummy_sched, ObjectiveValues(12, 5, 15.0))
        ind4 = Individual(self.dummy_sol, self.dummy_sched, ObjectiveValues(15, 8, 20.0))

        fronts = fast_non_dominated_sort([ind1, ind2, ind3, ind4])

        self.assertEqual(len(fronts), 3)
        self.assertEqual(set(fronts[0]), {ind1, ind2})
        self.assertEqual(fronts[1], [ind3])
        self.assertEqual(fronts[2], [ind4])

        self.assertEqual(ind1.rank, 1)
        self.assertEqual(ind2.rank, 1)
        self.assertEqual(ind3.rank, 2)
        self.assertEqual(ind4.rank, 3)

    def test_crowding_distance_assignment(self) -> None:
        ind1 = Individual(self.dummy_sol, self.dummy_sched, ObjectiveValues(5, 1, 10.0))
        ind2 = Individual(self.dummy_sol, self.dummy_sched, ObjectiveValues(10, 2, 8.0))
        ind3 = Individual(self.dummy_sol, self.dummy_sched, ObjectiveValues(15, 3, 6.0))

        front = [ind1, ind2, ind3]
        calculate_crowding_distance(front)

        # Boundaries must have infinite crowding distance
        self.assertEqual(ind1.crowding_distance, float("inf"))
        self.assertEqual(ind3.crowding_distance, float("inf"))
        # Internal point must have finite positive crowding distance
        self.assertGreater(ind2.crowding_distance, 0.0)
        self.assertNotEqual(ind2.crowding_distance, float("inf"))

    def test_crowding_distance_identical_points(self) -> None:
        # All points have identical objectives -> span is 0, no division by zero
        ind1 = Individual(self.dummy_sol, self.dummy_sched, ObjectiveValues(10, 2, 5.0))
        ind2 = Individual(self.dummy_sol, self.dummy_sched, ObjectiveValues(10, 2, 5.0))
        ind3 = Individual(self.dummy_sol, self.dummy_sched, ObjectiveValues(10, 2, 5.0))

        front = [ind1, ind2, ind3]
        calculate_crowding_distance(front)
        # Extremes get inf, middle gets 0.0 without raising ZeroDivisionError
        self.assertEqual(ind1.crowding_distance, float("inf"))
        self.assertEqual(ind3.crowding_distance, float("inf"))

    def test_binary_tournament_selection(self) -> None:
        rng = random.Random(42)
        p1 = Individual(self.dummy_sol, self.dummy_sched, ObjectiveValues(10, 2, 10.0), rank=1, crowding_distance=0.5)
        p2 = Individual(self.dummy_sol, self.dummy_sched, ObjectiveValues(12, 3, 12.0), rank=2, crowding_distance=0.9)

        # Lower rank wins
        winner = binary_tournament(p1, p2, rng)
        self.assertIs(winner, p1)

        # Same rank: higher crowding distance wins
        p3 = Individual(self.dummy_sol, self.dummy_sched, ObjectiveValues(10, 2, 10.0), rank=1, crowding_distance=0.8)
        winner2 = binary_tournament(p1, p3, rng)
        self.assertIs(winner2, p3)

    def test_crossover_pox_preserves_validity(self) -> None:
        rng = random.Random(99)
        p1 = Solution(sequence=(1, 1, 2, 2), modes=(1, 1, 2, 2))
        p2 = Solution(sequence=(2, 1, 2, 1), modes=(2, 2, 1, 1))

        c1, c2 = crossover_pox(p1, p2, self.instance, rng)

        # Both children must validate successfully against instance
        c1.validate_with_instance(self.instance)
        c2.validate_with_instance(self.instance)

        # Check job appearance frequencies: job 1 twice, job 2 twice
        self.assertEqual(c1.sequence.count(1), 2)
        self.assertEqual(c1.sequence.count(2), 2)
        self.assertEqual(c2.sequence.count(1), 2)
        self.assertEqual(c2.sequence.count(2), 2)

    def test_mutate_sequence_swap_preserves_frequencies(self) -> None:
        rng = random.Random(123)
        sol = Solution(sequence=(1, 2, 1, 2), modes=(1, 1, 1, 1))
        mutated = mutate_sequence_swap(sol, rng)

        self.assertEqual(mutated.sequence.count(1), 2)
        self.assertEqual(mutated.sequence.count(2), 2)
        mutated.validate_with_instance(self.instance)

    def test_mutate_modes_per_gene(self) -> None:
        rng = random.Random(456)
        sol = Solution(sequence=(1, 2, 1, 2), modes=(1, 1, 1, 1))
        # With p=1.0, any gene with >1 modes must be mutated to a valid alternative
        mutated = mutate_modes_per_gene(sol, self.instance, p_mut_mode=1.0, rng=rng)

        mutated.validate_with_instance(self.instance)
        for op, mode_id in zip(self.instance.all_operations, mutated.modes):
            self.assertIn(mode_id, op.mode_ids)


class TestNSGA2Execution(unittest.TestCase):
    """Integration and execution tests for the complete NSGA-II algorithm."""

    def setUp(self) -> None:
        toy_path = Path(__file__).resolve().parent.parent / "data" / "toy_instance.dzn"
        self.instance = load_dzn(toy_path)

    def test_full_run_and_population_size(self) -> None:
        pop_size = 12
        generations = 5
        result = nsga2(
            self.instance,
            population_size=pop_size,
            generations=generations,
            seed=42,
        )

        self.assertEqual(len(result.population), pop_size)
        self.assertEqual(len(result.population_objectives), pop_size)
        self.assertGreater(len(result.non_dominated_solutions), 0)
        self.assertEqual(
            len(result.non_dominated_solutions),
            len(result.non_dominated_schedules),
        )
        self.assertEqual(
            len(result.non_dominated_solutions),
            len(result.non_dominated_objectives),
        )

    def test_deterministic_reproducibility(self) -> None:
        # Same seed must yield identical results
        res1 = nsga2(self.instance, population_size=10, generations=4, seed=777)
        res2 = nsga2(self.instance, population_size=10, generations=4, seed=777)

        self.assertEqual(
            [s.sequence for s in res1.non_dominated_solutions],
            [s.sequence for s in res2.non_dominated_solutions],
        )
        self.assertEqual(
            [s.modes for s in res1.non_dominated_solutions],
            [s.modes for s in res2.non_dominated_solutions],
        )
        self.assertEqual(
            [o.to_tuple() for o in res1.non_dominated_objectives],
            [o.to_tuple() for o in res2.non_dominated_objectives],
        )

    def test_all_non_dominated_schedules_pass_validator(self) -> None:
        result = nsga2(self.instance, population_size=16, generations=6, seed=123)

        for sched in result.non_dominated_schedules:
            errors = validate_schedule(self.instance, sched)
            self.assertEqual(errors, [])

    def test_non_dominated_objectives_validity(self) -> None:
        result = nsga2(self.instance, population_size=10, generations=4, seed=42)

        for obj in result.non_dominated_objectives:
            self.assertGreater(obj.makespan, 0)
            self.assertGreaterEqual(obj.tardiness, 0)
            self.assertGreater(obj.energy, 0.0)

    def test_parameter_validations(self) -> None:
        with self.assertRaises(ValueError):
            NSGA2(population_size=2)  # must be >= 4
        with self.assertRaises(ValueError):
            NSGA2(generations=0)  # must be >= 1
        with self.assertRaises(ValueError):
            NSGA2(crossover_probability=1.5)
        with self.assertRaises(ValueError):
            NSGA2(mutation_sequence_probability=-0.1)


if __name__ == "__main__":
    unittest.main()

