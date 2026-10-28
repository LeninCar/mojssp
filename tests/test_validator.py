"""Unit tests for semantic and constraint validation of MO-JSSP instances."""

import sys
import unittest
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mojssp.model.mode import ProcessingMode
from mojssp.model.operation import Operation
from mojssp.model.job import Job
from mojssp.model.instance import Instance
from mojssp.model.validator import validate_instance, ValidationError


class TestValidator(unittest.TestCase):
    """Test validation rules for valid and invalid instances."""

    def _make_valid_instance(self) -> Instance:
        op1_1 = Operation(
            job_id=1,
            op_id=1,
            machine_id=1,
            modes=(ProcessingMode(mode_id=1, duration=5, energy=10.0),),
            release_date=0,
        )
        op1_2 = Operation(
            job_id=1,
            op_id=2,
            machine_id=2,
            modes=(ProcessingMode(mode_id=1, duration=6, energy=15.0),),
            release_date=0,
        )
        job1 = Job(job_id=1, operations=(op1_1, op1_2), due_date=10)

        op2_1 = Operation(
            job_id=2,
            op_id=1,
            machine_id=2,
            modes=(ProcessingMode(mode_id=1, duration=4, energy=10.0),),
            release_date=0,
        )
        op2_2 = Operation(
            job_id=2,
            op_id=2,
            machine_id=1,
            modes=(ProcessingMode(mode_id=1, duration=7, energy=18.0),),
            release_date=0,
        )
        job2 = Job(job_id=2, operations=(op2_1, op2_2), due_date=10)

        return Instance(
            name="valid_test",
            num_jobs=2,
            num_machines=2,
            jobs=(job1, job2),
        )

    def test_valid_instance_passes(self):
        inst = self._make_valid_instance()
        errors = validate_instance(inst, raise_on_error=True)
        self.assertEqual(len(errors), 0)

    def test_invalid_machine_out_of_bounds(self):
        op1 = Operation(
            job_id=1,
            op_id=1,
            machine_id=5,  # Machine 5 is out of bounds for num_machines=2
            modes=(ProcessingMode(mode_id=1, duration=5, energy=10.0),),
        )
        job1 = Job(job_id=1, operations=(op1,), due_date=10)
        inst = Instance(name="bad_mach", num_jobs=1, num_machines=2, jobs=(job1,))
        with self.assertRaises(ValidationError) as ctx:
            validate_instance(inst, raise_on_error=True)
        self.assertTrue(any("out of bounds" in err for err in ctx.exception.errors))

    def test_duplicate_op_id_in_job(self):
        op1 = Operation(
            job_id=1,
            op_id=1,
            machine_id=1,
            modes=(ProcessingMode(mode_id=1, duration=5, energy=10.0),),
        )
        op2 = Operation(
            job_id=1,
            op_id=1,  # Duplicate op_id 1
            machine_id=2,
            modes=(ProcessingMode(mode_id=1, duration=4, energy=12.0),),
        )
        job1 = Job(job_id=1, operations=(op1, op2), due_date=10)
        inst = Instance(name="dup_op", num_jobs=1, num_machines=2, jobs=(job1,))
        with self.assertRaises(ValidationError) as ctx:
            validate_instance(inst, raise_on_error=True)
        self.assertTrue(any("Duplicate op_id" in err for err in ctx.exception.errors))

    def test_duplicate_mode_id_in_operation(self):
        m1 = ProcessingMode(mode_id=1, duration=5, energy=10.0)
        m2 = ProcessingMode(mode_id=1, duration=3, energy=20.0)  # Duplicate mode_id 1
        op = Operation(job_id=1, op_id=1, machine_id=1, modes=(m1, m2))
        job1 = Job(job_id=1, operations=(op,), due_date=10)
        inst = Instance(name="dup_mode", num_jobs=1, num_machines=1, jobs=(job1,))
        with self.assertRaises(ValidationError) as ctx:
            validate_instance(inst, raise_on_error=True)
        self.assertTrue(any("duplicate mode_id" in err for err in ctx.exception.errors))

    def test_negative_release_date_rejected(self):
        with self.assertRaises(ValueError):
            Operation(
                job_id=1,
                op_id=1,
                machine_id=1,
                modes=(ProcessingMode(mode_id=1, duration=5, energy=10.0),),
                release_date=-2,
            )

    def test_negative_due_date_rejected(self):
        op = Operation(
            job_id=1,
            op_id=1,
            machine_id=1,
            modes=(ProcessingMode(mode_id=1, duration=5, energy=10.0),),
        )
        with self.assertRaises(ValueError):
            Job(job_id=1, operations=(op,), due_date=-1)


if __name__ == "__main__":
    unittest.main()
