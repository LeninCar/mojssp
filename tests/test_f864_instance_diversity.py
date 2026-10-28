"""Unit test suite for Phase F8.6.4 instance diversity audit.

Verifies:
1. Exactly 37 instances exist (12 original, 25 generated).
2. All 37 instances can be loaded via load_dzn.
3. Characteristics table exists and covers all 37 instances without NaNs or invalid values.
4. Distance matrix has exact number of unique pairs (37*36/2 = 666), non-negative distances, no self-pairs.
5. Factor coverage matrix exists with all required dimensions.
6. Summary JSON exists with valid structure and extreme case classifications.
"""

import csv
import json
import math
import os
from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.mojssp.model.io import load_dzn


class TestF864InstanceDiversity(unittest.TestCase):
    """Test suite verifying integrity and correctness of Phase F8.6.4 diversity audit."""

    @classmethod
    def setUpClass(cls):
        cls.project_root = Path(__file__).resolve().parent.parent
        cls.exp_dir = cls.project_root / "data" / "experimental"
        cls.gen_dir = cls.project_root / "data" / "generated" / "f86_3"
        cls.diag_dir = Path(__file__).parent / "fixtures" / "historical" / "diagnostics"

        cls.char_csv = cls.diag_dir / "f864_instance_characteristics.csv"
        cls.dist_csv = cls.diag_dir / "f864_instance_distances.csv"
        cls.coverage_csv = cls.diag_dir / "f864_factor_coverage.csv"
        cls.summary_json = cls.diag_dir / "f864_summary.json"

    def test_01_all_37_instances_exist_and_loadable(self):
        """Check that 12 original and 25 generated instances exist on disk and load cleanly."""
        exp_files = list(self.exp_dir.glob("*.dzn"))
        gen_files = list(self.gen_dir.rglob("*.dzn"))

        self.assertEqual(len(exp_files), 12, "Expected 12 original instances in data/experimental")
        self.assertEqual(len(gen_files), 25, "Expected 25 generated instances in data/generated/f86_3")

        all_files = exp_files + gen_files
        self.assertEqual(len(all_files), 37)

        for fpath in all_files:
            with self.subTest(instance=fpath.stem):
                inst = load_dzn(fpath, validate=True)
                self.assertGreater(inst.num_jobs, 0)
                self.assertGreater(inst.num_machines, 0)
                self.assertGreater(inst.total_operations, 0)

    def test_02_characteristics_table_integrity(self):
        """Check f864_instance_characteristics.csv has 37 rows, correct columns, no NaNs."""
        self.assertTrue(self.char_csv.exists(), f"Missing {self.char_csv}")

        with open(self.char_csv, mode="r", encoding="utf-8") as f:
            reader = list(csv.DictReader(f))

        self.assertEqual(len(reader), 37, "Expected 37 rows in characteristics table")

        sources = [r["source"] for r in reader]
        self.assertEqual(sources.count("original"), 12)
        self.assertEqual(sources.count("generated"), 25)

        required_cols = [
            "instance", "source", "jobs", "machines", "operations",
            "operations_per_job", "operations_per_machine", "jobs_per_machine",
            "duration_mean", "duration_cv", "energy_mean", "energy_cv",
            "time_energy_conflict", "release_mean", "release_cv",
            "due_mean", "due_cv", "tardiness_pressure", "machine_load_cv",
            "bottleneck_concentration", "bound_cmax_min", "bound_cmax_max",
        ]

        for col in required_cols:
            self.assertIn(col, reader[0], f"Missing column {col} in characteristics CSV")

        for r in reader:
            for k, v in r.items():
                self.assertNotEqual(v, "", f"Empty value in row {r['instance']} for {k}")
                self.assertNotIn(v.lower(), ["nan", "null", "none", "inf"], f"Invalid float value in {r['instance']} for {k}")

    def test_03_distance_matrix_integrity(self):
        """Check f864_instance_distances.csv has exactly 666 unique pairs and valid properties."""
        self.assertTrue(self.dist_csv.exists(), f"Missing {self.dist_csv}")

        with open(self.dist_csv, mode="r", encoding="utf-8") as f:
            reader = list(csv.DictReader(f))

        # 37 * 36 / 2 = 666 pairs
        self.assertEqual(len(reader), 666, "Expected 666 unique pairwise distances")

        seen_pairs = set()
        for r in reader:
            a = r["instance_a"]
            b = r["instance_b"]
            self.assertNotEqual(a, b, f"Self-comparison found for instance {a}")
            pair_key = tuple(sorted([a, b]))
            self.assertNotIn(pair_key, seen_pairs, f"Duplicate pair found: {pair_key}")
            seen_pairs.add(pair_key)

            dist = float(r["distance"])
            self.assertGreaterEqual(dist, 0.0, f"Negative distance between {a} and {b}")

            self.assertIn(r["similarity_category"], [
                "muy similares", "similares", "moderadamente diferentes", "claramente diferentes"
            ])

    def test_04_factor_coverage_matrix(self):
        """Check f864_factor_coverage.csv covers all core dimensions."""
        self.assertTrue(self.coverage_csv.exists(), f"Missing {self.coverage_csv}")

        with open(self.coverage_csv, mode="r", encoding="utf-8") as f:
            reader = list(csv.DictReader(f))

        factors = [r["factor"] for r in reader]
        self.assertTrue(any("Escala" in f for f in factors))
        self.assertTrue(any("Bottleneck" in f for f in factors))
        self.assertTrue(any("Duración" in f for f in factors))
        self.assertTrue(any("Energía" in f for f in factors))
        self.assertTrue(any("Tardanza" in f for f in factors))
        self.assertTrue(any("Releases" in f for f in factors))

    def test_05_summary_json_integrity(self):
        """Check f864_summary.json exists and contains extreme case classifications."""
        self.assertTrue(self.summary_json.exists(), f"Missing {self.summary_json}")

        data = json.loads(self.summary_json.read_text(encoding="utf-8"))
        self.assertEqual(data["total_instances"], 37)
        self.assertEqual(data["counts"]["original_instances"], 12)
        self.assertEqual(data["counts"]["generated_instances"], 25)

        extreme_names = [e["instance"] for e in data["extreme_cases"]]
        self.assertIn("nrg_strong_10x10", extreme_names)
        self.assertIn("tard_high_10x10", extreme_names)
        self.assertIn("btnk_high_10x10", extreme_names)
        self.assertIn("rel_high_10x10", extreme_names)
        self.assertIn("rel_zero_10x10", extreme_names)
        self.assertIn("load_low_10x20", extreme_names)
        self.assertIn("load_high_20x10", extreme_names)


if __name__ == "__main__":
    unittest.main()
