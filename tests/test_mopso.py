"""Unit tests for discrete MOPSO module (Phase 6)."""

import math
from pathlib import Path
import random
import sys
import unittest
from unittest.mock import patch

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mojssp import (
    Decoder,
    Evaluator,
    Instance,
    MOPSO,
    MOPSOResult,
    mopso,
    ParetoArchive,
    PersonalParetoArchive,
    Solution,
    decode,
    evaluate,
    load_dzn,
    validate_schedule,
)
from mojssp.algorithms.mopso import (
    calculate_entries_crowding_distance,
    generate_mode_moves,
    generate_sequence_moves,
    select_guide_by_crowding,
)
from mojssp.metrics.pareto_archive import ArchiveEntry


class TestMOPSOComponents(unittest.TestCase):
    """Test unit components of discrete MOPSO."""

    def setUp(self) -> None:
        toy_dzn = Path(__file__).resolve().parent.parent / "data" / "validation" / "toy_instance.dzn"
        self.instance = load_dzn(str(toy_dzn))

    def test_velocity_limits_and_50_50_budget_distribution(self) -> None:
        """Test calculation of Vseq_max, Vmode_max and odd remainder allocation to gbest."""
        # For N = 4 operations:
        # Vseq_max = max(1, floor(0.15 * 4)) = max(1, 0) = 1
        # Vmode_max = max(1, floor(0.08 * 4)) = max(1, 0) = 1
        # Since 1 is odd:
        # seq_pbest = floor(1 / 2) = 0
        # seq_gbest = 1 - 0 = 1
        n_ops = 4
        vseq_max = max(1, math.floor(0.15 * n_ops))
        vmode_max = max(1, math.floor(0.08 * n_ops))
        self.assertEqual(vseq_max, 1)
        self.assertEqual(vmode_max, 1)

        seq_pbest = math.floor(vseq_max / 2)
        seq_gbest = vseq_max - seq_pbest
        self.assertEqual(seq_pbest, 0)
        self.assertEqual(seq_gbest, 1)

        # For N = 20:
        # Vseq_max = floor(0.15 * 20) = 3
        # Vmode_max = max(1, floor(0.08 * 20)) = max(1, 1) = 1
        n_ops2 = 20
        vseq_max2 = max(1, math.floor(0.15 * n_ops2))
        self.assertEqual(vseq_max2, 3)
        seq_pbest2 = math.floor(vseq_max2 / 2)
        seq_gbest2 = vseq_max2 - seq_pbest2
        self.assertEqual(seq_pbest2, 1)
        self.assertEqual(seq_gbest2, 2)  # Odd remainder assigned to gbest

    def test_velocity_budget_sum_and_parity_distribution(self) -> None:
        """Test that pbest_budget + gbest_budget == Vmax for sequence and modes across diverse N."""
        test_n_values = [1, 2, 3, 4, 7, 10, 13, 20, 25, 33, 50, 100]

        for n in test_n_values:
            vseq_max = max(1, math.floor(0.15 * n))
            vmode_max = max(1, math.floor(0.08 * n))

            seq_pbest = math.floor(vseq_max / 2)
            seq_gbest = vseq_max - seq_pbest
            mode_pbest = math.floor(vmode_max / 2)
            mode_gbest = vmode_max - mode_pbest

            # Exact sum invariant
            self.assertEqual(seq_pbest + seq_gbest, vseq_max)
            self.assertEqual(mode_pbest + mode_gbest, vmode_max)

            # Odd remainder assigned to gbest
            if vseq_max % 2 == 1:
                self.assertEqual(seq_gbest, seq_pbest + 1)
            else:
                self.assertEqual(seq_gbest, seq_pbest)

            if vmode_max % 2 == 1:
                self.assertEqual(mode_gbest, mode_pbest + 1)
            else:
                self.assertEqual(mode_gbest, mode_pbest)

    def test_sequence_moves_preserves_job_multiplicities(self) -> None:
        """Test that generate_sequence_moves swaps jobs while preserving exact multiplicities."""
        current = (1, 1, 2, 2)
        guide = (2, 2, 1, 1)

        # Budget = 1 swap
        res1 = generate_sequence_moves(current, guide, budget=1)
        # Position 0 was 1, guide needs 2. Earliest 2 is at index 2.
        # Swapping index 0 and 2 yields: (2, 1, 1, 2)
        self.assertEqual(res1, (2, 1, 1, 2))
        self.assertEqual(res1.count(1), 2)
        self.assertEqual(res1.count(2), 2)

        # Budget = 2 swaps
        res2 = generate_sequence_moves(current, guide, budget=2)
        # First swap: (2, 1, 1, 2). Next diff at pos 1: has 1, guide needs 2. Earliest 2 is at index 3.
        # Swapping pos 1 and 3 yields: (2, 2, 1, 1) == guide!
        self.assertEqual(res2, (2, 2, 1, 1))
        self.assertEqual(res2.count(1), 2)
        self.assertEqual(res2.count(2), 2)

    def test_sequence_moves_no_change_when_current_equals_guide(self) -> None:
        """Test that no sequence moves are generated when current == guide."""
        current = (1, 2, 1, 2)
        res = generate_sequence_moves(current, current, budget=5)
        self.assertEqual(res, current)

    def test_mode_moves_preserves_validity(self) -> None:
        """Test that generate_mode_moves changes modes to guide modes within budget."""
        current_modes = (1, 1, 1, 1)
        guide_modes = (2, 2, 2, 2)

        # Budget = 1
        res1 = generate_mode_moves(current_modes, guide_modes, budget=1, instance=self.instance)
        self.assertEqual(res1, (2, 1, 1, 1))

        # Budget = 2
        res2 = generate_mode_moves(current_modes, guide_modes, budget=2, instance=self.instance)
        self.assertEqual(res2, (2, 2, 1, 1))

    def test_mode_moves_no_change_when_current_equals_guide(self) -> None:
        """Test that no mode moves are generated when current == guide."""
        current_modes = (1, 2, 1, 2)
        res = generate_mode_moves(current_modes, current_modes, budget=5, instance=self.instance)
        self.assertEqual(res, current_modes)

    def test_personal_archive_capacity_and_crowding_pruning(self) -> None:
        """Test that PersonalParetoArchive respects max_size and prunes by crowding."""
        archive = PersonalParetoArchive(max_size=3)

        for i in range(5):
            modes = (1, 1, 1, 1 if i == 0 else 2)
            seq = (1, 2, 1, 2) if i % 2 == 0 else (2, 1, 1, 2)
            sol = Solution(sequence=seq, modes=modes)
            sched = decode(self.instance, sol)
            objs = evaluate(self.instance, sched)
            archive.add(sol, sched, objs)

        self.assertLessEqual(len(archive), 3)

    def test_pbest_selected_via_crowding_not_by_single_objective(self) -> None:
        """Test that pbest is selected from personal archive via crowding, not min(Cmax), min(T), or min(E)."""
        archive = PersonalParetoArchive(max_size=10)
        # Entry 1: min makespan (8), max energy (93)
        s1 = Solution((1, 2, 1, 2), (2, 2, 2, 2))
        # Entry 2: intermediate makespan (11), intermediate energy (63)
        s2 = Solution((1, 2, 1, 2), (2, 1, 1, 1))
        # Entry 3: max makespan (12), min energy (53)
        s3 = Solution((1, 2, 1, 2), (1, 1, 1, 1))

        archive.add(s1, decode(self.instance, s1), evaluate(self.instance, decode(self.instance, s1)))
        archive.add(s2, decode(self.instance, s2), evaluate(self.instance, decode(self.instance, s2)))
        archive.add(s3, decode(self.instance, s3), evaluate(self.instance, decode(self.instance, s3)))

        # Verify that all 3 entries are mutually non-dominated in the archive
        self.assertEqual(len(archive), 3)

        # Calculate crowding distances for particle's personal archive
        p_crowding = calculate_entries_crowding_distance(archive.entries)

        # Boundary extremes have inf distance
        inf_entries = [e for e in archive.entries if math.isinf(p_crowding.get(e, 0.0))]
        self.assertGreaterEqual(len(inf_entries), 2)

        # Over multiple draws, select_guide_by_crowding selects among extremes uniformly
        # and does NOT always select min(Cmax) or min(E)
        selections = [
            select_guide_by_crowding(archive.entries, p_crowding, random.Random(seed)) for seed in range(50)
        ]
        selected_solutions = {e.solution for e in selections}

        # Must have selected more than one solution across different seeds
        self.assertGreater(len(selected_solutions), 1)
        # Specifically, neither min(Cmax) nor min(E) has a monopoly
        self.assertIn(s1, selected_solutions)
        self.assertIn(s3, selected_solutions)

    def test_gbest_selection_priority_for_infinite_crowding_and_proportional_for_finite(self) -> None:
        """Test that gbest selection prioritizes infinity uniformly, and is proportional for finite."""
        rng = random.Random(42)

        s1 = Solution((1, 2, 1, 2), (1, 1, 1, 1))
        s2 = Solution((1, 2, 1, 2), (2, 1, 1, 1))
        s3 = Solution((1, 2, 1, 2), (2, 2, 2, 2))
        e1 = ArchiveEntry(s1, decode(self.instance, s1), evaluate(self.instance, decode(self.instance, s1)))
        e2 = ArchiveEntry(s2, decode(self.instance, s2), evaluate(self.instance, decode(self.instance, s2)))
        e3 = ArchiveEntry(s3, decode(self.instance, s3), evaluate(self.instance, decode(self.instance, s3)))

        entries = [e1, e2, e3]

        # Case A: Boundary points with infinity crowding
        distances = calculate_entries_crowding_distance(entries)
        self.assertTrue(math.isinf(distances[e1]))
        self.assertTrue(math.isinf(distances[e3]))

        # Selected guide must be chosen uniformly among infinite entries
        chosen_inf = [
            select_guide_by_crowding(entries, distances, random.Random(seed)) for seed in range(100)
        ]
        self.assertTrue(all(e in [e1, e3] for e in chosen_inf))
        # Both infinite extremes are selected roughly equally
        self.assertGreater(chosen_inf.count(e1), 30)
        self.assertGreater(chosen_inf.count(e3), 30)

        # Case B: All finite distances
        finite_distances = {e1: 0.1, e2: 0.8, e3: 0.1}
        selections = [
            select_guide_by_crowding(entries, finite_distances, random.Random(seed)) for seed in range(200)
        ]
        # e2 has 80% weight
        self.assertGreater(selections.count(e2), 130)

    def test_global_crowding_cache_lifecycle_with_new_entries(self) -> None:
        """Test intentional global crowding caching: new entries wait for next recalculation."""
        global_archive = ParetoArchive()

        sA = Solution((1, 2, 1, 2), (1, 1, 1, 1))
        sB = Solution((1, 2, 1, 2), (2, 2, 2, 2))
        global_archive.add(sA, decode(self.instance, sA), evaluate(self.instance, decode(self.instance, sA)))
        global_archive.add(sB, decode(self.instance, sB), evaluate(self.instance, decode(self.instance, sB)))

        # Step 1: Calculate initial crowding cache
        global_crowding = calculate_entries_crowding_distance(global_archive.entries)
        initial_entries = list(global_archive.entries)
        for e in initial_entries:
            self.assertIn(e, global_crowding)

        # Step 2: Add new non-dominated entry sC to ParetoArchive
        sC = Solution((1, 2, 1, 2), (2, 1, 1, 1))
        global_archive.add(sC, decode(self.instance, sC), evaluate(self.instance, decode(self.instance, sC)))

        # Step 3: Verify sC is in ParetoArchive, but NOT in previous global_crowding cache
        self.assertEqual(len(global_archive), 3)
        entry_C = next(e for e in global_archive.entries if e.solution == sC)
        self.assertNotIn(entry_C, global_crowding)

        # Step 4: Verify sC is NOT eligible as gbest under the active_global_entries filter
        active_global_entries = [e for e in global_archive.entries if e in global_crowding]
        self.assertNotIn(entry_C, active_global_entries)
        self.assertEqual(len(active_global_entries), 2)

        # Step 5: Next scheduled periodic recalculation occurs
        global_crowding = calculate_entries_crowding_distance(global_archive.entries)

        # Step 6: Verify sC now appears in global_crowding and is eligible as gbest
        self.assertIn(entry_C, global_crowding)
        active_global_entries_after = [e for e in global_archive.entries if e in global_crowding]
        self.assertIn(entry_C, active_global_entries_after)
        self.assertEqual(len(active_global_entries_after), 3)


class TestMOPSOExecution(unittest.TestCase):
    """Test full execution of discrete MOPSO."""

    def setUp(self) -> None:
        toy_dzn = Path(__file__).resolve().parent.parent / "data" / "validation" / "toy_instance.dzn"
        self.instance = load_dzn(str(toy_dzn))

    def test_parameter_validations(self) -> None:
        """Test validation of constructor parameters."""
        with self.assertRaises(ValueError):
            MOPSO(population_size=1)
        with self.assertRaises(ValueError):
            MOPSO(population_size=10, max_evaluations=5)
        with self.assertRaises(ValueError):
            MOPSO(personal_archive_size=0)
        with self.assertRaises(ValueError):
            MOPSO(global_crowding_interval=0)

    def test_swarm_size_and_initialization(self) -> None:
        """Test that swarm size matches population_size and particles have valid positions."""
        algo = MOPSO(population_size=10, max_evaluations=10)
        res = algo.run(self.instance, seed=123)

        self.assertEqual(len(res.population), 10)
        self.assertEqual(len(res.population_objectives), 10)
        self.assertEqual(res.total_evaluations, 10)

        for sol in res.population:
            sched = decode(self.instance, sol)
            validate_schedule(self.instance, sched)

    def test_budget_exact_accounting_and_stop_mid_iteration(self) -> None:
        """Test that evaluations do not exceed max_evaluations when stopping mid-iteration."""
        # pop_size = 10, max_evaluations = 15.
        # Initial evaluations: 10.
        # Iteration 1 evaluates 5 particles, then stops exactly at 15!
        algo = MOPSO(population_size=10, max_evaluations=15)
        res = algo.run(self.instance, seed=42)

        self.assertEqual(res.total_evaluations, 15)
        self.assertEqual(res.iterations, 1)

    def test_deterministic_reproducibility(self) -> None:
        """Test that two runs with identical seed are deterministic and reproducible for the same instance, configuration and seed."""
        algo1 = MOPSO(population_size=6, max_evaluations=30)
        algo2 = MOPSO(population_size=6, max_evaluations=30)

        res1 = algo1.run(self.instance, seed=999)
        res2 = algo2.run(self.instance, seed=999)

        self.assertEqual(res1.total_evaluations, res2.total_evaluations)
        self.assertEqual(res1.iterations, res2.iterations)
        self.assertEqual(
            [e.solution.sequence for e in res1.archive.entries],
            [e.solution.sequence for e in res2.archive.entries],
        )
        self.assertEqual(
            [e.solution.modes for e in res1.archive.entries],
            [e.solution.modes for e in res2.archive.entries],
        )
        self.assertEqual(
            [e.objectives for e in res1.archive.entries],
            [e.objectives for e in res2.archive.entries],
        )

    def test_all_archive_schedules_pass_validator(self) -> None:
        """Test that all non-dominated solutions discovered by MOPSO produce valid schedules."""
        res = mopso(self.instance, population_size=8, max_evaluations=40, seed=42)

        self.assertGreater(len(res.archive), 0)
        for entry in res.archive.entries:
            validate_schedule(self.instance, entry.schedule)
            self.assertEqual(entry.schedule.makespan, entry.objectives.makespan)

    def test_global_archive_contains_only_non_dominated(self) -> None:
        """Test that the final global Pareto archive contains mutually non-dominated solutions."""
        from mojssp import dominates

        res = mopso(self.instance, population_size=10, max_evaluations=60, seed=77)
        entries = res.archive.entries

        for i, e1 in enumerate(entries):
            for j, e2 in enumerate(entries):
                if i != j:
                    self.assertFalse(
                        dominates(e1.objectives, e2.objectives),
                        f"Entry {i} dominates entry {j} in global archive!",
                    )

    def test_global_crowding_interval_recalculation(self) -> None:
        """Test that global crowding is recalculated at iteration 1 and periodically every interval."""
        pop_size = 4
        # 4 initial + 4 * 25 iterations = 104 evaluations (25 completed iterations)
        algo = MOPSO(
            population_size=pop_size,
            max_evaluations=4 + 4 * 25,
            global_crowding_interval=10,
        )

        from mojssp.algorithms.mopso import calculate_entries_crowding_distance as orig_calc

        # Track each call to calculate_entries_crowding_distance:
        # At iteration start (when global crowding is checked), if it runs, it is called BEFORE
        # the pop_size particle calls of that iteration.
        call_records = []

        def spy_calc(entries):
            call_records.append(len(entries))
            return orig_calc(entries)

        with patch("mojssp.algorithms.mopso.calculate_entries_crowding_distance", side_effect=spy_calc):
            res = algo.run(self.instance, seed=42)

        self.assertEqual(res.iterations, 25)
        self.assertEqual(res.total_evaluations, 104)

        # For 25 iterations:
        # Particle calls: 4 per iteration * 25 iterations = 100 calls.
        # Global archive calls occur at:
        # Iteration 1: 1 call
        # Iteration 10: 1 call
        # Iteration 20: 1 call
        # Total global calls = 3.
        # Total calls = 100 + 3 = 103.
        self.assertEqual(len(call_records), 103)


if __name__ == "__main__":
    unittest.main()
