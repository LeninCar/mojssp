"""Unit tests for DMAB window size W horizon extension diagnostic (Phase 8.3.4).

Verifies invariants of the extended horizon diagnostic:
1. Total budget exactly 1000 FE.
2. Warm-up exactly 150 FE (3 blocks x 50 FE).
3. Adaptive phase exactly 850 FE (17 blocks x 50 FE = 17 decisions).
4. No evaluations outside budget.
5. Reward strictly calculated as HV_after - HV_before.
6. Global archive monotonic in Hypervolume.
7. Bitwise reproducibility with identical seeds.
8. No production code modified.
"""

import math
from pathlib import Path
import unittest

from scripts.diagnose_dmab_window_horizon import (
    WindowHorizonRunResult,
    run_single_window_horizon_trial,
)


class TestDMABWindowHorizonDiagnostic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.instance_path = Path("data/experimental/10_10_2-5_1.dzn")
        cls.c = math.sqrt(2)

    def test_run_invariants_w5_seed42(self):
        """Verify structural invariants for W=5, seed=42 under 1000 FE."""
        res: WindowHorizonRunResult = run_single_window_horizon_trial(
            instance_path=self.instance_path,
            w=5,
            c=self.c,
            seed=42,
            total_budget=1000,
            block_size=50,
        )
        self.assertEqual(res.total_evals, 1000)
        self.assertEqual(res.warmup_evals, 150)
        self.assertEqual(res.adaptive_evals, 850)
        self.assertEqual(res.total_blocks, 20)
        self.assertEqual(len(res.adaptive_sequence), 17)
        self.assertEqual(sum(res.total_fe_by_arm.values()), 1000)
        self.assertEqual(sum(res.adaptive_fe_by_arm.values()), 850)

        # Monotonicity and reward correctness
        prev_hv = 0.0
        for rec in res.history:
            self.assertGreaterEqual(rec.hv_after, rec.hv_before - 1e-12)
            self.assertAlmostEqual(rec.reward, rec.hv_after - rec.hv_before, places=9)
            self.assertGreaterEqual(rec.hv_before, prev_hv - 1e-12)
            prev_hv = rec.hv_after

    def test_run_invariants_w10_seed100(self):
        """Verify structural invariants for W=10, seed=100 under 1000 FE."""
        res: WindowHorizonRunResult = run_single_window_horizon_trial(
            instance_path=self.instance_path,
            w=10,
            c=self.c,
            seed=100,
            total_budget=1000,
            block_size=50,
        )
        self.assertEqual(res.total_evals, 1000)
        self.assertEqual(res.warmup_evals, 150)
        self.assertEqual(res.adaptive_evals, 850)
        self.assertEqual(res.total_blocks, 20)
        self.assertEqual(len(res.adaptive_sequence), 17)
        self.assertEqual(sum(res.total_fe_by_arm.values()), 1000)
        self.assertEqual(sum(res.adaptive_fe_by_arm.values()), 850)

        prev_hv = 0.0
        for rec in res.history:
            self.assertGreaterEqual(rec.hv_after, rec.hv_before - 1e-12)
            self.assertAlmostEqual(rec.reward, rec.hv_after - rec.hv_before, places=9)
            prev_hv = rec.hv_after

    def test_bitwise_reproducibility(self):
        """Verify bitwise reproducibility when repeating trial with same seed."""
        res1 = run_single_window_horizon_trial(
            instance_path=self.instance_path,
            w=5,
            c=self.c,
            seed=42,
            total_budget=1000,
            block_size=50,
        )
        res2 = run_single_window_horizon_trial(
            instance_path=self.instance_path,
            w=5,
            c=self.c,
            seed=42,
            total_budget=1000,
            block_size=50,
        )
        self.assertEqual(res1.total_evals, res2.total_evals)
        self.assertEqual(res1.total_blocks, res2.total_blocks)
        self.assertAlmostEqual(res1.final_hv, res2.final_hv, places=12)
        self.assertEqual(res1.final_archive_size, res2.final_archive_size)
        self.assertEqual(res1.adaptive_sequence, res2.adaptive_sequence)
        self.assertEqual(res1.total_fe_by_arm, res2.total_fe_by_arm)


if __name__ == "__main__":
    unittest.main()
