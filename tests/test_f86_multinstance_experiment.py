"""Unit tests for Phase 8.6: Multi-Instance & Multi-Seed Experiment.

Verifies invariants of the F8.6 experimental protocol and generated artifacts:
1. Total execution count: exactly 200 runs (5 instances x 10 seeds x 4 configs).
2. Strict budget enforcement: exactly 1000 FE with 0 overshoot across all 200 runs.
3. Portfolio structure: 150 FE neutral warm-up, 850 FE adaptive (17 blocks).
4. Adaptive sum invariant: nsga2_fe + mopso_fe + nsga2_ls_fe == 850.
5. Adaptive trace count: exactly 850 blocks (5 instances x 10 seeds x 17 blocks).
6. Pairwise comparisons count: exactly 150 rows (5 instances x 10 seeds x 3 comparisons).
7. Summary table: exactly 20 rows (5 instances x 4 configs).
8. DMAB parameters recorded: W=10, c=0.07.
9. Bit-for-bit reproducibility on repeated execution under the same seed.
"""

import csv
from pathlib import Path
import unittest

from scripts.run_f86_experiment import (
    run_portfolio_execution,
    run_standalone_execution,
)


class TestF86MultinstanceExperiment(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.exp_dir = Path("results/experiments")
        cls.runs_csv = cls.exp_dir / "f86_runs.csv"
        cls.blocks_csv = cls.exp_dir / "f86_dmab_blocks.csv"
        cls.pairwise_csv = cls.exp_dir / "f86_pairwise.csv"
        cls.summary_csv = cls.exp_dir / "f86_summary_by_instance.csv"

    def test_artifacts_exist(self):
        """Verify all 4 required CSV artifacts exist."""
        self.assertTrue(self.runs_csv.exists(), f"Missing {self.runs_csv}")
        self.assertTrue(self.blocks_csv.exists(), f"Missing {self.blocks_csv}")
        self.assertTrue(self.pairwise_csv.exists(), f"Missing {self.pairwise_csv}")
        self.assertTrue(self.summary_csv.exists(), f"Missing {self.summary_csv}")

    def test_runs_csv_invariants(self):
        """Verify 200 data rows, exact 1000 FE, zero overshoot, and portfolio partitioning."""
        with open(self.runs_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        self.assertEqual(len(rows), 200, f"Expected 200 runs, got {len(rows)}")

        instances = set()
        seeds = set()
        configs = set()

        for r in rows:
            instances.add(r["instance"])
            seeds.add(int(r["seed"]))
            configs.add(r["configuration"])

            self.assertEqual(int(r["budget"]), 1000)
            self.assertEqual(int(r["evaluations_used"]), 1000)
            self.assertEqual(int(r["overshoot"]), 0)
            self.assertGreater(float(r["final_hv"]), 0.0)
            self.assertGreater(int(r["archive_size"]), 0)

            if r["configuration"] == "Portfolio+DMAB":
                self.assertEqual(int(r["warmup_fe"]), 150)
                self.assertEqual(int(r["adaptive_fe"]), 850)
                n_fe = int(r["nsga2_fe"])
                m_fe = int(r["mopso_fe"])
                l_fe = int(r["nsga2_ls_fe"])
                self.assertEqual(n_fe + m_fe + l_fe, 850)

                n_blk = int(r["nsga2_blocks"])
                m_blk = int(r["mopso_blocks"])
                l_blk = int(r["nsga2_ls_blocks"])
                self.assertEqual(n_blk + m_blk + l_blk, 17)

                share_n = float(r["nsga2_budget_share"])
                share_m = float(r["mopso_budget_share"])
                share_l = float(r["nsga2_ls_budget_share"])
                self.assertAlmostEqual(share_n + share_m + share_l, 100.0, places=5)

        self.assertEqual(len(instances), 5)
        self.assertEqual(len(seeds), 10)
        self.assertEqual(configs, {"NSGA-II", "MOPSO", "NSGA-II+LS", "Portfolio+DMAB"})

    def test_dmab_blocks_csv_invariants(self):
        """Verify 850 adaptive blocks, non-negative rewards, and recorded parameters."""
        with open(self.blocks_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        self.assertEqual(len(rows), 850, f"Expected 850 blocks, got {len(rows)}")

        for r in rows:
            self.assertEqual(r["phase"], "adaptive")
            self.assertEqual(int(r["budget_allocated"]), 50)
            self.assertEqual(int(r["evaluations_used"]), 50)
            self.assertEqual(int(r["window_size"]), 10)
            self.assertAlmostEqual(float(r["exploration_factor"]), 0.07, places=5)

            hv_before = float(r["hv_before"])
            hv_after = float(r["hv_after"])
            reward = float(r["reward"])
            self.assertGreaterEqual(hv_after, hv_before - 1e-12)
            self.assertAlmostEqual(reward, hv_after - hv_before, places=6)

    def test_pairwise_csv_invariants(self):
        """Verify 150 pairwise comparison rows and correct math."""
        with open(self.pairwise_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        self.assertEqual(len(rows), 150, f"Expected 150 pairwise rows, got {len(rows)}")

        for r in rows:
            p_hv = float(r["portfolio_hv"])
            s_hv = float(r["standalone_hv"])
            diff = float(r["absolute_difference"])
            rel = float(r["relative_difference_percent"])

            self.assertAlmostEqual(diff, p_hv - s_hv, places=7)
            expected_rel = (diff / s_hv * 100.0) if s_hv > 0 else 0.0
            self.assertAlmostEqual(rel, expected_rel, places=3)

    def test_summary_by_instance_csv_invariants(self):
        """Verify 20 summary rows (5 instances x 4 configs) with n=10 each."""
        with open(self.summary_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        self.assertEqual(len(rows), 20, f"Expected 20 summary rows, got {len(rows)}")

        for r in rows:
            self.assertEqual(int(r["n"]), 10)
            mean_hv = float(r["mean_hv"])
            min_hv = float(r["min_hv"])
            max_hv = float(r["max_hv"])
            self.assertLessEqual(min_hv, mean_hv)
            self.assertLessEqual(mean_hv, max_hv)

    def test_bitwise_reproducibility(self):
        """Verify deterministic reproducibility on instance 15_10_2-5_1.dzn with seed 7."""
        inst = Path("data/experimental/15_10_2-5_1.dzn")
        p1, tr1 = run_portfolio_execution(inst, seed=7, total_budget=1000)
        p2, tr2 = run_portfolio_execution(inst, seed=7, total_budget=1000)

        self.assertEqual(p1.final_hv, p2.final_hv)
        self.assertEqual(p1.archive_size, p2.archive_size)
        self.assertEqual(p1.selection_sequence, p2.selection_sequence)
        self.assertEqual(p1.nsga2_fe, p2.nsga2_fe)
        self.assertEqual(p1.mopso_fe, p2.mopso_fe)
        self.assertEqual(p1.nsga2_ls_fe, p2.nsga2_ls_fe)

        for t1, t2 in zip(tr1, tr2):
            self.assertEqual(t1.selected_arm, t2.selected_arm)
            self.assertEqual(t1.reward, t2.reward)
            self.assertEqual(t1.hv_after, t2.hv_after)


if __name__ == "__main__":
    unittest.main()
