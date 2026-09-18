"""Unit and integration tests for ParetoArchive and dominance module (Phase 4)."""

import sys
import unittest
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mojssp import (
    ArchiveEntry,
    Decoder,
    Instance,
    Job,
    NSGA2,
    ObjectiveValues,
    Operation,
    ParetoArchive,
    ProcessingMode,
    Schedule,
    ScheduledOperation,
    Solution,
    dominates,
    load_dzn,
)


class TestDominance(unittest.TestCase):
    """Unit tests for the common Pareto dominance function."""

    def test_a_dominates_b(self) -> None:
        a = ObjectiveValues(makespan=10, tardiness=2, energy=50.0)
        b = ObjectiveValues(makespan=12, tardiness=2, energy=55.0)
        self.assertTrue(dominates(a, b))
        self.assertFalse(dominates(b, a))

    def test_b_dominates_a(self) -> None:
        a = ObjectiveValues(makespan=15, tardiness=5, energy=80.0)
        b = ObjectiveValues(makespan=12, tardiness=3, energy=75.0)
        self.assertTrue(dominates(b, a))
        self.assertFalse(dominates(a, b))

    def test_incomparable_solutions(self) -> None:
        # Trade-off: A better in makespan, B better in energy
        a = ObjectiveValues(makespan=8, tardiness=2, energy=90.0)
        b = ObjectiveValues(makespan=12, tardiness=2, energy=50.0)
        self.assertFalse(dominates(a, b))
        self.assertFalse(dominates(b, a))

    def test_identical_objectives(self) -> None:
        # Identical objective vectors: neither dominates the other
        a = ObjectiveValues(makespan=10, tardiness=2, energy=50.0)
        b = ObjectiveValues(makespan=10, tardiness=2, energy=50.0)
        self.assertFalse(dominates(a, b))
        self.assertFalse(dominates(b, a))


class TestParetoArchive(unittest.TestCase):
    """Unit tests for ParetoArchive operations and invariants."""

    def setUp(self) -> None:
        # Helper to construct dummy valid ScheduledOperation and Schedule matching objectives
        def make_dummy_data(job_ids: tuple, modes: tuple, makespan: int, tardiness: int, energy: float):
            sol = Solution(sequence=job_ids, modes=modes)
            # Make a single scheduled op matching makespan and energy
            sched_op = ScheduledOperation(
                job_id=job_ids[0],
                op_id=0,
                machine_id=0,
                mode_id=modes[0],
                start=0,
                completion=makespan,
                duration=makespan,
                energy=energy,
            )
            sched = Schedule([sched_op])
            objs = ObjectiveValues(makespan=makespan, tardiness=tardiness, energy=energy)
            return sol, sched, objs

        self.sol_a, self.sched_a, self.obj_a = make_dummy_data((0,), (1,), 10, 2, 50.0)
        self.sol_b, self.sched_b, self.obj_b = make_dummy_data((0,), (2,), 15, 5, 80.0)  # Dominated by A
        self.sol_c, self.sched_c, self.obj_c = make_dummy_data((1,), (1,), 6, 4, 90.0)   # Incomparable with A and D
        self.sol_d, self.sched_d, self.obj_d = make_dummy_data((1,), (2,), 7, 1, 40.0)   # Dominates A, incomparable with C

        # Different genotype from A, but identical objectives to A
        self.sol_a_alt, self.sched_a_alt, self.obj_a_alt = make_dummy_data((0,), (3,), 10, 2, 50.0)

    def test_empty_archive(self) -> None:
        archive = ParetoArchive()
        self.assertTrue(archive.is_empty)
        self.assertEqual(len(archive), 0)
        self.assertEqual(archive.entries, ())
        self.assertEqual(archive.solutions, ())
        self.assertEqual(archive.schedules, ())
        self.assertEqual(archive.objectives, ())

    def test_add_first_solution(self) -> None:
        archive = ParetoArchive()
        accepted = archive.add(self.sol_a, self.sched_a, self.obj_a)
        self.assertTrue(accepted)
        self.assertFalse(archive.is_empty)
        self.assertEqual(len(archive), 1)
        self.assertIn(self.sol_a, archive)

    def test_candidate_dominated_is_discarded(self) -> None:
        archive = ParetoArchive()
        archive.add(self.sol_a, self.sched_a, self.obj_a)

        # B is dominated by A: should be rejected
        accepted_b = archive.add(self.sol_b, self.sched_b, self.obj_b)
        self.assertFalse(accepted_b)
        self.assertEqual(len(archive), 1)
        self.assertNotIn(self.sol_b, archive)

    def test_candidate_non_dominated_is_accepted(self) -> None:
        archive = ParetoArchive()
        archive.add(self.sol_a, self.sched_a, self.obj_a)

        # C is non-dominated wrt A (trade-off): should be accepted
        accepted_c = archive.add(self.sol_c, self.sched_c, self.obj_c)
        self.assertTrue(accepted_c)
        self.assertEqual(len(archive), 2)
        self.assertIn(self.sol_a, archive)
        self.assertIn(self.sol_c, archive)

    def test_candidate_dominating_existing_removes_dominated(self) -> None:
        archive = ParetoArchive()
        archive.add(self.sol_a, self.sched_a, self.obj_a)
        archive.add(self.sol_c, self.sched_c, self.obj_c)
        self.assertEqual(len(archive), 2)

        # D dominates A (7 < 10, 1 < 2, 40 < 50): adding D must accept D and remove A
        accepted_d = archive.add(self.sol_d, self.sched_d, self.obj_d)
        self.assertTrue(accepted_d)
        self.assertIn(self.sol_d, archive)
        self.assertNotIn(self.sol_a, archive)
        self.assertIn(self.sol_c, archive)
        self.assertEqual(len(archive), 2)

    def test_solutions_with_same_objectives_preserved(self) -> None:
        # Crucial requirement: different solutions with identical objective vectors
        # must both remain in the archive.
        archive = ParetoArchive()
        archive.add(self.sol_a, self.sched_a, self.obj_a)

        accepted_alt = archive.add(self.sol_a_alt, self.sched_a_alt, self.obj_a_alt)
        self.assertTrue(accepted_alt)
        self.assertEqual(len(archive), 2)
        self.assertIn(self.sol_a, archive)
        self.assertIn(self.sol_a_alt, archive)

    def test_identical_solution_genotype_not_duplicated(self) -> None:
        archive = ParetoArchive()
        archive.add(self.sol_a, self.sched_a, self.obj_a)

        # Adding exact same solution again returns False and doesn't duplicate
        accepted_duplicate = archive.add(self.sol_a, self.sched_a, self.obj_a)
        self.assertFalse(accepted_duplicate)
        self.assertEqual(len(archive), 1)

    def test_batch_update_and_successive_additions(self) -> None:
        archive = ParetoArchive()
        # Update with multiple candidates: A, B (dominated), C (non-dominated)
        count = archive.update([
            (self.sol_a, self.sched_a, self.obj_a),
            (self.sol_b, self.sched_b, self.obj_b),
            (self.sol_c, self.sched_c, self.obj_c),
        ])
        self.assertEqual(count, 2)  # A and C accepted, B rejected
        self.assertEqual(len(archive), 2)

        # Successive update adding D (which dominates A)
        count_d = archive.update([(self.sol_d, self.sched_d, self.obj_d)])
        self.assertEqual(count_d, 1)
        self.assertEqual(len(archive), 2)  # D and C remain
        self.assertEqual(set(archive.solutions), {self.sol_d, self.sol_c})

    def test_archive_entry_integrity_validation(self) -> None:
        # Mismatched makespan between schedule (10) and objectives (99)
        with self.assertRaises(ValueError):
            ArchiveEntry(
                solution=self.sol_a,
                schedule=self.sched_a,
                objectives=ObjectiveValues(makespan=99, tardiness=2, energy=50.0),
            )

        # Mismatched energy between schedule (50.0) and objectives (99.0)
        with self.assertRaises(ValueError):
            ArchiveEntry(
                solution=self.sol_a,
                schedule=self.sched_a,
                objectives=ObjectiveValues(makespan=10, tardiness=2, energy=99.0),
            )

        # Invalid type
        with self.assertRaises(TypeError):
            ArchiveEntry(solution="not_a_solution", schedule=self.sched_a, objectives=self.obj_a)  # type: ignore

    def test_archive_iteration_and_clear(self) -> None:
        archive = ParetoArchive()
        archive.add(self.sol_a, self.sched_a, self.obj_a)
        archive.add(self.sol_c, self.sched_c, self.obj_c)

        entries = list(archive)
        self.assertEqual(len(entries), 2)
        self.assertIsInstance(entries[0], ArchiveEntry)

        archive.clear()
        self.assertTrue(archive.is_empty)
        self.assertEqual(len(archive), 0)


class TestNSGA2IntegrationWithDominanceAndArchive(unittest.TestCase):
    """Integration test verifying NSGA-II compatibility with dominance and archive."""

    def test_nsga2_runs_with_common_dominance_and_feeds_archive(self) -> None:
        toy_path = Path(__file__).resolve().parent.parent / "data" / "toy_instance.dzn"
        instance = load_dzn(toy_path)

        # Run NSGA-II
        result = NSGA2(population_size=10, generations=5, seed=42).run(instance)
        self.assertGreater(len(result.non_dominated_solutions), 0)

        # Feed NSGA-II results into ParetoArchive
        archive = ParetoArchive()
        added_count = archive.update(
            list(zip(
                result.non_dominated_solutions,
                result.non_dominated_schedules,
                result.non_dominated_objectives,
            ))
        )
        self.assertGreater(added_count, 0)
        self.assertEqual(len(archive), added_count)

        # Verify all archived solutions are mutually non-dominated
        for e1 in archive.entries:
            for e2 in archive.entries:
                if e1 != e2:
                    self.assertFalse(dominates(e1.objectives, e2.objectives))


if __name__ == "__main__":
    unittest.main()
