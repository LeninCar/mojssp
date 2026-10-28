"""Unit tests for MO-JSSP domain entities (ProcessingMode, Operation, Job, Instance)."""

import sys
import unittest
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mojssp.model.mode import ProcessingMode
from mojssp.model.operation import Operation
from mojssp.model.job import Job
from mojssp.model.instance import Instance


class TestInstanceEntities(unittest.TestCase):
    """Test behavior, validation, and properties of ProcessingMode, Operation, Job, and Instance."""

    def test_processing_mode_valid(self):
        mode = ProcessingMode(mode_id=1, duration=5, energy=10.5)
        self.assertEqual(mode.mode_id, 1)
        self.assertEqual(mode.duration, 5)
        self.assertEqual(mode.energy, 10.5)

    def test_processing_mode_invalid_duration(self):
        with self.assertRaises(ValueError):
            ProcessingMode(mode_id=1, duration=0, energy=10.0)
        with self.assertRaises(ValueError):
            ProcessingMode(mode_id=1, duration=-2, energy=10.0)

    def test_processing_mode_invalid_energy(self):
        with self.assertRaises(ValueError):
            ProcessingMode(mode_id=1, duration=5, energy=-0.5)

    def test_operation_creation_and_mode_lookup(self):
        m1 = ProcessingMode(mode_id=1, duration=5, energy=10.0)
        m2 = ProcessingMode(mode_id=2, duration=3, energy=20.0)
        op = Operation(
            job_id=1,
            op_id=1,
            machine_id=2,
            modes=(m1, m2),
            release_date=1,
        )
        self.assertEqual(op.job_id, 1)
        self.assertEqual(op.op_id, 1)
        self.assertEqual(op.machine_id, 2)
        self.assertEqual(op.mode_ids, (1, 2))
        self.assertEqual(op.get_mode(1), m1)
        self.assertEqual(op.get_mode(2), m2)
        self.assertEqual(op.release_date, 1)

    def test_operation_missing_mode_lookup(self):
        m1 = ProcessingMode(mode_id=1, duration=5, energy=10.0)
        op = Operation(job_id=1, op_id=1, machine_id=1, modes=(m1,))
        with self.assertRaises(KeyError):
            op.get_mode(99)

    def test_operation_empty_modes(self):
        with self.assertRaises(ValueError):
            Operation(job_id=1, op_id=1, machine_id=1, modes=())

    def test_job_creation_and_properties(self):
        m1 = ProcessingMode(mode_id=1, duration=5, energy=10.0)
        m2 = ProcessingMode(mode_id=2, duration=3, energy=20.0)
        op1 = Operation(job_id=1, op_id=1, machine_id=1, modes=(m1, m2))
        op2 = Operation(job_id=1, op_id=2, machine_id=2, modes=(m1,))

        job = Job(job_id=1, operations=(op1, op2), due_date=15)
        self.assertEqual(job.job_id, 1)
        self.assertEqual(job.due_date, 15)
        self.assertEqual(job.num_operations, 2)
        self.assertEqual(job.last_operation, op2)
        self.assertEqual(job.get_operation(1), op1)
        self.assertEqual(job.get_operation(2), op2)

    def test_job_invalid_due_date(self):
        m1 = ProcessingMode(mode_id=1, duration=5, energy=10.0)
        op1 = Operation(job_id=1, op_id=1, machine_id=1, modes=(m1,))
        with self.assertRaises(ValueError):
            Job(job_id=1, operations=(op1,), due_date=-5)

    def test_job_empty_operations(self):
        with self.assertRaises(ValueError):
            Job(job_id=1, operations=(), due_date=10)

    def test_job_mismatched_op_job_id(self):
        m1 = ProcessingMode(mode_id=1, duration=5, energy=10.0)
        op1 = Operation(job_id=2, op_id=1, machine_id=1, modes=(m1,))
        with self.assertRaises(ValueError):
            Job(job_id=1, operations=(op1,), due_date=10)

    def test_instance_structure_and_queries(self):
        # Job 1: Op 1 (M1: dur 5/3, en 10/20), Op 2 (M2: dur 6/4, en 15/25)
        op1_1 = Operation(
            job_id=1,
            op_id=1,
            machine_id=1,
            modes=(
                ProcessingMode(mode_id=1, duration=5, energy=10.0),
                ProcessingMode(mode_id=2, duration=3, energy=20.0),
            ),
        )
        op1_2 = Operation(
            job_id=1,
            op_id=2,
            machine_id=2,
            modes=(
                ProcessingMode(mode_id=1, duration=6, energy=15.0),
                ProcessingMode(mode_id=2, duration=4, energy=25.0),
            ),
        )
        job1 = Job(job_id=1, operations=(op1_1, op1_2), due_date=10)

        # Job 2: Op 1 (M2: dur 4/2, en 10/20), Op 2 (M1: dur 7/5, en 18/28)
        op2_1 = Operation(
            job_id=2,
            op_id=1,
            machine_id=2,
            modes=(
                ProcessingMode(mode_id=1, duration=4, energy=10.0),
                ProcessingMode(mode_id=2, duration=2, energy=20.0),
            ),
        )
        op2_2 = Operation(
            job_id=2,
            op_id=2,
            machine_id=1,
            modes=(
                ProcessingMode(mode_id=1, duration=7, energy=18.0),
                ProcessingMode(mode_id=2, duration=5, energy=28.0),
            ),
        )
        job2 = Job(job_id=2, operations=(op2_1, op2_2), due_date=10)

        inst = Instance(
            name="test_inst",
            num_jobs=2,
            num_machines=2,
            jobs=(job1, job2),
        )

        self.assertEqual(inst.num_jobs, 2)
        self.assertEqual(inst.num_machines, 2)
        self.assertEqual(inst.total_operations, 4)
        self.assertEqual(len(inst.all_operations), 4)

        # Operations per machine
        m1_ops = inst.get_operations_for_machine(1)
        self.assertEqual(len(m1_ops), 2)
        self.assertIn(op1_1, m1_ops)
        self.assertIn(op2_2, m1_ops)

        m2_ops = inst.get_operations_for_machine(2)
        self.assertEqual(len(m2_ops), 2)
        self.assertIn(op1_2, m2_ops)
        self.assertIn(op2_1, m2_ops)

        # Direct access queries
        self.assertEqual(inst.get_job(1), job1)
        self.assertEqual(inst.get_job(2), job2)
        self.assertEqual(inst.get_operation(1, 1), op1_1)
        self.assertEqual(inst.get_operation(2, 2), op2_2)

        # Out of bounds access
        with self.assertRaises(IndexError):
            inst.get_job(99)
        with self.assertRaises(IndexError):
            inst.get_operation(1, 99)


if __name__ == "__main__":
    unittest.main()
