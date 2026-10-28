"""Unit tests for Solution representation in MO-JSSP (Subphase 2.1)."""

import random
import sys
import unittest
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mojssp.model.io import load_dzn
from mojssp.model.solution import Solution


class TestSolution(unittest.TestCase):
    """Test creation, validation, canonical mode mapping, and randomization of Solution."""

    def setUp(self):
        toy_path = Path(__file__).resolve().parent.parent / "data" / "validation" / "toy_instance.dzn"
        self.instance = load_dzn(toy_path)

    def test_valid_solution_creation(self):
        # 2 jobs, each with 2 operations -> total 4 operations
        sol = Solution(sequence=(1, 2, 1, 2), modes=(1, 2, 1, 2))
        sol.validate_with_instance(self.instance)
        self.assertEqual(sol.sequence, (1, 2, 1, 2))
        self.assertEqual(sol.modes, (1, 2, 1, 2))

    def test_solution_is_pure_genotype(self):
        # Solution must be purely genotypic and not have an objectives attribute
        sol = Solution(sequence=(1, 2, 1, 2), modes=(1, 2, 1, 2))
        self.assertFalse(hasattr(sol, "objectives"), "Solution must not contain an objectives attribute.")

    def test_solution_immutability(self):
        sol = Solution(sequence=(1, 2, 1, 2), modes=(1, 2, 1, 2))
        with self.assertRaises(AttributeError):
            sol.sequence = (2, 1, 2, 1)  # type: ignore
        with self.assertRaises(AttributeError):
            sol.modes = (2, 1, 2, 1)  # type: ignore

    def test_invalid_sequence_length_raises(self):
        sol = Solution(sequence=(1, 2, 1), modes=(1, 1, 1, 1))
        with self.assertRaises(ValueError) as ctx:
            sol.validate_with_instance(self.instance)
        self.assertIn("sequence length", str(ctx.exception))

    def test_invalid_modes_length_raises(self):
        sol = Solution(sequence=(1, 2, 1, 2), modes=(1, 1, 1))
        with self.assertRaises(ValueError) as ctx:
            sol.validate_with_instance(self.instance)
        self.assertIn("modes length", str(ctx.exception))

    def test_invalid_job_frequency_raises(self):
        # Job 1 appears 3 times, Job 2 appears 1 time (expected 2 and 2)
        sol = Solution(sequence=(1, 1, 1, 2), modes=(1, 1, 1, 1))
        with self.assertRaises(ValueError) as ctx:
            sol.validate_with_instance(self.instance)
        self.assertIn("Job 1 appears 3 times", str(ctx.exception))

    def test_invalid_mode_id_raises(self):
        # Mode 99 does not exist in any operation of the instance
        sol = Solution(sequence=(1, 2, 1, 2), modes=(1, 99, 1, 1))
        with self.assertRaises(ValueError) as ctx:
            sol.validate_with_instance(self.instance)
        self.assertIn("Mode 99 is not valid", str(ctx.exception))

    def test_canonical_mode_mapping(self):
        # instance.all_operations order:
        # 0: Job 1, Op 1
        # 1: Job 1, Op 2
        # 2: Job 2, Op 1
        # 3: Job 2, Op 2
        sol = Solution(sequence=(1, 2, 1, 2), modes=(1, 2, 2, 1))
        sol.validate_with_instance(self.instance)

        self.assertEqual(sol.get_mode_for_operation(1, 1, self.instance), 1)
        self.assertEqual(sol.get_mode_for_operation(1, 2, self.instance), 2)
        self.assertEqual(sol.get_mode_for_operation(2, 1, self.instance), 2)
        self.assertEqual(sol.get_mode_for_operation(2, 2, self.instance), 1)

    def test_get_mode_for_operation_nonexistent_raises(self):
        sol = Solution(sequence=(1, 2, 1, 2), modes=(1, 1, 1, 1))
        with self.assertRaises(IndexError):
            sol.get_mode_for_operation(99, 1, self.instance)

    def test_random_solution_generation_and_reproducibility(self):
        rng1 = random.Random(12345)
        sol1 = Solution.random(self.instance, rng=rng1)
        sol1.validate_with_instance(self.instance)

        # Reproducibility with same seed
        rng2 = random.Random(12345)
        sol2 = Solution.random(self.instance, rng=rng2)
        self.assertEqual(sol1.sequence, sol2.sequence)
        self.assertEqual(sol1.modes, sol2.modes)

        # Default random (without seed) produces a valid solution
        sol3 = Solution.random(self.instance)
        sol3.validate_with_instance(self.instance)


if __name__ == "__main__":
    unittest.main()
