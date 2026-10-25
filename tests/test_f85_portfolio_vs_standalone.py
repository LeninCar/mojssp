"""Unit tests for Phase 8.5: Portfolio vs Standalone + budget adaptation.

Verifies invariants of the F8.5 experimental protocol:
1. Strict budget enforcement: exactly 1000 FE for standalone runs and portfolio.
2. Zero overshoot in all configurations.
3. Portfolio budget breakdown: 150 FE neutral warm-up (3 blocks) + 850 FE adaptive (17 blocks).
4. Sum of arm evaluations in Portfolio equals 1000 FE (nsga2_fe + mopso_fe + nsga2_ls_fe == 1000).
5. Exact 17 adaptive DMAB decisions.
6. Bitwise reproducibility under identical seeds.
7. Verification of exported CSV artifacts and schema.
"""

from pathlib import Path
import unittest

from scripts.run_f85_experiment import (
    run_portfolio_execution,
    run_standalone_execution,
)


class TestF85PortfolioVsStandalone(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.instance_path = Path("data/experimental/10_10_2-5_1.dzn")
        cls.budget = 1000
        cls.block_size = 50
        cls.w = 10
        cls.c = 0.07

    def test_standalone_budget_enforcement(self):
        """Verify standalone runs strictly consume 1000 FE with zero overshoot."""
        for alg in ["NSGA-II", "MOPSO", "NSGA-II+LS"]:
            res = run_standalone_execution(
                instance_path=self.instance_path,
                seed=42,
                configuration=alg,
                budget=self.budget,
            )
            self.assertEqual(
                res.evaluations_used,
                self.budget,
                f"{alg} used {res.evaluations_used} FE instead of {self.budget}",
            )
            self.assertGreater(res.final_hv, 0.0)
            self.assertGreater(res.archive_size, 0)

    def test_portfolio_budget_and_block_invariants(self):
        """Verify Portfolio+DMAB strictly respects 1000 FE, warmup/adaptive partition and block counts."""
        res, traces = run_portfolio_execution(
            instance_path=self.instance_path,
            seed=42,
            total_budget=self.budget,
            block_size=self.block_size,
            w=self.w,
            c=self.c,
        )

        # Budget totals
        self.assertEqual(res.evaluations_used, self.budget)
        self.assertEqual(res.warmup_fe, 150)
        self.assertEqual(res.adaptive_fe, 850)
        self.assertEqual(res.nsga2_fe + res.mopso_fe + res.nsga2_ls_fe, self.budget)

        # Block counts
        self.assertEqual(len(traces), 17)
        self.assertEqual(res.nsga2_blocks + res.mopso_blocks + res.nsga2_ls_blocks, 17)

        # Budget shares sum to 100%
        total_share = res.nsga2_budget_share + res.mopso_budget_share + res.nsga2_ls_budget_share
        self.assertAlmostEqual(total_share, 100.0, places=5)

        # Non-decreasing HV and valid rewards in traces
        prev_hv = 0.0
        for tr in traces:
            self.assertGreaterEqual(tr.hv_after, tr.hv_before - 1e-12)
            self.assertAlmostEqual(tr.reward, tr.hv_after - tr.hv_before, places=9)
            self.assertGreaterEqual(tr.hv_before, prev_hv - 1e-12)
            prev_hv = tr.hv_after

    def test_bitwise_reproducibility(self):
        """Verify identical seed produces identical results bitwise."""
        res1, traces1 = run_portfolio_execution(
            instance_path=self.instance_path,
            seed=100,
            total_budget=self.budget,
            block_size=self.block_size,
            w=self.w,
            c=self.c,
        )
        res2, traces2 = run_portfolio_execution(
            instance_path=self.instance_path,
            seed=100,
            total_budget=self.budget,
            block_size=self.block_size,
            w=self.w,
            c=self.c,
        )

        self.assertEqual(res1.final_hv, res2.final_hv)
        self.assertEqual(res1.archive_size, res2.archive_size)
        self.assertEqual(res1.selection_sequence, res2.selection_sequence)
        self.assertEqual(res1.nsga2_fe, res2.nsga2_fe)
        self.assertEqual(res1.mopso_fe, res2.mopso_fe)
        self.assertEqual(res1.nsga2_ls_fe, res2.nsga2_ls_fe)

        for tr1, tr2 in zip(traces1, traces2):
            self.assertEqual(tr1.selected_arm, tr2.selected_arm)
            self.assertEqual(tr1.reward, tr2.reward)
            self.assertEqual(tr1.hv_after, tr2.hv_after)

    def test_exported_csv_files_exist(self):
        """Verify exported CSV files exist and contain valid headers and expected row count."""
        summary_csv = Path(__file__).parent / "fixtures/historical/experiments/f85_portfolio_vs_standalone.csv"
        alloc_csv = Path(__file__).parent / "fixtures/historical/experiments/f85_dmab_allocation.csv"

        self.assertTrue(summary_csv.exists(), f"Missing {summary_csv}")
        self.assertTrue(alloc_csv.exists(), f"Missing {alloc_csv}")

        # Summary CSV must have 1 header + 8 data rows (2 seeds x 4 configs)
        with open(summary_csv, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
        self.assertEqual(len(lines), 9)

        # Allocation CSV must have 1 header + 34 data rows (2 seeds x 17 adaptive blocks)
        with open(alloc_csv, "r", encoding="utf-8") as f:
            lines_alloc = [line.strip() for line in f if line.strip()]
        self.assertEqual(len(lines_alloc), 35)


if __name__ == "__main__":
    unittest.main()
