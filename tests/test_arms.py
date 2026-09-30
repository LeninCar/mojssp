import sys
import unittest
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mojssp import (
    ActiveLSState,
    AlgorithmBlockResult,
    ArchiveEntry,
    Instance,
    MOPSOArm,
    NSGA2Arm,
    NSGA2LSArm,
    ParetoArchive,
    PortfolioArm,
    Solution,
    load_dzn,
)


class TestNSGA2Arm(unittest.TestCase):
    """Test suite for NSGA2Arm under Phase 7.2 common arm contract."""

    def setUp(self) -> None:
        toy_path = Path(__file__).resolve().parent.parent / "data" / "toy_instance.dzn"
        self.instance = load_dzn(toy_path)
        self.seed = 42

    def test_protocol_conformance(self) -> None:
        """Verify NSGA2Arm conforms to the PortfolioArm runtime_checkable protocol."""
        arm = NSGA2Arm(self.instance, population_size=10, seed=self.seed)
        self.assertIsInstance(arm, PortfolioArm)
        self.assertEqual(arm.arm_name, "NSGA-II")
        self.assertEqual(arm.total_evaluations, 0)
        self.assertFalse(arm.is_completed)

    def test_budget_strict_enforcement(self) -> None:
        """Verify run(B) never exceeds B evaluations across various budget values."""
        budgets = [1, 7, 23, 50, 100]
        arm = NSGA2Arm(self.instance, population_size=10, max_generations=50, seed=self.seed)

        accumulated_evals = 0
        for b in budgets:
            res = arm.run(b)
            self.assertIsInstance(res, AlgorithmBlockResult)
            self.assertLessEqual(res.evaluations_used, b)
            self.assertEqual(res.evaluations_used, b)
            accumulated_evals += res.evaluations_used
            self.assertEqual(arm.total_evaluations, accumulated_evals)

    def test_zero_or_negative_budget(self) -> None:
        """Verify run(0) or run(-5) returns 0 evaluations without error."""
        arm = NSGA2Arm(self.instance, population_size=10, seed=self.seed)
        res0 = arm.run(0)
        self.assertEqual(res0.evaluations_used, 0)
        self.assertEqual(arm.total_evaluations, 0)

        res_neg = arm.run(-10)
        self.assertEqual(res_neg.evaluations_used, 0)
        self.assertEqual(arm.total_evaluations, 0)

    def test_archive_defensive_snapshot(self) -> None:
        """Verify result.solutions is a defensive snapshot that cannot mutate arm._archive."""
        arm = NSGA2Arm(self.instance, population_size=10, seed=self.seed)
        res = arm.run(20)
        self.assertIsInstance(res.solutions, ParetoArchive)
        self.assertFalse(res.solutions.is_empty)

        # Modifying the returned archive should not modify the arm's internal archive
        initial_count = len(arm.current_archive)
        res.solutions.clear()
        self.assertTrue(res.solutions.is_empty)
        self.assertEqual(len(arm.current_archive), initial_count)

    def test_continuity_200_vs_100_plus_100(self) -> None:
        """Verify running continuous 200 evals is bit-for-bit identical to 100 + 100."""
        # Continuous run
        arm_cont = NSGA2Arm(self.instance, population_size=10, max_generations=20, seed=self.seed)
        res_cont = arm_cont.run(200)

        # Segmented run: 100 + 100
        arm_seg = NSGA2Arm(self.instance, population_size=10, max_generations=20, seed=self.seed)
        res_seg1 = arm_seg.run(100)
        res_seg2 = arm_seg.run(100)

        self.assertEqual(res_seg1.evaluations_used, 100)
        self.assertEqual(res_seg2.evaluations_used, 100)
        self.assertEqual(arm_seg.total_evaluations, 200)

        # Exact match in population solutions and objectives
        cont_pop = [(ind.solution, ind.objectives) for ind in arm_cont._population]
        seg_pop = [(ind.solution, ind.objectives) for ind in arm_seg._population]
        self.assertEqual(cont_pop, seg_pop)

        # Exact match in archive solutions and objectives
        self.assertEqual(res_cont.solutions.solutions, res_seg2.solutions.solutions)
        self.assertEqual(res_cont.solutions.objectives, res_seg2.solutions.objectives)

    def test_arbitrary_budget_cuts(self) -> None:
        """Verify exact continuity across arbitrary cuts: 50+150, 37+63+100, 101+99, 5+95+100, 1+9+40+150."""
        arm_base = NSGA2Arm(self.instance, population_size=10, max_generations=20, seed=self.seed)
        res_base = arm_base.run(200)
        base_pop = [(ind.solution, ind.objectives) for ind in arm_base._population]
        base_arch_sols = res_base.solutions.solutions
        base_arch_objs = res_base.solutions.objectives

        cut_sequences = [
            [50, 150],
            [37, 63, 100],
            [101, 99],
            [5, 95, 100],
            [1, 9, 40, 150],
        ]

        for cuts in cut_sequences:
            with self.subTest(cuts=cuts):
                arm = NSGA2Arm(self.instance, population_size=10, max_generations=20, seed=self.seed)
                total_used = 0
                last_res = None
                for c in cuts:
                    last_res = arm.run(c)
                    total_used += last_res.evaluations_used

                self.assertEqual(total_used, 200)
                self.assertEqual(arm.total_evaluations, 200)

                arm_pop = [(ind.solution, ind.objectives) for ind in arm._population]
                self.assertEqual(arm_pop, base_pop)
                self.assertEqual(last_res.solutions.solutions, base_arch_sols)
                self.assertEqual(last_res.solutions.objectives, base_arch_objs)

    def test_global_max_evaluations_truncation_and_completion(self) -> None:
        """Verify arm respects max_evaluations=150, truncates on 100+100, and reports completed=True."""
        arm = NSGA2Arm(
            self.instance,
            population_size=10,
            max_generations=50,
            max_evaluations=150,
            seed=self.seed,
        )

        res1 = arm.run(100)
        self.assertEqual(res1.evaluations_used, 100)
        self.assertFalse(res1.completed)
        self.assertFalse(arm.is_completed)
        self.assertEqual(arm.total_evaluations, 100)

        # Second block requests 100, but only 50 remain
        res2 = arm.run(100)
        self.assertEqual(res2.evaluations_used, 50)
        self.assertTrue(res2.completed)
        self.assertTrue(arm.is_completed)
        self.assertEqual(arm.total_evaluations, 150)

        # Subsequent call with arm completed returns 0 evaluations
        res3 = arm.run(100)
        self.assertEqual(res3.evaluations_used, 0)
        self.assertTrue(res3.completed)
        self.assertTrue(arm.is_completed)
        self.assertEqual(arm.total_evaluations, 150)

    def test_max_generations_completion(self) -> None:
        """Verify arm completes when max_generations is reached and subsequent run() uses 0 evals."""
        # pop_size=10, max_generations=2 => 10 (P0) + 2*10 (Q) = 30 evaluations
        arm = NSGA2Arm(
            self.instance,
            population_size=10,
            max_generations=2,
            seed=self.seed,
        )

        res1 = arm.run(50)
        self.assertEqual(res1.evaluations_used, 30)
        self.assertTrue(res1.completed)
        self.assertTrue(arm.is_completed)
        self.assertEqual(arm.generations_completed, 2)
        self.assertEqual(arm.total_evaluations, 30)

        # Subsequent call
        res2 = arm.run(50)
        self.assertEqual(res2.evaluations_used, 0)
        self.assertTrue(res2.completed)
        self.assertTrue(arm.is_completed)

    def test_reset_functionality(self) -> None:
        """Verify reset() restores the arm to its initial unexecuted state."""
        arm = NSGA2Arm(self.instance, population_size=10, max_generations=10, seed=self.seed)
        res1 = arm.run(50)
        self.assertEqual(res1.evaluations_used, 50)
        self.assertEqual(arm.total_evaluations, 50)

        arm.reset()
        self.assertEqual(arm.total_evaluations, 0)
        self.assertEqual(arm.generations_completed, 0)
        self.assertFalse(arm.is_completed)
        self.assertTrue(arm.current_archive.is_empty)

        # After reset, running 50 again with same seed produces identical evaluations
        res2 = arm.run(50)
        self.assertEqual(res2.evaluations_used, 50)
        self.assertEqual(res1.solutions.solutions, res2.solutions.solutions)
        self.assertEqual(res1.solutions.objectives, res2.solutions.objectives)


class TestMOPSOArm(unittest.TestCase):
    """Test suite for MOPSOArm under Phase 7.2 common arm contract."""

    def setUp(self) -> None:
        toy_path = Path(__file__).resolve().parent.parent / "data" / "toy_instance.dzn"
        self.instance = load_dzn(toy_path)
        self.seed = 42

    def test_protocol_conformance(self) -> None:
        """Verify MOPSOArm conforms to the PortfolioArm runtime_checkable protocol."""
        arm = MOPSOArm(self.instance, population_size=10, seed=self.seed)
        self.assertIsInstance(arm, PortfolioArm)
        self.assertEqual(arm.arm_name, "MOPSO")
        self.assertEqual(arm.total_evaluations, 0)
        self.assertFalse(arm.is_completed)
        self.assertEqual(arm.iterations, 0)
        self.assertEqual(arm.current_particle_index, 0)
        self.assertEqual(len(arm.particles), 0)
        self.assertTrue(arm.current_archive.is_empty)

    def test_budget_strict_enforcement(self) -> None:
        """Verify run(B) never exceeds B evaluations across various budget values."""
        budgets = [1, 7, 23, 50, 100]
        arm = MOPSOArm(self.instance, population_size=10, max_evaluations=500, seed=self.seed)

        accumulated_evals = 0
        for b in budgets:
            res = arm.run(b)
            self.assertIsInstance(res, AlgorithmBlockResult)
            self.assertLessEqual(res.evaluations_used, b)
            self.assertEqual(res.evaluations_used, b)
            accumulated_evals += res.evaluations_used
            self.assertEqual(arm.total_evaluations, accumulated_evals)

    def test_zero_or_negative_budget(self) -> None:
        """Verify run(0) or run(-5) returns 0 evaluations without error."""
        arm = MOPSOArm(self.instance, population_size=10, seed=self.seed)
        res0 = arm.run(0)
        self.assertEqual(res0.evaluations_used, 0)
        self.assertEqual(arm.total_evaluations, 0)

        res_neg = arm.run(-10)
        self.assertEqual(res_neg.evaluations_used, 0)
        self.assertEqual(arm.total_evaluations, 0)

    def test_archive_defensive_snapshot(self) -> None:
        """Verify result.solutions is a defensive snapshot that cannot mutate arm._global_archive."""
        arm = MOPSOArm(self.instance, population_size=10, seed=self.seed)
        res = arm.run(20)
        self.assertIsInstance(res.solutions, ParetoArchive)
        self.assertFalse(res.solutions.is_empty)

        initial_count = len(arm.current_archive)
        res.solutions.clear()
        self.assertTrue(res.solutions.is_empty)
        self.assertEqual(len(arm.current_archive), initial_count)
        self.assertEqual(len(arm.global_archive), initial_count)

    def test_continuity_200_vs_100_plus_100(self) -> None:
        """Verify running continuous 200 evals is bit-for-bit identical to 100 + 100."""
        # Continuous run
        arm_cont = MOPSOArm(self.instance, population_size=10, max_evaluations=500, seed=self.seed)
        res_cont = arm_cont.run(200)

        # Segmented run: 100 + 100
        arm_seg = MOPSOArm(self.instance, population_size=10, max_evaluations=500, seed=self.seed)
        res_seg1 = arm_seg.run(100)
        res_seg2 = arm_seg.run(100)

        self.assertEqual(res_seg1.evaluations_used, 100)
        self.assertEqual(res_seg2.evaluations_used, 100)
        self.assertEqual(arm_seg.total_evaluations, 200)

        # Exact match in particle positions and objectives
        cont_particles = [(p.position, obj) for p, obj in zip(arm_cont.particles, arm_cont.particle_objectives)]
        seg_particles = [(p.position, obj) for p, obj in zip(arm_seg.particles, arm_seg.particle_objectives)]
        self.assertEqual(cont_particles, seg_particles)

        # Exact match in global archive solutions and objectives
        self.assertEqual(res_cont.solutions.solutions, res_seg2.solutions.solutions)
        self.assertEqual(res_cont.solutions.objectives, res_seg2.solutions.objectives)

    def test_arbitrary_budget_cuts(self) -> None:
        """Verify exact continuity across arbitrary cuts: 50+150, 37+63+100, 101+99, 5+95+100, 1+9+40+150, 23+41+57+79."""
        arm_base = MOPSOArm(self.instance, population_size=10, max_evaluations=500, seed=self.seed)
        res_base = arm_base.run(200)
        base_particles = [(p.position, obj) for p, obj in zip(arm_base.particles, arm_base.particle_objectives)]
        base_arch_sols = res_base.solutions.solutions
        base_arch_objs = res_base.solutions.objectives

        cut_sequences = [
            [50, 150],
            [37, 63, 100],
            [101, 99],
            [5, 95, 100],
            [1, 9, 40, 150],
            [23, 41, 57, 79],
        ]

        for cuts in cut_sequences:
            with self.subTest(cuts=cuts):
                arm = MOPSOArm(self.instance, population_size=10, max_evaluations=500, seed=self.seed)
                total_used = 0
                last_res = None
                for c in cuts:
                    last_res = arm.run(c)
                    total_used += last_res.evaluations_used

                self.assertEqual(total_used, 200)
                self.assertEqual(arm.total_evaluations, 200)

                arm_particles = [(p.position, obj) for p, obj in zip(arm.particles, arm.particle_objectives)]
                self.assertEqual(arm_particles, base_particles)
                self.assertEqual(last_res.solutions.solutions, base_arch_sols)
                self.assertEqual(last_res.solutions.objectives, base_arch_objs)

    def test_mid_initialization_cuts(self) -> None:
        """Verify pausing and resuming during swarm initialization preserves exact swarm state."""
        # pop_size=10: run 3, then 7
        arm = MOPSOArm(self.instance, population_size=10, seed=self.seed)
        res1 = arm.run(3)
        self.assertEqual(res1.evaluations_used, 3)
        self.assertEqual(len(arm.particles), 3)
        self.assertEqual(arm.iterations, 0)
        self.assertEqual(arm.total_evaluations, 3)

        res2 = arm.run(7)
        self.assertEqual(res2.evaluations_used, 7)
        self.assertEqual(len(arm.particles), 10)
        self.assertEqual(arm.iterations, 0)
        self.assertEqual(arm.total_evaluations, 10)

        # Baseline running 10 in one go
        arm_base = MOPSOArm(self.instance, population_size=10, seed=self.seed)
        res_base = arm_base.run(10)

        arm_particles = [(p.position, obj) for p, obj in zip(arm.particles, arm.particle_objectives)]
        base_particles = [(p.position, obj) for p, obj in zip(arm_base.particles, arm_base.particle_objectives)]
        self.assertEqual(arm_particles, base_particles)
        self.assertEqual(res2.solutions.solutions, res_base.solutions.solutions)
        self.assertEqual(res2.solutions.objectives, res_base.solutions.objectives)

    def test_global_crowding_preservation(self) -> None:
        """Verify global_crowding dictionary is preserved across pause and resume."""
        arm = MOPSOArm(self.instance, population_size=10, global_crowding_interval=10, seed=self.seed)
        # 10 evals init + 3 evals of iteration 1 = 13 evals
        arm.run(13)
        self.assertEqual(arm.iterations, 1)
        self.assertEqual(arm.current_particle_index, 3)
        crowding_before = dict(arm.global_crowding)
        self.assertGreater(len(crowding_before), 0)

        # Resume with 4 more evals (still in iteration 1, particles 3..6)
        arm.run(4)
        self.assertEqual(arm.iterations, 1)
        self.assertEqual(arm.current_particle_index, 7)
        crowding_after = dict(arm.global_crowding)
        # Should be identical because global_crowding is only updated at iter 1 and multiples of interval
        self.assertEqual(crowding_before, crowding_after)

    def test_global_archive_independence_from_personal_archives(self) -> None:
        """Verify global_archive is never pruned by personal_archive bounded size."""
        # Personal archive capped at 2, while global archive can grow arbitrarily
        arm = MOPSOArm(
            self.instance,
            population_size=10,
            personal_archive_size=2,
            seed=self.seed,
        )
        arm.run(100)
        for p in arm.particles:
            self.assertLessEqual(len(p.personal_archive), 2)
        self.assertGreater(len(arm.global_archive), 2)

    def test_global_max_evaluations_truncation_and_completion(self) -> None:
        """Verify arm respects max_evaluations=150, truncates on 100+100, and reports completed=True."""
        arm = MOPSOArm(
            self.instance,
            population_size=10,
            max_evaluations=150,
            seed=self.seed,
        )

        res1 = arm.run(100)
        self.assertEqual(res1.evaluations_used, 100)
        self.assertFalse(res1.completed)
        self.assertFalse(arm.is_completed)
        self.assertEqual(arm.total_evaluations, 100)

        # Second block requests 100, but only 50 remain
        res2 = arm.run(100)
        self.assertEqual(res2.evaluations_used, 50)
        self.assertTrue(res2.completed)
        self.assertTrue(arm.is_completed)
        self.assertEqual(arm.total_evaluations, 150)

        # Subsequent call with arm completed returns 0 evaluations
        res3 = arm.run(100)
        self.assertEqual(res3.evaluations_used, 0)
        self.assertTrue(res3.completed)
        self.assertTrue(arm.is_completed)
        self.assertEqual(arm.total_evaluations, 150)

    def test_reset_functionality(self) -> None:
        """Verify reset() restores MOPSOArm to its initial unexecuted state."""
        arm = MOPSOArm(self.instance, population_size=10, seed=self.seed)
        res1 = arm.run(50)
        self.assertEqual(res1.evaluations_used, 50)
        self.assertEqual(arm.total_evaluations, 50)

        arm.reset()
        self.assertEqual(arm.total_evaluations, 0)
        self.assertEqual(arm.iterations, 0)
        self.assertEqual(arm.current_particle_index, 0)
        self.assertEqual(len(arm.particles), 0)
        self.assertFalse(arm.is_completed)
        self.assertTrue(arm.current_archive.is_empty)

        # After reset, running 50 again with same seed produces identical evaluations
        res2 = arm.run(50)
        self.assertEqual(res2.evaluations_used, 50)
        self.assertEqual(res1.solutions.solutions, res2.solutions.solutions)
        self.assertEqual(res1.solutions.objectives, res2.solutions.objectives)


class TestNSGA2LSArm(unittest.TestCase):
    """Test suite for NSGA2LSArm under Phase 7.2 common arm contract."""

    def setUp(self) -> None:
        toy_path = Path(__file__).resolve().parent.parent / "data" / "toy_instance.dzn"
        self.instance = load_dzn(toy_path)
        self.seed = 42

    def test_protocol_conformance(self) -> None:
        """Verify NSGA2LSArm conforms to the PortfolioArm runtime_checkable protocol."""
        arm = NSGA2LSArm(self.instance, population_size=10, seed=self.seed)
        self.assertIsInstance(arm, PortfolioArm)
        self.assertEqual(arm.arm_name, "NSGA-II+LS")
        self.assertEqual(arm.total_evaluations, 0)
        self.assertEqual(arm.ls_evaluations, 0)
        self.assertFalse(arm.is_completed)
        self.assertEqual(arm.generations_completed, 0)
        self.assertEqual(arm.phase, "INIT")
        self.assertEqual(len(arm.population), 0)
        self.assertIsNone(arm.active_ls_state)
        self.assertTrue(arm.current_archive.is_empty)

    def test_budget_strict_enforcement(self) -> None:
        """Verify run(B) never exceeds B evaluations across various budget values."""
        budgets = [0, 1, 7, 23, 50, 100]
        arm = NSGA2LSArm(self.instance, population_size=10, max_generations=10, seed=self.seed)

        accumulated_evals = 0
        for b in budgets:
            res = arm.run(b)
            self.assertIsInstance(res, AlgorithmBlockResult)
            self.assertLessEqual(res.evaluations_used, b)
            self.assertEqual(res.evaluations_used, b)
            accumulated_evals += res.evaluations_used
            self.assertEqual(arm.total_evaluations, accumulated_evals)
            self.assertLessEqual(arm.ls_evaluations, arm.total_evaluations)

    def test_zero_or_negative_budget(self) -> None:
        """Verify run(0) or run(-5) returns 0 evaluations without error."""
        arm = NSGA2LSArm(self.instance, population_size=10, seed=self.seed)
        res0 = arm.run(0)
        self.assertEqual(res0.evaluations_used, 0)
        self.assertEqual(arm.total_evaluations, 0)

        res_neg = arm.run(-10)
        self.assertEqual(res_neg.evaluations_used, 0)
        self.assertEqual(arm.total_evaluations, 0)

    def test_archive_defensive_snapshot(self) -> None:
        """Verify result.solutions is a defensive snapshot that cannot mutate arm._archive."""
        arm = NSGA2LSArm(self.instance, population_size=10, seed=self.seed)
        res = arm.run(20)
        self.assertIsInstance(res.solutions, ParetoArchive)
        self.assertFalse(res.solutions.is_empty)

        initial_count = len(arm.current_archive)
        res.solutions.clear()
        self.assertTrue(res.solutions.is_empty)
        self.assertEqual(len(arm.current_archive), initial_count)
        self.assertEqual(len(arm.archive), initial_count)

    def test_continuity_200_vs_100_plus_100(self) -> None:
        """Verify running continuous 200 evals is bit-for-bit identical to 100 + 100."""
        # Continuous run
        arm_cont = NSGA2LSArm(self.instance, population_size=10, max_generations=5, seed=self.seed)
        res_cont = arm_cont.run(200)

        # Segmented run: 100 + 100
        arm_seg = NSGA2LSArm(self.instance, population_size=10, max_generations=5, seed=self.seed)
        res_seg1 = arm_seg.run(100)
        res_seg2 = arm_seg.run(100)

        self.assertEqual(res_seg1.evaluations_used, 100)
        self.assertEqual(res_seg2.evaluations_used, 100)
        self.assertEqual(arm_seg.total_evaluations, 200)
        self.assertEqual(arm_seg.total_evaluations, arm_cont.total_evaluations)
        self.assertEqual(arm_seg.ls_evaluations, arm_cont.ls_evaluations)
        self.assertEqual(arm_seg.phase, arm_cont.phase)
        self.assertEqual(arm_seg.generations_completed, arm_cont.generations_completed)

        # Population match
        cont_pop = [(ind.solution, ind.objectives) for ind in arm_cont.population]
        seg_pop = [(ind.solution, ind.objectives) for ind in arm_seg.population]
        self.assertEqual(cont_pop, seg_pop)

        # Offspring and candidates match
        cont_offspring = [(ind.solution, ind.objectives) for ind in arm_cont.offspring_in_progress]
        seg_offspring = [(ind.solution, ind.objectives) for ind in arm_seg.offspring_in_progress]
        self.assertEqual(cont_offspring, seg_offspring)
        self.assertEqual(arm_cont.pending_sibling, arm_seg.pending_sibling)

        cont_cand = [(ind.solution, ind.objectives) for ind in arm_cont.candidates_for_ls]
        seg_cand = [(ind.solution, ind.objectives) for ind in arm_seg.candidates_for_ls]
        self.assertEqual(cont_cand, seg_cand)
        self.assertEqual(arm_cont.current_candidate_index, arm_seg.current_candidate_index)

        cont_refined = [(ind.solution, ind.objectives) for ind in arm_cont.refined_individuals]
        seg_refined = [(ind.solution, ind.objectives) for ind in arm_seg.refined_individuals]
        self.assertEqual(cont_refined, seg_refined)

        # Active LS state match
        if arm_cont.active_ls_state is not None:
            self.assertIsNotNone(arm_seg.active_ls_state)
            self.assertEqual(
                arm_cont.active_ls_state.current_iteration,
                arm_seg.active_ls_state.current_iteration,
            )
            self.assertEqual(
                arm_cont.active_ls_state.pair_index,
                arm_seg.active_ls_state.pair_index,
            )
            self.assertEqual(
                arm_cont.active_ls_state.sampled_pairs,
                arm_seg.active_ls_state.sampled_pairs,
            )
            self.assertEqual(
                arm_cont.active_ls_state.base_entry_solution,
                arm_seg.active_ls_state.base_entry_solution,
            )
            self.assertEqual(
                arm_cont.active_ls_state.iteration_improved,
                arm_seg.active_ls_state.iteration_improved,
            )
            self.assertEqual(
                arm_cont.active_ls_state.consecutive_no_improvement,
                arm_seg.active_ls_state.consecutive_no_improvement,
            )
            cont_ls_entries = [
                (e.solution, e.objectives) for e in arm_cont.active_ls_state.local_archive_entries
            ]
            seg_ls_entries = [
                (e.solution, e.objectives) for e in arm_seg.active_ls_state.local_archive_entries
            ]
            self.assertEqual(cont_ls_entries, seg_ls_entries)

        # Archive match
        self.assertEqual(res_cont.solutions.solutions, res_seg2.solutions.solutions)
        self.assertEqual(res_cont.solutions.objectives, res_seg2.solutions.objectives)

    def test_arbitrary_budget_cuts(self) -> None:
        """Verify exact continuity across arbitrary cuts: 50+150, 37+63+100, 101+99, 5+95+100, 1+9+40+150, 23+41+57+79."""
        arm_base = NSGA2LSArm(self.instance, population_size=10, max_generations=5, seed=self.seed)
        res_base = arm_base.run(200)
        base_pop = [(ind.solution, ind.objectives) for ind in arm_base.population]
        base_arch_sols = res_base.solutions.solutions
        base_arch_objs = res_base.solutions.objectives

        cut_sequences = [
            [50, 150],
            [37, 63, 100],
            [101, 99],
            [5, 95, 100],
            [1, 9, 40, 150],
            [23, 41, 57, 79],
        ]

        for cuts in cut_sequences:
            with self.subTest(cuts=cuts):
                arm = NSGA2LSArm(self.instance, population_size=10, max_generations=5, seed=self.seed)
                total_used = 0
                last_res = None
                for c in cuts:
                    last_res = arm.run(c)
                    total_used += last_res.evaluations_used

                self.assertEqual(total_used, 200)
                self.assertEqual(arm.total_evaluations, 200)
                self.assertEqual(arm.ls_evaluations, arm_base.ls_evaluations)

                arm_pop = [(ind.solution, ind.objectives) for ind in arm.population]
                self.assertEqual(arm_pop, base_pop)
                self.assertEqual(last_res.solutions.solutions, base_arch_sols)
                self.assertEqual(last_res.solutions.objectives, base_arch_objs)

    def test_cut_specifically_within_local_search(self) -> None:
        """Verify arm accurately pauses and resumes inside active Local Search iteration."""
        # 10 evals for P0, 10 evals for Q1 = 20 evals, then LS starts.
        # Running 35 evaluations pauses at eval 15 of LS.
        arm = NSGA2LSArm(self.instance, population_size=10, max_generations=5, seed=self.seed)
        res1 = arm.run(35)
        self.assertEqual(res1.evaluations_used, 35)
        self.assertEqual(arm.phase, "LS")
        self.assertIsNotNone(arm.active_ls_state)

        # Check all required active_ls_state properties
        active = arm.active_ls_state
        self.assertIsInstance(active, ActiveLSState)
        self.assertGreater(len(active.sampled_pairs), 0)
        self.assertGreaterEqual(active.pair_index, 0)
        self.assertLess(active.pair_index, len(active.sampled_pairs))
        self.assertIsNotNone(active.base_entry_solution)
        self.assertGreater(len(active.local_archive_entries), 0)
        self.assertGreaterEqual(active.current_iteration, 1)
        self.assertGreaterEqual(active.consecutive_no_improvement, 0)
        self.assertIsInstance(active.iteration_improved, bool)

        # Baseline running 70 evaluations in one go
        arm_base = NSGA2LSArm(self.instance, population_size=10, max_generations=5, seed=self.seed)
        res_base = arm_base.run(70)

        # Resume paused arm with 35 more evaluations (total 70)
        res2 = arm.run(35)
        self.assertEqual(res2.evaluations_used, 35)
        self.assertEqual(arm.total_evaluations, 70)
        self.assertEqual(arm.ls_evaluations, arm_base.ls_evaluations)
        self.assertEqual(res2.solutions.solutions, res_base.solutions.solutions)
        self.assertEqual(res2.solutions.objectives, res_base.solutions.objectives)

    def test_cut_during_offspring(self) -> None:
        """Verify arm pauses and resumes accurately during offspring construction with pending sibling."""
        # pop_size=10: 10 evals in P0. Budget 13 stops during Q generation (child 1 evaluated, child 2 pending).
        arm = NSGA2LSArm(self.instance, population_size=10, max_generations=5, seed=self.seed)
        res1 = arm.run(13)
        self.assertEqual(res1.evaluations_used, 13)
        self.assertEqual(arm.phase, "OFFSPRING")
        self.assertEqual(len(arm.offspring_in_progress), 3)
        self.assertIsNotNone(arm.pending_sibling)

        # Baseline running 20 in one go
        arm_base = NSGA2LSArm(self.instance, population_size=10, max_generations=5, seed=self.seed)
        res_base = arm_base.run(20)

        # Resume with 7 evals to complete offspring
        res2 = arm.run(7)
        self.assertEqual(res2.evaluations_used, 7)
        self.assertEqual(arm.total_evaluations, 20)
        self.assertEqual(arm.phase, "LS")
        self.assertEqual(res2.solutions.solutions, res_base.solutions.solutions)
        self.assertEqual(res2.solutions.objectives, res_base.solutions.objectives)

    def test_rng_continuity(self) -> None:
        """Verify pausing and resuming does not divert RNG trajectory without reseeding."""
        arm_cont = NSGA2LSArm(self.instance, population_size=10, max_generations=5, seed=self.seed)
        arm_cont.run(150)
        rng_cont_state = arm_cont._rng.getstate()

        arm_seg = NSGA2LSArm(self.instance, population_size=10, max_generations=5, seed=self.seed)
        arm_seg.run(50)
        arm_seg.run(50)
        arm_seg.run(50)
        rng_seg_state = arm_seg._rng.getstate()

        self.assertEqual(rng_cont_state, rng_seg_state)

    def test_global_max_evaluations_truncation_and_completion(self) -> None:
        """Verify arm respects max_evaluations=150, truncates on 100+100, and reports completed=True."""
        arm = NSGA2LSArm(
            self.instance,
            population_size=10,
            max_generations=50,
            max_evaluations=150,
            seed=self.seed,
        )

        res1 = arm.run(100)
        self.assertEqual(res1.evaluations_used, 100)
        self.assertFalse(res1.completed)
        self.assertFalse(arm.is_completed)
        self.assertEqual(arm.total_evaluations, 100)

        # Second block requests 100, but only 50 remain
        res2 = arm.run(100)
        self.assertEqual(res2.evaluations_used, 50)
        self.assertTrue(res2.completed)
        self.assertTrue(arm.is_completed)
        self.assertEqual(arm.total_evaluations, 150)

        # Subsequent call with arm completed returns 0 evaluations
        res3 = arm.run(100)
        self.assertEqual(res3.evaluations_used, 0)
        self.assertTrue(res3.completed)
        self.assertTrue(arm.is_completed)
        self.assertEqual(arm.total_evaluations, 150)

    def test_reset_functionality(self) -> None:
        """Verify reset() restores NSGA2LSArm to its initial unexecuted state."""
        arm = NSGA2LSArm(self.instance, population_size=10, max_generations=5, seed=self.seed)
        res1 = arm.run(50)
        self.assertEqual(res1.evaluations_used, 50)
        self.assertEqual(arm.total_evaluations, 50)

        arm.reset()
        self.assertEqual(arm.total_evaluations, 0)
        self.assertEqual(arm.ls_evaluations, 0)
        self.assertEqual(arm.generations_completed, 0)
        self.assertEqual(arm.phase, "INIT")
        self.assertEqual(len(arm.population), 0)
        self.assertEqual(len(arm.offspring_in_progress), 0)
        self.assertIsNone(arm.pending_sibling)
        self.assertEqual(len(arm.candidates_for_ls), 0)
        self.assertEqual(arm.current_candidate_index, 0)
        self.assertEqual(len(arm.refined_individuals), 0)
        self.assertIsNone(arm.active_ls_state)
        self.assertFalse(arm.is_completed)
        self.assertTrue(arm.current_archive.is_empty)

        # After reset, running 50 again with same seed produces identical evaluations
        res2 = arm.run(50)
        self.assertEqual(res2.evaluations_used, 50)
        self.assertEqual(res1.solutions.solutions, res2.solutions.solutions)
        self.assertEqual(res1.solutions.objectives, res2.solutions.objectives)


if __name__ == "__main__":
    unittest.main()
