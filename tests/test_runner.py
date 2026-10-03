"""Unit and integration tests for experimental runner and CSV persistence (Phase 8.3)."""

from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mojssp import (
    BlockExecutionRecord,
    Instance,
    load_dzn,
)
from mojssp.runner import (
    compute_arm_allocations,
    export_results_to_csv,
    run_portfolio_experiment,
    run_standalone_experiment,
)


class TestRunner(unittest.TestCase):
    """Test suite covering runner invariants, budget tracking, and persistence."""

    @classmethod
    def setUpClass(cls):
        cls.val_dir = Path(__file__).resolve().parent.parent / "data" / "validation"
        cls.toy_instance = load_dzn(cls.val_dir / "toy_instance.dzn", validate=True)
        cls.small_3x2 = load_dzn(cls.val_dir / "small_3x2.dzn", validate=True)

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_budget_never_exceeded_standalone(self):
        # 1. Standalone budget strict compliance
        budget = 75
        for arm_name in ["NSGA-II", "MOPSO", "NSGA-II+LS"]:
            res = run_standalone_experiment(
                instance=self.toy_instance,
                arm_name=arm_name,
                seed=42,
                budget=budget,
                block_size=25,
                population_size=10,
            )
            self.assertEqual(res.evaluations_used, budget)
            self.assertLessEqual(res.evaluations_used, res.budget)
            self.assertTrue(res.completed)
            self.assertGreater(res.hypervolume, 0.0)

    def test_portfolio_budget_and_allocations(self):
        # 2, 3, 4, 5, 6, 7, 8, 9: Invariants of portfolio execution
        total_budget = 100
        block_size = 25  # 4 blocks of 25

        run_res, history = run_portfolio_experiment(
            instance=self.toy_instance,
            seed=42,
            total_budget=total_budget,
            block_size=block_size,
            population_size=10,
        )

        # 3. Total evaluations of portfolio is exactly total_budget
        self.assertEqual(run_res.evaluations_used, total_budget)
        self.assertEqual(len(history), 4)

        # 2. evaluations_used <= budget_allocated per block
        for b in history:
            self.assertLessEqual(b.evaluations_used, b.budget_allocated)
            self.assertGreater(b.evaluations_used, 0)

            # 6. Monotonicity: hv_after >= hv_before
            self.assertGreaterEqual(b.hv_after, b.hv_before - 1e-9)

            # 7. Exact reward definition: reward == hv_after - hv_before
            self.assertAlmostEqual(b.reward, b.hv_after - b.hv_before, places=7)

        # 4. Arms appearing in selection
        selected_arms = set(b.arm_name for b in history)
        # In 4 blocks, all 3 arms must appear during the warm-up (blocks 0, 1, 2)
        self.assertTrue({"NSGA-II", "MOPSO", "NSGA-II+LS"}.issubset(selected_arms))

        # 8, 9. Arm allocations aggregate matches blocks and total evaluations
        allocs = run_res.arm_allocations
        self.assertIsNotNone(allocs)
        total_assigned_evals = sum(a.evaluations_assigned for a in allocs.values())
        self.assertEqual(total_assigned_evals, total_budget)

        total_assigned_blocks = sum(a.number_of_blocks for a in allocs.values())
        self.assertEqual(total_assigned_blocks, len(history))

        # Check percentages sum to 100%
        total_pct = sum(a.percentage_of_budget for a in allocs.values())
        self.assertAlmostEqual(total_pct, 100.0, places=5)

    def test_reproducibility_with_same_seed(self):
        # 10. Execution is bit-for-bit reproducible with same seed
        res1, hist1 = run_portfolio_experiment(
            instance=self.small_3x2,
            seed=101,
            total_budget=80,
            block_size=20,
            population_size=10,
        )
        res2, hist2 = run_portfolio_experiment(
            instance=self.small_3x2,
            seed=101,
            total_budget=80,
            block_size=20,
            population_size=10,
        )

        self.assertEqual(res1.hypervolume, res2.hypervolume)
        self.assertEqual(res1.evaluations_used, res2.evaluations_used)
        self.assertEqual(res1.archive_size, res2.archive_size)
        self.assertEqual(len(hist1), len(hist2))
        for b1, b2 in zip(hist1, hist2):
            self.assertEqual(b1.arm_name, b2.arm_name)
            self.assertEqual(b1.evaluations_used, b2.evaluations_used)
            self.assertEqual(b1.reward, b2.reward)

    def test_csv_export_and_field_completeness(self):
        # 11, 12: CSV export contains all fields and separates instances cleanly
        res_toy, hist_toy = run_portfolio_experiment(
            instance=self.toy_instance, seed=42, total_budget=60, block_size=20, population_size=10
        )
        res_s32, hist_s32 = run_portfolio_experiment(
            instance=self.small_3x2, seed=42, total_budget=60, block_size=20, population_size=10
        )
        standalone_toy = run_standalone_experiment(
            instance=self.toy_instance, arm_name="NSGA-II", seed=42, budget=60, block_size=20, population_size=10
        )

        all_runs = [res_toy, res_s32, standalone_toy]
        all_blocks = [(res_toy.run_id, b) for b in hist_toy] + [(res_s32.run_id, b) for b in hist_s32]

        export_results_to_csv(runs=all_runs, portfolio_blocks=all_blocks, results_dir=self.tmp_dir)

        # Check runs.csv
        runs_csv = Path(self.tmp_dir) / "raw" / "runs.csv"
        self.assertTrue(runs_csv.exists())
        lines = runs_csv.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 4)  # header + 3 runs
        header = lines[0].split(",")
        self.assertIn("run_id", header)
        self.assertIn("instance", header)
        self.assertIn("algorithm", header)
        self.assertIn("hypervolume", header)

        # Check blocks.csv
        blocks_csv = Path(self.tmp_dir) / "raw" / "portfolio_blocks.csv"
        self.assertTrue(blocks_csv.exists())
        b_lines = blocks_csv.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(b_lines), 1 + len(all_blocks))

        # Check arm_allocations.csv
        alloc_csv = Path(self.tmp_dir) / "summaries" / "arm_allocations.csv"
        self.assertTrue(alloc_csv.exists())

        # Check front JSON files
        fronts_dir = Path(self.tmp_dir) / "fronts"
        self.assertTrue((fronts_dir / f"{res_toy.run_id}.json").exists())
        self.assertTrue((fronts_dir / f"{res_s32.run_id}.json").exists())


if __name__ == "__main__":
    unittest.main()
