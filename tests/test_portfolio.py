import sys
import unittest
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mojssp import (
    AlgorithmBlockResult,
    ArchiveEntry,
    Decoder,
    Evaluator,
    Instance,
    MOPSOArm,
    NSGA2Arm,
    NSGA2LSArm,
    ObjectiveValues,
    ParetoArchive,
    Portfolio,
    PortfolioArm,
    PortfolioBlockResult,
    Schedule,
    ScheduledOperation,
    Solution,
    dominates,
    load_dzn,
)


class TestPortfolio(unittest.TestCase):
    """Test suite for Portfolio and Global Pareto Archive (Phase 7.3)."""

    def setUp(self) -> None:
        toy_path = Path(__file__).resolve().parent.parent / "data" / "validation" / "toy_instance.dzn"
        self.instance = load_dzn(toy_path)
        self.seed = 42

    def test_arms_registration(self) -> None:
        """Test 1: Verify Portfolio can register and work with NSGA2Arm, MOPSOArm, NSGA2LSArm."""
        arm1 = NSGA2Arm(self.instance, population_size=10, seed=self.seed)
        arm2 = MOPSOArm(self.instance, population_size=10, seed=self.seed)
        arm3 = NSGA2LSArm(self.instance, population_size=10, seed=self.seed)

        portfolio = Portfolio(arms=[arm1, arm2, arm3])

        self.assertEqual(len(portfolio.arms), 3)
        self.assertIn("NSGA-II", portfolio.arm_names)
        self.assertIn("MOPSO", portfolio.arm_names)
        self.assertIn("NSGA-II+LS", portfolio.arm_names)

        # Access by canonical name and aliases
        self.assertIs(portfolio.get_arm("NSGA-II"), arm1)
        self.assertIs(portfolio.get_arm("nsga2"), arm1)
        self.assertIs(portfolio.get_arm("MOPSO"), arm2)
        self.assertIs(portfolio.get_arm("mopso"), arm2)
        self.assertIs(portfolio.get_arm("NSGA-II+LS"), arm3)
        self.assertIs(portfolio.get_arm("nsga2_ls"), arm3)
        self.assertIs(portfolio.get_arm("nsga2ls"), arm3)

        # Validation: non-PortfolioArm
        with self.assertRaises(TypeError):
            portfolio.register_arm("not_an_arm")  # type: ignore

        # Validation: duplicate arm registration
        with self.assertRaises(ValueError):
            portfolio.register_arm(arm1)

    def test_run_arm_execution(self) -> None:
        """Test 2: Verify portfolio.run_arm(name, B) executes arm and updates Global Archive."""
        arm = NSGA2Arm(self.instance, population_size=10, seed=self.seed)
        portfolio = Portfolio(arms=[arm])

        res = portfolio.run_arm("nsga2", 20)
        self.assertIsInstance(res, PortfolioBlockResult)
        self.assertEqual(res.arm_name, "NSGA-II")
        self.assertEqual(res.evaluations_used, 20)
        self.assertFalse(res.completed)
        self.assertIsInstance(res.global_archive, ParetoArchive)
        self.assertFalse(res.global_archive.is_empty)
        self.assertIsInstance(res.arm_result, AlgorithmBlockResult)

        # Global archive in portfolio matches result
        self.assertEqual(len(portfolio.global_archive), len(res.global_archive))
        self.assertEqual(portfolio.total_evaluations, 20)

    def test_budget_strict_enforcement(self) -> None:
        """Test 3: Verify evaluations_used <= B for various budget values."""
        arm = NSGA2Arm(self.instance, population_size=10, seed=self.seed)
        portfolio = Portfolio(arms=[arm])

        budgets = [0, 1, 7, 23, 50, 100]
        total_expected = 0
        for b in budgets:
            res = portfolio.run_arm("nsga2", b)
            self.assertLessEqual(res.evaluations_used, b)
            self.assertEqual(res.evaluations_used, b)
            total_expected += res.evaluations_used
            self.assertEqual(portfolio.total_evaluations, total_expected)

    def test_global_archive_persistence(self) -> None:
        """Test 4: Verify Global Archive persists and accumulates across blocks and arms."""
        arm1 = NSGA2Arm(self.instance, population_size=10, seed=self.seed)
        arm2 = MOPSOArm(self.instance, population_size=10, seed=self.seed + 1)
        portfolio = Portfolio(arms=[arm1, arm2])

        # Block 1 with NSGA-II
        res1 = portfolio.run_arm("nsga2", 20)
        g1_count = len(portfolio.global_archive)
        self.assertGreater(g1_count, 0)
        g1_solutions = set(portfolio.global_archive.solutions)

        # Block 2 with MOPSO
        res2 = portfolio.run_arm("mopso", 20)
        g2_count = len(portfolio.global_archive)
        self.assertGreater(g2_count, 0)

        # Global archive must have incorporated MOPSO solutions into previous G1
        self.assertEqual(portfolio.total_evaluations, 40)
        # All entries in global archive must be non-dominated
        for e1 in portfolio.global_archive.entries:
            for e2 in portfolio.global_archive.entries:
                if e1 != e2:
                    self.assertFalse(dominates(e1.objectives, e2.objectives))

    def test_arms_combination_all_three(self) -> None:
        """Test 5: Sequentially run NSGA2, MOPSO, and NSGA2LS feeding the same Global Archive."""
        arm1 = NSGA2Arm(self.instance, population_size=10, seed=self.seed)
        arm2 = MOPSOArm(self.instance, population_size=10, seed=self.seed + 1)
        arm3 = NSGA2LSArm(self.instance, population_size=10, seed=self.seed + 2)
        portfolio = Portfolio(arms=[arm1, arm2, arm3])

        portfolio.run_arm("nsga2", 30)
        portfolio.run_arm("mopso", 30)
        portfolio.run_arm("nsga2_ls", 30)

        self.assertEqual(portfolio.total_evaluations, 90)
        self.assertFalse(portfolio.global_archive.is_empty)

        # Ensure no solution in global archive dominates any other
        entries = portfolio.global_archive.entries
        for i, e1 in enumerate(entries):
            for j, e2 in enumerate(entries):
                if i != j:
                    self.assertFalse(
                        dominates(e1.objectives, e2.objectives),
                        f"Solution {i} dominates solution {j} in Global Archive!",
                    )

    def test_duplicate_rejection_in_global_archive(self) -> None:
        """Test 6: Identical solution from two arms does not cause duplicates in Global Archive."""
        # Create a mock/controlled test using two arms or directly injecting solutions
        arm1 = NSGA2Arm(self.instance, population_size=10, seed=self.seed)
        portfolio = Portfolio(arms=[arm1])

        # Run arm1 once to populate global archive
        res1 = portfolio.run_arm("nsga2", 15)
        initial_entries_count = len(portfolio.global_archive)

        # Manually verify that feeding identical archive entries does not duplicate them
        portfolio._global_archive.update(res1.global_archive.entries)
        self.assertEqual(len(portfolio.global_archive), initial_entries_count)

    def test_dominance_pruning_in_global_archive(self) -> None:
        """Test 7: Verify dominated solutions are properly pruned when a dominating solution is added."""
        portfolio = Portfolio()
        def make_dummy_entry(job_id: int, mode_id: int, makespan: int, tardiness: int, energy: float):
            sol = Solution(sequence=(job_id,), modes=(mode_id,))
            sched_op = ScheduledOperation(
                job_id=job_id,
                op_id=0,
                machine_id=0,
                mode_id=mode_id,
                start=0,
                completion=makespan,
                duration=makespan,
                energy=energy,
            )
            sched = Schedule([sched_op])
            objs = ObjectiveValues(makespan=makespan, tardiness=tardiness, energy=energy)
            return ArchiveEntry(solution=sol, schedule=sched, objectives=objs)

        # entry1: dominated by entry2
        entry1 = make_dummy_entry(job_id=0, mode_id=1, makespan=15, tardiness=5, energy=80.0)
        # entry2: dominates entry1 on all objectives
        entry2 = make_dummy_entry(job_id=1, mode_id=2, makespan=10, tardiness=2, energy=50.0)

        self.assertTrue(dominates(entry2.objectives, entry1.objectives))

        # Add entry1 first
        portfolio._global_archive.add_entry(entry1)
        self.assertEqual(len(portfolio.global_archive), 1)
        self.assertEqual(portfolio.global_archive.solutions[0], entry1.solution)

        # Now add entry2 (which dominates entry1): entry1 should be pruned, entry2 retained
        portfolio._global_archive.add_entry(entry2)
        self.assertEqual(len(portfolio.global_archive), 1)
        self.assertEqual(portfolio.global_archive.solutions[0], entry2.solution)

    def test_arm_internal_state_continuity(self) -> None:
        """Test 8: Verify portfolio does not reset or reconstruct an arm between blocks."""
        arm = NSGA2Arm(self.instance, population_size=10, seed=self.seed)
        portfolio = Portfolio(arms=[arm])

        res1 = portfolio.run_arm("nsga2", 50)
        self.assertEqual(arm.total_evaluations, 50)
        self.assertEqual(portfolio.total_evaluations, 50)

        res2 = portfolio.run_arm("nsga2", 50)
        self.assertEqual(arm.total_evaluations, 100)
        self.assertEqual(portfolio.total_evaluations, 100)

        # Arm continued its trajectory seamlessly
        self.assertEqual(res1.evaluations_used, 50)
        self.assertEqual(res2.evaluations_used, 50)

    def test_defensive_snapshot_independence(self) -> None:
        """Test 9: Verify modifying returned global_archive snapshot does not mutate internal archive."""
        arm = NSGA2Arm(self.instance, population_size=10, seed=self.seed)
        portfolio = Portfolio(arms=[arm])

        res = portfolio.run_arm("nsga2", 20)
        self.assertFalse(portfolio.global_archive.is_empty)

        # Mutate the returned snapshot in result
        original_count = len(portfolio.global_archive)
        res.global_archive.clear()
        self.assertTrue(res.global_archive.is_empty)
        self.assertEqual(len(portfolio.global_archive), original_count)

        # Mutate the property snapshot
        snap = portfolio.global_archive
        snap.clear()
        self.assertTrue(snap.is_empty)
        self.assertEqual(len(portfolio.global_archive), original_count)

    def test_real_integration_all_arms(self) -> None:
        """Test 10: Real end-to-end integration with NSGA2Arm, MOPSOArm, NSGA2LSArm on toy_instance."""
        arm_nsga2 = NSGA2Arm(self.instance, population_size=10, seed=42)
        arm_mopso = MOPSOArm(self.instance, population_size=10, seed=43)
        arm_nsga2ls = NSGA2LSArm(self.instance, population_size=10, seed=44)

        portfolio = Portfolio(
            arms={
                "nsga2": arm_nsga2,
                "mopso": arm_mopso,
                "nsga2_ls": arm_nsga2ls,
            }
        )

        # Run interleaved blocks
        r1 = portfolio.run_arm("nsga2", 25)
        r2 = portfolio.run_arm("mopso", 25)
        r3 = portfolio.run_arm("nsga2_ls", 25)
        r4 = portfolio.run_arm("nsga2", 25)

        self.assertEqual(portfolio.total_evaluations, 100)
        self.assertEqual(arm_nsga2.total_evaluations, 50)
        self.assertEqual(arm_mopso.total_evaluations, 25)
        self.assertEqual(arm_nsga2ls.total_evaluations, 25)

        global_archive = portfolio.global_archive
        self.assertGreater(len(global_archive), 0)

        # Verify all entries in global_archive are non-dominated
        for i, e1 in enumerate(global_archive.entries):
            for j, e2 in enumerate(global_archive.entries):
                if i != j:
                    self.assertFalse(dominates(e1.objectives, e2.objectives))

    def test_unknown_arm_keyerror(self) -> None:
        """Verify requesting an unregistered arm raises KeyError."""
        portfolio = Portfolio()
        with self.assertRaises(KeyError):
            portfolio.run_arm("non_existent_arm", 50)
        with self.assertRaises(KeyError):
            portfolio.get_arm("non_existent_arm")

    def test_reset_functionality(self) -> None:
        """Verify reset() clears Global Archive, evaluation counter, and resets registered arms."""
        arm1 = NSGA2Arm(self.instance, population_size=10, seed=self.seed)
        arm2 = MOPSOArm(self.instance, population_size=10, seed=self.seed)
        portfolio = Portfolio(arms=[arm1, arm2])

        portfolio.run_arm("nsga2", 30)
        portfolio.run_arm("mopso", 30)
        self.assertEqual(portfolio.total_evaluations, 60)
        self.assertFalse(portfolio.global_archive.is_empty)

        portfolio.reset()
        self.assertEqual(portfolio.total_evaluations, 0)
        self.assertTrue(portfolio.global_archive.is_empty)
        self.assertEqual(arm1.total_evaluations, 0)
        self.assertEqual(arm2.total_evaluations, 0)


if __name__ == "__main__":
    unittest.main()
