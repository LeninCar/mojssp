"""Unit tests for I/O operations (loading from MiniZinc .dzn data files)."""

import sys
import tempfile
import unittest
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mojssp.model.io import load_dzn


class TestIO(unittest.TestCase):
    """Test loading .dzn files and mapping to MO-JSSP domain model."""

    def setUp(self):
        self.toy_dzn_path = Path(__file__).resolve().parent.parent / "data" / "validation" / "toy_instance.dzn"

    def test_load_toy_dzn(self):
        self.assertTrue(self.toy_dzn_path.exists(), f"File {self.toy_dzn_path} must exist.")
        inst = load_dzn(self.toy_dzn_path, validate=True)

        self.assertEqual(inst.name, "toy_instance")
        self.assertEqual(inst.num_jobs, 2)
        self.assertEqual(inst.num_machines, 2)
        self.assertEqual(inst.total_operations, 4)

        # Check Job 1 precedence order: M1 first (prec=0), M2 second (prec=1)
        job1 = inst.jobs[0]
        self.assertEqual(job1.job_id, 1)
        self.assertEqual(job1.due_date, 10)  # d_1 = 10
        self.assertEqual(job1.num_operations, 2)
        self.assertEqual(job1.operations[0].op_id, 1)
        self.assertEqual(job1.operations[0].machine_id, 1)
        self.assertEqual(job1.operations[1].op_id, 2)
        self.assertEqual(job1.operations[1].machine_id, 2)

        # Check Job 2 precedence order: M2 first (prec=0), M1 second (prec=1)
        job2 = inst.jobs[1]
        self.assertEqual(job2.job_id, 2)
        self.assertEqual(job2.due_date, 10)  # d_2 = 10
        self.assertEqual(job2.num_operations, 2)
        self.assertEqual(job2.operations[0].op_id, 1)
        self.assertEqual(job2.operations[0].machine_id, 2)
        self.assertEqual(job2.operations[1].op_id, 2)
        self.assertEqual(job2.operations[1].machine_id, 1)

        # Check Job 1 Op 1 speed modes:
        # time: 5 (speed 1), 3 (speed 2)
        # energy: 10 (speed 1), 20 (speed 2)
        op1_1 = job1.operations[0]
        self.assertEqual(len(op1_1.modes), 2)
        m1 = op1_1.get_mode(1)
        self.assertEqual(m1.duration, 5)
        self.assertEqual(m1.energy, 10.0)

        m2 = op1_1.get_mode(2)
        self.assertEqual(m2.duration, 3)
        self.assertEqual(m2.energy, 20.0)

        # Check release dates
        self.assertEqual(op1_1.release_date, 0)

    def test_load_malformed_dzn(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            bad_dzn = Path(tmp_dir) / "bad.dzn"
            bad_dzn.write_text("JOBS = 1..2;\nMACHINES = 1..2;\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_dzn(bad_dzn)


if __name__ == "__main__":
    unittest.main()
