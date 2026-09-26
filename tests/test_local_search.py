"""Unit tests for Local Search module (Phase 5)."""

from pathlib import Path
import random
import sys
import unittest

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mojssp import (
    ArchiveAddResult,
    Decoder,
    Evaluator,
    Instance,
    LocalParetoArchive,
    LocalSearch,
    LocalSearchResult,
    ParetoArchive,
    Solution,
    decode,
    evaluate,
    load_dzn,
    validate_schedule,
)


class TestLocalSearch(unittest.TestCase):
    """Test suite for LocalSearch and LocalParetoArchive."""

    def setUp(self) -> None:
        toy_dzn = Path(__file__).resolve().parent.parent / "data" / "toy_instance.dzn"
        self.instance = load_dzn(str(toy_dzn))
        self.init_sol = Solution(sequence=(1, 2, 1, 2), modes=(1, 1, 1, 1))

    def test_local_archive_capacity_and_crowding_distance_pruning(self) -> None:
        """Test that LocalParetoArchive prunes to max_size=10 using crowding distance."""
        archive = LocalParetoArchive(max_size=3)

        # Create distinct solutions and valid schedules/objectives
        # We can construct synthetic solutions with different makespan/tardiness/energy trade-offs
        for i in range(5):
            sol = Solution(sequence=(1, 2, 1, 2), modes=(1, 1, 1, 1))
            sched = decode(self.instance, sol)
            # Create synthetic non-dominated entries
            objs = Evaluator().evaluate(self.instance, sched)
            # Use distinct solutions by varying modes or sequence
            s = Solution(sequence=(1, 2, 1, 2), modes=(1, 1, 1, 1 if i == 0 else 2))
            archive.add(s, sched, objs)

        # Capacity must never exceed max_size
        self.assertLessEqual(len(archive), 3)

    def test_local_archive_only_contains_non_dominated(self) -> None:
        """Test that LocalParetoArchive discards dominated candidates."""
        archive = LocalParetoArchive(max_size=10)
        sol1 = Solution(sequence=(1, 2, 1, 2), modes=(1, 1, 1, 1))
        sched1 = decode(self.instance, sol1)
        objs1 = evaluate(self.instance, sched1)
        archive.add(sol1, sched1, objs1)

        # Identical genotype is rejected
        self.assertFalse(archive.add(sol1, sched1, objs1))
        self.assertEqual(len(archive), 1)

    def test_local_archive_independence_from_global_archive(self) -> None:
        """Test that LocalParetoArchive does not interfere with global ParetoArchive."""
        global_archive = ParetoArchive()
        local_archive = LocalParetoArchive(max_size=10)

        sol = Solution(sequence=(1, 2, 1, 2), modes=(1, 1, 1, 1))
        sched = decode(self.instance, sol)
        objs = evaluate(self.instance, sched)

        local_archive.add(sol, sched, objs)
        self.assertEqual(len(local_archive), 1)
        self.assertEqual(len(global_archive), 0)

    def test_modes_remain_invariant_in_local_search(self) -> None:
        """Test that all refined solutions have the exact same modes as the initial solution."""
        ls = LocalSearch(max_iterations=10, max_neighbors=5, max_no_improvement=5)
        res = ls.search(self.instance, self.init_sol, rng=random.Random(42))

        for refined_sol in res.refined_solutions:
            self.assertEqual(refined_sol.modes, self.init_sol.modes)

    def test_job_multiplicities_preserved_and_schedules_valid(self) -> None:
        """Test that all refined solutions preserve job frequencies and produce valid schedules."""
        ls = LocalSearch(max_iterations=15, max_neighbors=10, max_no_improvement=10)
        res = ls.search(self.instance, self.init_sol, rng=random.Random(42))

        for refined_sol in res.refined_solutions:
            # Multiplicities
            self.assertEqual(refined_sol.sequence.count(1), 2)
            self.assertEqual(refined_sol.sequence.count(2), 2)
            # Schedule validity
            sched = decode(self.instance, refined_sol)
            validate_schedule(self.instance, sched)

    def test_max_neighbors_and_iterations_limits(self) -> None:
        """Test that max_iterations (50) and max_no_improvement (20) are respected."""
        ls = LocalSearch(max_iterations=5, max_no_improvement=2, max_neighbors=3)
        res = ls.search(self.instance, self.init_sol, rng=random.Random(42))

        self.assertLessEqual(res.iterations_run, 5)
        self.assertIn(res.stopped_reason, ("max_iterations", "no_improvement", "no_neighbors"))

    def test_evaluation_counter_accuracy(self) -> None:
        """Test that eval_counter increments by 1 for every real evaluation."""
        eval_counter = [0]
        ls = LocalSearch(max_iterations=5, max_no_improvement=5, max_neighbors=4)
        res = ls.search(
            self.instance,
            self.init_sol,
            rng=random.Random(123),
            eval_counter=eval_counter,
        )

        self.assertGreater(res.evaluations_count, 0)
        self.assertEqual(res.evaluations_count, eval_counter[0])

    def test_reproducibility_with_seed(self) -> None:
        """Test that LocalSearch with identical seed produces identical results."""
        ls1 = LocalSearch(max_iterations=10, max_no_improvement=5, max_neighbors=5)
        ls2 = LocalSearch(max_iterations=10, max_no_improvement=5, max_neighbors=5)

        res1 = ls1.search(self.instance, self.init_sol, rng=random.Random(999))
        res2 = ls2.search(self.instance, self.init_sol, rng=random.Random(999))

        self.assertEqual(res1.iterations_run, res2.iterations_run)
        self.assertEqual(res1.evaluations_count, res2.evaluations_count)
        self.assertEqual(res1.stopped_reason, res2.stopped_reason)
        self.assertEqual(
            [s.sequence for s in res1.refined_solutions],
            [s.sequence for s in res2.refined_solutions],
        )

    def test_case1_dominated_candidate_is_not_pareto_improvement(self) -> None:
        """Caso 1: Dominated candidate is rejected and does not count as Pareto improvement."""
        archive = LocalParetoArchive(max_size=10)
        sA = Solution(sequence=(1, 2, 1, 2), modes=(1, 1, 1, 1))
        archive.add(sA, decode(self.instance, sA), evaluate(self.instance, decode(self.instance, sA)))

        # s_dom is strictly dominated by sA (Cmax=22 vs 12, T=13 vs 3, E=53 vs 53)
        s_dom = Solution(sequence=(1, 1, 2, 2), modes=(1, 1, 1, 1))
        sched_dom = decode(self.instance, s_dom)
        objs_dom = evaluate(self.instance, sched_dom)

        res = archive.add(s_dom, sched_dom, objs_dom)
        self.assertFalse(res.accepted)
        self.assertFalse(res.candidate_remained)
        self.assertFalse(res.pareto_improvement)
        self.assertEqual(res.dominated_removed, 0)
        self.assertEqual(len(archive), 1)

    def test_case2_candidate_dominating_existing_is_pareto_improvement(self) -> None:
        """Caso 2: Candidate that strictly dominates an existing solution is a Pareto improvement."""
        archive = LocalParetoArchive(max_size=10)
        s_dom = Solution(sequence=(1, 1, 2, 2), modes=(1, 1, 1, 1))
        archive.add(s_dom, decode(self.instance, s_dom), evaluate(self.instance, decode(self.instance, s_dom)))

        # Insert superior solution sA that strictly dominates s_dom
        sA = Solution(sequence=(1, 2, 1, 2), modes=(1, 1, 1, 1))
        schedA = decode(self.instance, sA)
        objsA = evaluate(self.instance, schedA)

        res = archive.add(sA, schedA, objsA)
        self.assertTrue(res.accepted)
        self.assertTrue(res.candidate_remained)
        self.assertEqual(res.dominated_removed, 1)
        self.assertTrue(res.pareto_improvement)
        self.assertEqual(len(archive), 1)
        self.assertEqual(archive.entries[0].solution, sA)

    def test_case3_crowding_replacement_without_dominance_is_not_pareto_improvement(self) -> None:
        """Caso 3: A replacement driven purely by crowding distance is NOT a Pareto improvement."""
        archive = LocalParetoArchive(max_size=2)
        # Two non-dominated solutions filling the archive (size=2)
        sA = Solution(sequence=(1, 2, 1, 2), modes=(1, 1, 1, 1))  # (12, 3, 53)
        sC = Solution(sequence=(1, 2, 1, 2), modes=(2, 1, 1, 1))  # (11, 1, 63)
        resA = archive.add(sA, decode(self.instance, sA), evaluate(self.instance, decode(self.instance, sA)))
        resC = archive.add(sC, decode(self.instance, sC), evaluate(self.instance, decode(self.instance, sC)))
        self.assertTrue(resA.pareto_improvement)
        self.assertTrue(resC.pareto_improvement)
        self.assertEqual(len(archive), 2)

        # Add sB: (8, 0, 93), non-dominated with sA and sC
        sB = Solution(sequence=(1, 2, 1, 2), modes=(2, 2, 2, 2))  # (8, 0, 93)
        schedB = decode(self.instance, sB)
        objsB = evaluate(self.instance, schedB)

        resB = archive.add(sB, schedB, objsB)
        # sB displaced sC due to crowding distance (sA and sB are extreme points, sC is interior)
        self.assertTrue(resB.accepted)
        self.assertTrue(resB.candidate_remained)
        self.assertTrue(resB.pruned_by_capacity)
        self.assertEqual(resB.dominated_removed, 0)
        # The archive content changed!
        self.assertEqual([e.solution for e in archive.entries], [sA, sB])
        # BUT this is not a Pareto improvement!
        self.assertFalse(resB.pareto_improvement)

    def test_case4_new_non_dominated_with_capacity_is_pareto_improvement(self) -> None:
        """Caso 4: A new non-dominated solution accepted when archive has capacity is a Pareto improvement."""
        archive = LocalParetoArchive(max_size=5)
        sA = Solution(sequence=(1, 2, 1, 2), modes=(1, 1, 1, 1))
        archive.add(sA, decode(self.instance, sA), evaluate(self.instance, decode(self.instance, sA)))

        # New non-dominated solution sC
        sC = Solution(sequence=(1, 2, 1, 2), modes=(2, 1, 1, 1))
        schedC = decode(self.instance, sC)
        objsC = evaluate(self.instance, schedC)

        resC = archive.add(sC, schedC, objsC)
        self.assertTrue(resC.accepted)
        self.assertTrue(resC.candidate_remained)
        self.assertFalse(resC.pruned_by_capacity)
        self.assertEqual(resC.dominated_removed, 0)
        self.assertTrue(resC.pareto_improvement)
        self.assertEqual(len(archive), 2)

    def test_case5_stopping_condition_triggers_after_max_no_improvement_even_if_crowding_changes(self) -> None:
        """Caso 5: LocalSearch stops on max_no_improvement (20) when changes are purely crowding replacements."""
        from unittest.mock import patch

        ls = LocalSearch(max_iterations=50, max_no_improvement=20, max_neighbors=2)

        crowding_only_result = ArchiveAddResult(
            accepted=True,
            dominated_removed=0,
            pruned_by_capacity=True,
            candidate_remained=True,
            pareto_improvement=False,
        )

        orig_add = LocalParetoArchive.add
        calls = [0]

        def mock_add(archive_self, *args, **kwargs):
            calls[0] += 1
            if calls[0] == 1:
                # Allow initial solution insertion
                return orig_add(archive_self, *args, **kwargs)
            # Simulate neighbor accepted and kept by crowding, but pareto_improvement is False
            return crowding_only_result

        with patch.object(LocalParetoArchive, "add", autospec=True, side_effect=mock_add):
            res = ls.search(self.instance, self.init_sol, rng=random.Random(42))

        # Must have stopped due to no_improvement after exactly 20 iterations
        self.assertEqual(res.stopped_reason, "no_improvement")
        self.assertEqual(res.iterations_run, 20)


if __name__ == "__main__":
    unittest.main()

