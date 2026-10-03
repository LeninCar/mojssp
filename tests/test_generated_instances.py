"""Unit test suite for the 25 generated MO-JSSP instances (Phase F8.6.3).

Verifies:
1. Exactly 25 instances exist in registry and filesystem.
2. All have valid .dzn format.
3. All can be loaded via load_dzn with semantic validation passing.
4. Dimensions are valid (JOBS > 0, MACHINES > 0, ops = n * m, SPEED = 5).
5. All processing times are strictly positive (p > 0).
6. All energy consumption values are non-negative (e >= 0).
7. Release dates (r >= 0) and due dates (d >= 0) are valid non-negative values.
8. Feasible solution genotypes can be constructed and decoded by Decoder.
9. Schedules can be evaluated by Evaluator.
10. Objective values (Cmax, Tardiness, Energy) are finite and non-negative.
11. Generation is strictly deterministic and reproducible under identical seeds.
"""

import unittest
from pathlib import Path

from scripts.generate_mojssp_instances import (
    INSTANCES_CONFIG,
    InstanceConfig,
    generate_single_instance,
)
from src.mojssp.decoder import Decoder
from src.mojssp.evaluator import Evaluator
from src.mojssp.io import load_dzn
from src.mojssp.solution import Solution
from src.mojssp.validator import validate_instance


class TestGeneratedInstances(unittest.TestCase):
    """Test suite covering the 25 newly generated MO-JSSP instances."""

    @classmethod
    def setUpClass(cls):
        cls.data_dir = Path("data/generated/f86_3")
        cls.registry_path = Path("data/instance_registry.csv")
        cls.decoder = Decoder()
        cls.evaluator = Evaluator()

    def test_01_exactly_25_instances_exist_in_registry_and_disk(self):
        """Check that exactly 25 instances exist in config and on disk."""
        self.assertEqual(len(INSTANCES_CONFIG), 25)

        dzn_files = list(self.data_dir.rglob("*.dzn"))
        self.assertEqual(len(dzn_files), 25)

        self.assertTrue(self.registry_path.exists())
        lines = self.registry_path.read_text(encoding="utf-8").strip().splitlines()
        # Header + 25 rows = 26 lines
        self.assertEqual(len(lines), 26)

    def test_02_group_distribution(self):
        """Check group distribution: 5 base, 12 factors, 8 interactions."""
        base_files = list((self.data_dir / "base").glob("*.dzn"))
        factors_files = list((self.data_dir / "factors").glob("*.dzn"))
        interactions_files = list((self.data_dir / "interactions").glob("*.dzn"))

        self.assertEqual(len(base_files), 5)
        self.assertEqual(len(factors_files), 12)
        self.assertEqual(len(interactions_files), 8)

    def test_03_load_dzn_and_semantic_validation_for_all(self):
        """Check that all 25 instances load without error and pass validate_instance."""
        dzn_files = sorted(self.data_dir.rglob("*.dzn"))
        self.assertEqual(len(dzn_files), 25)

        for fpath in dzn_files:
            with self.subTest(instance=fpath.stem):
                inst = load_dzn(fpath, validate=True)
                errors = validate_instance(inst, raise_on_error=False)
                self.assertEqual(errors, [], f"Instance {fpath.stem} had validation errors: {errors}")

    def test_04_dimensions_and_modes_consistency(self):
        """Check dimensions: jobs, machines, total_operations, and 5 modes per op."""
        for cfg in INSTANCES_CONFIG:
            fpath = self.data_dir / cfg.group / f"{cfg.name}.dzn"
            with self.subTest(instance=cfg.name):
                inst = load_dzn(fpath, validate=False)
                self.assertEqual(inst.num_jobs, cfg.num_jobs)
                self.assertEqual(inst.num_machines, cfg.num_machines)
                self.assertEqual(inst.total_operations, cfg.num_jobs * cfg.num_machines)

                for job in inst.jobs:
                    self.assertEqual(len(job.operations), cfg.num_machines)
                    for op in job.operations:
                        self.assertEqual(len(op.modes), 5)
                        self.assertEqual(op.mode_ids, (1, 2, 3, 4, 5))

    def test_05_strictly_positive_durations(self):
        """Check that all processing mode durations are strictly positive integers."""
        for fpath in self.data_dir.rglob("*.dzn"):
            inst = load_dzn(fpath, validate=False)
            for op in inst.all_operations:
                for mode in op.modes:
                    self.assertGreater(mode.duration, 0, f"Mode duration <= 0 in {fpath.stem}")

    def test_06_non_negative_energy_values(self):
        """Check that all processing mode energy values are non-negative."""
        for fpath in self.data_dir.rglob("*.dzn"):
            inst = load_dzn(fpath, validate=False)
            for op in inst.all_operations:
                for mode in op.modes:
                    self.assertGreaterEqual(mode.energy, 0.0, f"Mode energy < 0 in {fpath.stem}")

    def test_07_valid_release_and_due_dates(self):
        """Check that release dates and due dates are non-negative."""
        for fpath in self.data_dir.rglob("*.dzn"):
            inst = load_dzn(fpath, validate=False)
            for op in inst.all_operations:
                self.assertGreaterEqual(op.release_date, 0, f"Negative release date in {fpath.stem}")
            for job in inst.jobs:
                self.assertGreaterEqual(job.due_date, 0, f"Negative due date in {fpath.stem}")

    def test_08_and_09_and_10_decoder_and_evaluator_produce_valid_objectives(self):
        """Check that each instance can be decoded and evaluated to valid (Cmax, T, E)."""
        for fpath in sorted(self.data_dir.rglob("*.dzn")):
            with self.subTest(instance=fpath.stem):
                inst = load_dzn(fpath, validate=True)
                sol = Solution.random(inst)
                schedule = self.decoder.decode(inst, sol)
                self.assertEqual(len(schedule.operations), inst.total_operations)

                obj_vals = self.evaluator.evaluate(inst, schedule)
                cmax, tard, energy = obj_vals.to_tuple()

                self.assertGreater(cmax, 0, f"Cmax <= 0 in {fpath.stem}")
                self.assertGreaterEqual(tard, 0, f"Tardiness < 0 in {fpath.stem}")
                self.assertGreater(energy, 0.0, f"Energy <= 0 in {fpath.stem}")

    def test_11_generation_is_reproducible_with_seed(self):
        """Check that running the generator with the same seed yields identical .dzn output."""
        cfg = InstanceConfig(
            name="test_repro", group="base", profile="test",
            num_jobs=8, num_machines=8, seed=4242
        )
        content_1, _ = generate_single_instance(cfg)
        content_2, _ = generate_single_instance(cfg)
        self.assertEqual(content_1, content_2, "Non-deterministic generation with identical seed!")


if __name__ == "__main__":
    unittest.main()

