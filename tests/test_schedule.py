"""Unit tests for ScheduledOperation and Schedule (phenotype representation)."""

import sys
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mojssp import Schedule, ScheduledOperation



class TestScheduledOperation(unittest.TestCase):
    """Tests for ScheduledOperation immutability and invariants."""

    def test_valid_scheduled_operation(self) -> None:
        op = ScheduledOperation(
            job_id=0,
            op_id=0,
            machine_id=1,
            mode_id=2,
            start=5,
            completion=8,
            duration=3,
            energy=6.0,
            release_date=4,
        )
        self.assertEqual(op.job_id, 0)
        self.assertEqual(op.op_id, 0)
        self.assertEqual(op.machine_id, 1)
        self.assertEqual(op.mode_id, 2)
        self.assertEqual(op.start, 5)
        self.assertEqual(op.completion, 8)
        self.assertEqual(op.duration, 3)
        self.assertEqual(op.energy, 6.0)
        self.assertEqual(op.release_date, 4)

    def test_immutability(self) -> None:
        op = ScheduledOperation(
            job_id=0,
            op_id=0,
            machine_id=1,
            mode_id=1,
            start=0,
            completion=4,
            duration=4,
            energy=5.0,
        )
        with self.assertRaises(FrozenInstanceError):
            op.start = 2  # type: ignore

    def test_inconsistent_completion(self) -> None:
        with self.assertRaises(ValueError):
            ScheduledOperation(
                job_id=0,
                op_id=0,
                machine_id=1,
                mode_id=1,
                start=2,
                completion=10,  # should be 2 + 5 = 7
                duration=5,
                energy=5.0,
            )

    def test_invalid_duration(self) -> None:
        with self.assertRaises(ValueError):
            ScheduledOperation(
                job_id=0,
                op_id=0,
                machine_id=1,
                mode_id=1,
                start=0,
                completion=0,
                duration=0,
                energy=5.0,
            )

    def test_start_before_release_date(self) -> None:
        with self.assertRaises(ValueError):
            ScheduledOperation(
                job_id=0,
                op_id=0,
                machine_id=1,
                mode_id=1,
                start=3,
                completion=7,
                duration=4,
                energy=5.0,
                release_date=5,  # release_date > start
            )

    def test_negative_values(self) -> None:
        with self.assertRaises(ValueError):
            ScheduledOperation(
                job_id=-1,
                op_id=0,
                machine_id=1,
                mode_id=1,
                start=0,
                completion=2,
                duration=2,
                energy=1.0,
            )
        with self.assertRaises(ValueError):
            ScheduledOperation(
                job_id=0,
                op_id=0,
                machine_id=1,
                mode_id=1,
                start=0,
                completion=2,
                duration=2,
                energy=-1.0,
            )


class TestSchedule(unittest.TestCase):
    """Tests for Schedule phenotype collection and query methods."""

    def setUp(self) -> None:
        self.op0_0 = ScheduledOperation(
            job_id=0,
            op_id=0,
            machine_id=0,
            mode_id=1,
            start=0,
            completion=3,
            duration=3,
            energy=6.0,
        )
        self.op0_1 = ScheduledOperation(
            job_id=0,
            op_id=1,
            machine_id=1,
            mode_id=1,
            start=3,
            completion=5,
            duration=2,
            energy=4.0,
        )
        self.op1_0 = ScheduledOperation(
            job_id=1,
            op_id=0,
            machine_id=1,
            mode_id=2,
            start=5,
            completion=9,
            duration=4,
            energy=7.0,
        )
        self.op1_1 = ScheduledOperation(
            job_id=1,
            op_id=1,
            machine_id=0,
            mode_id=1,
            start=9,
            completion=11,
            duration=2,
            energy=3.0,
        )
        self.schedule = Schedule([self.op0_0, self.op0_1, self.op1_0, self.op1_1])

    def test_schedule_immutability(self) -> None:
        with self.assertRaises(FrozenInstanceError):
            self.schedule.operations = ()  # type: ignore

    def test_duplicate_operations_rejected(self) -> None:
        duplicate_op = ScheduledOperation(
            job_id=0,
            op_id=0,
            machine_id=1,
            mode_id=2,
            start=10,
            completion=12,
            duration=2,
            energy=3.0,
        )
        with self.assertRaises(ValueError):
            Schedule([self.op0_0, duplicate_op])

    def test_get_operations_by_job(self) -> None:
        ops_j0 = self.schedule.get_operations_by_job(0)
        self.assertEqual(len(ops_j0), 2)
        self.assertEqual(ops_j0[0].op_id, 0)
        self.assertEqual(ops_j0[1].op_id, 1)

        # Non-existent job
        self.assertEqual(self.schedule.get_operations_by_job(99), ())

    def test_get_operations_by_machine(self) -> None:
        ops_m1 = self.schedule.get_operations_by_machine(1)
        self.assertEqual(len(ops_m1), 2)
        # Ordered by start time
        self.assertEqual(ops_m1[0].start, 3)
        self.assertEqual(ops_m1[1].start, 5)

        # Non-existent machine
        self.assertEqual(self.schedule.get_operations_by_machine(99), ())

    def test_job_completion_times(self) -> None:
        self.assertEqual(self.schedule.get_job_completion_time(0), 5)
        self.assertEqual(self.schedule.get_job_completion_time(1), 11)
        self.assertEqual(self.schedule.job_completion_times, {0: 5, 1: 11})

        with self.assertRaises(KeyError):
            self.schedule.get_job_completion_time(99)

    def test_makespan_and_num_operations(self) -> None:
        self.assertEqual(self.schedule.num_operations, 4)
        self.assertEqual(self.schedule.makespan, 11)
        self.assertEqual(set(self.schedule.job_ids), {0, 1})
        self.assertEqual(set(self.schedule.machine_ids), {0, 1})

    def test_empty_schedule(self) -> None:
        empty = Schedule([])
        self.assertEqual(empty.num_operations, 0)
        self.assertEqual(empty.makespan, 0)
        self.assertEqual(empty.job_ids, ())
        self.assertEqual(empty.machine_ids, ())
        self.assertEqual(empty.job_completion_times, {})
        with self.assertRaises(KeyError):
            empty.get_job_completion_time(0)


if __name__ == "__main__":
    unittest.main()

