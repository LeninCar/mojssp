"""Unit tests for independent ScheduleValidator (Subphase 2.5)."""

import random
import sys
import unittest
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mojssp import (
    Decoder,
    Instance,
    Job,
    Operation,
    ProcessingMode,
    Schedule,
    ScheduledOperation,
    ScheduleValidationError,
    ScheduleValidator,
    Solution,
    load_dzn,
    validate_schedule,
)


class TestScheduleValidator(unittest.TestCase):
    """Test suite for independent ScheduleValidator auditing."""

    def setUp(self) -> None:
        # Build standard 2-job, 2-machine instance
        # Job 0:
        #   Op 0: M0, modes: [(1, dur=3, energy=5.0), (2, dur=2, energy=8.0)], r=0
        #   Op 1: M1, modes: [(1, dur=4, energy=6.0)], r=0
        # Job 1:
        #   Op 0: M1, modes: [(1, dur=5, energy=10.0), (2, dur=3, energy=15.0)], r=2
        #   Op 1: M0, modes: [(1, dur=2, energy=4.0)], r=0
        self.mode0_0_1 = ProcessingMode(mode_id=1, duration=3, energy=5.0)
        self.mode0_0_2 = ProcessingMode(mode_id=2, duration=2, energy=8.0)
        self.op0_0 = Operation(
            job_id=0, op_id=0, machine_id=0, modes=(self.mode0_0_1, self.mode0_0_2), release_date=0
        )
        self.mode0_1_1 = ProcessingMode(mode_id=1, duration=4, energy=6.0)
        self.op0_1 = Operation(job_id=0, op_id=1, machine_id=1, modes=(self.mode0_1_1,), release_date=0)
        self.job0 = Job(job_id=0, operations=(self.op0_0, self.op0_1), due_date=15)

        self.mode1_0_1 = ProcessingMode(mode_id=1, duration=5, energy=10.0)
        self.mode1_0_2 = ProcessingMode(mode_id=2, duration=3, energy=15.0)
        self.op1_0 = Operation(
            job_id=1, op_id=0, machine_id=1, modes=(self.mode1_0_1, self.mode1_0_2), release_date=2
        )
        self.mode1_1_1 = ProcessingMode(mode_id=1, duration=2, energy=4.0)
        self.op1_1 = Operation(job_id=1, op_id=1, machine_id=0, modes=(self.mode1_1_1,), release_date=0)
        self.job1 = Job(job_id=1, operations=(self.op1_0, self.op1_1), due_date=15)

        self.instance = Instance(
            name="val_test",
            num_jobs=2,
            num_machines=2,
            jobs=(self.job0, self.job1),
        )

        # Build a known valid schedule:
        # J0-O0 (M0, mode 1, dur 3, energy 5.0, r=0): [0, 3]
        # J0-O1 (M1, mode 1, dur 4, energy 6.0, r=0): [5, 9]
        # J1-O0 (M1, mode 2, dur 3, energy 15.0, r=2): [2, 5]
        # J1-O1 (M0, mode 1, dur 2, energy 4.0, r=0): [5, 7]
        self.valid_op0_0 = ScheduledOperation(
            job_id=0,
            op_id=0,
            machine_id=0,
            mode_id=1,
            start=0,
            completion=3,
            duration=3,
            energy=5.0,
            release_date=0,
        )
        self.valid_op0_1 = ScheduledOperation(
            job_id=0,
            op_id=1,
            machine_id=1,
            mode_id=1,
            start=5,
            completion=9,
            duration=4,
            energy=6.0,
            release_date=0,
        )
        self.valid_op1_0 = ScheduledOperation(
            job_id=1,
            op_id=0,
            machine_id=1,
            mode_id=2,
            start=2,
            completion=5,
            duration=3,
            energy=15.0,
            release_date=2,
        )
        self.valid_op1_1 = ScheduledOperation(
            job_id=1,
            op_id=1,
            machine_id=0,
            mode_id=1,
            start=5,
            completion=7,
            duration=2,
            energy=4.0,
            release_date=0,
        )
        self.valid_schedule = Schedule(
            [
                self.valid_op0_0,
                self.valid_op0_1,
                self.valid_op1_0,
                self.valid_op1_1,
            ]
        )
        self.validator = ScheduleValidator()

    def test_valid_schedule_passes(self) -> None:
        errors = self.validator.validate(self.instance, self.valid_schedule)
        self.assertEqual(errors, [])

    def test_convenience_validate_schedule_function(self) -> None:
        errors = validate_schedule(self.instance, self.valid_schedule)
        self.assertEqual(errors, [])

    def test_decoded_random_solution_passes(self) -> None:
        toy_inst = load_dzn("data/validation/toy_instance.dzn")
        rng = random.Random(123)
        sol = Solution.random(toy_inst, rng=rng)
        sched = Decoder().decode(toy_inst, sol)

        errors = validate_schedule(toy_inst, sched)
        self.assertEqual(errors, [])

    def test_missing_operation_fails(self) -> None:
        # Schedule with only 3 operations instead of 4
        partial_sched = Schedule([self.valid_op0_0, self.valid_op0_1, self.valid_op1_0])
        errors = self.validator.validate(self.instance, partial_sched, raise_on_error=False)

        self.assertTrue(any("Missing operation" in e for e in errors))
        with self.assertRaises(ScheduleValidationError):
            self.validator.validate(self.instance, partial_sched, raise_on_error=True)

    def test_additional_unexpected_operation_fails(self) -> None:
        extra_op = ScheduledOperation(
            job_id=0, op_id=2, machine_id=0, mode_id=1, start=10, completion=12, duration=2, energy=3.0
        )
        sched = Schedule([self.valid_op0_0, self.valid_op0_1, self.valid_op1_0, self.valid_op1_1, extra_op])
        errors = self.validator.validate(self.instance, sched, raise_on_error=False)

        self.assertTrue(any("Unexpected operation" in e for e in errors))
        self.assertTrue(any("Operation count mismatch" in e for e in errors))

    def test_invalid_job_id_fails(self) -> None:
        alien_op = ScheduledOperation(
            job_id=99, op_id=0, machine_id=0, mode_id=1, start=0, completion=2, duration=2, energy=2.0
        )
        sched = Schedule([self.valid_op0_0, self.valid_op0_1, self.valid_op1_0, alien_op])
        errors = self.validator.validate(self.instance, sched, raise_on_error=False)

        self.assertTrue(any("Unexpected operation" in e for e in errors))

    def test_wrong_machine_assignment_fails(self) -> None:
        # Op (0,0) is supposed to be on machine 0, but scheduled on machine 1
        wrong_mach_op = ScheduledOperation(
            job_id=0, op_id=0, machine_id=1, mode_id=1, start=10, completion=13, duration=3, energy=5.0
        )
        sched = Schedule([wrong_mach_op, self.valid_op0_1, self.valid_op1_0, self.valid_op1_1])
        errors = self.validator.validate(self.instance, sched, raise_on_error=False)

        self.assertTrue(any("Machine mismatch" in e for e in errors))

    def test_invalid_mode_id_fails(self) -> None:
        # Op (0,1) only allows mode 1; assign mode 99
        wrong_mode_op = ScheduledOperation(
            job_id=0, op_id=1, machine_id=1, mode_id=99, start=5, completion=9, duration=4, energy=6.0
        )
        sched = Schedule([self.valid_op0_0, wrong_mode_op, self.valid_op1_0, self.valid_op1_1])
        errors = self.validator.validate(self.instance, sched, raise_on_error=False)

        self.assertTrue(any("Invalid mode" in e for e in errors))

    def test_duration_mismatch_fails(self) -> None:
        # Op (0,0) under mode 1 should have duration 3, but scheduled with duration 5
        wrong_dur_op = ScheduledOperation(
            job_id=0, op_id=0, machine_id=0, mode_id=1, start=0, completion=5, duration=5, energy=5.0
        )
        sched = Schedule([wrong_dur_op, self.valid_op0_1, self.valid_op1_0, self.valid_op1_1])
        errors = self.validator.validate(self.instance, sched, raise_on_error=False)

        self.assertTrue(any("Duration mismatch" in e for e in errors))

    def test_energy_mismatch_fails(self) -> None:
        # Op (0,0) under mode 1 should have energy 5.0, but scheduled with energy 99.0
        wrong_energy_op = ScheduledOperation(
            job_id=0, op_id=0, machine_id=0, mode_id=1, start=0, completion=3, duration=3, energy=99.0
        )
        sched = Schedule([wrong_energy_op, self.valid_op0_1, self.valid_op1_0, self.valid_op1_1])
        errors = self.validator.validate(self.instance, sched, raise_on_error=False)

        self.assertTrue(any("Energy mismatch" in e for e in errors))

    def test_release_date_violation_fails(self) -> None:
        # Op (1,0) has release_date = 2 in instance. Schedule with start = 1 (and release_date=1)
        early_op = ScheduledOperation(
            job_id=1,
            op_id=0,
            machine_id=1,
            mode_id=2,
            start=1,
            completion=4,
            duration=3,
            energy=15.0,
            release_date=1,
        )
        sched = Schedule([self.valid_op0_0, self.valid_op0_1, early_op, self.valid_op1_1])
        errors = self.validator.validate(self.instance, sched, raise_on_error=False)

        self.assertTrue(any("Release date violation" in e or "Release date mismatch" in e for e in errors))

    def test_technological_precedence_violation_fails(self) -> None:
        # J0-O0 completes at 3. Make J0-O1 start at 2 (before J0-O0 completes)
        premature_op0_1 = ScheduledOperation(
            job_id=0, op_id=1, machine_id=1, mode_id=1, start=2, completion=6, duration=4, energy=6.0
        )
        # Shift J1-O0 so it doesn't overlap machine 1 [6, 9]
        shift_op1_0 = ScheduledOperation(
            job_id=1,
            op_id=0,
            machine_id=1,
            mode_id=2,
            start=6,
            completion=9,
            duration=3,
            energy=15.0,
            release_date=2,
        )
        sched = Schedule([self.valid_op0_0, premature_op0_1, shift_op1_0, self.valid_op1_1])
        errors = self.validator.validate(self.instance, sched, raise_on_error=False)

        self.assertTrue(any("Technological precedence violation" in e for e in errors))

    def test_machine_overlap_fails(self) -> None:
        # Machine 1 has J1-O0 [2, 5]. Make J0-O1 start at 4: [4, 8] -> overlap!
        overlap_op0_1 = ScheduledOperation(
            job_id=0, op_id=1, machine_id=1, mode_id=1, start=4, completion=8, duration=4, energy=6.0
        )
        sched = Schedule([self.valid_op0_0, overlap_op0_1, self.valid_op1_0, self.valid_op1_1])
        errors = self.validator.validate(self.instance, sched, raise_on_error=False)

        self.assertTrue(any("Machine 1 overlap" in e for e in errors))

    def test_boundary_touch_passes(self) -> None:
        # Machine 1: J1-O0 is [2, 5]. J0-O1 is [5, 9].
        # Exact boundary match: start_b == completion_a (5 == 5)
        # This is the valid_schedule itself:
        errors = self.validator.validate(self.instance, self.valid_schedule)
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
