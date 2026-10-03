"""Unit tests for Evaluator and ObjectiveValues."""

import random
import sys
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mojssp import (
    Decoder,
    Evaluator,
    Instance,
    Job,
    ObjectiveValues,
    Operation,
    ProcessingMode,
    Schedule,
    ScheduledOperation,
    Solution,
    evaluate,
    load_dzn,
)


class TestObjectiveValues(unittest.TestCase):
    """Tests for ObjectiveValues dataclass."""

    def test_creation_and_attributes(self) -> None:
        objs = ObjectiveValues(makespan=15, tardiness=4, energy=25.5)
        self.assertEqual(objs.makespan, 15)
        self.assertEqual(objs.tardiness, 4)
        self.assertEqual(objs.energy, 25.5)

    def test_immutability(self) -> None:
        objs = ObjectiveValues(makespan=10, tardiness=0, energy=20.0)
        with self.assertRaises(FrozenInstanceError):
            objs.makespan = 12  # type: ignore

    def test_tuple_unpacking(self) -> None:
        objs = ObjectiveValues(makespan=10, tardiness=2, energy=18.5)
        cmax, t, e = objs
        self.assertEqual(cmax, 10)
        self.assertEqual(t, 2)
        self.assertEqual(e, 18.5)

    def test_to_tuple(self) -> None:
        objs = ObjectiveValues(makespan=10, tardiness=2, energy=18.5)
        self.assertEqual(objs.to_tuple(), (10, 2, 18.5))

    def test_negative_values_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ObjectiveValues(makespan=-1, tardiness=0, energy=10.0)
        with self.assertRaises(ValueError):
            ObjectiveValues(makespan=10, tardiness=-1, energy=10.0)
        with self.assertRaises(ValueError):
            ObjectiveValues(makespan=10, tardiness=0, energy=-5.0)


class TestEvaluator(unittest.TestCase):
    """Tests for schedule evaluation against instances."""

    def setUp(self) -> None:
        mode = ProcessingMode(mode_id=1, duration=5, energy=10.0)
        op0 = Operation(job_id=0, op_id=0, machine_id=0, modes=(mode,))
        op1 = Operation(job_id=1, op_id=0, machine_id=1, modes=(mode,))

        # Job 0 due date = 8
        # Job 1 due date = 10
        self.job0 = Job(job_id=0, operations=(op0,), due_date=8)
        self.job1 = Job(job_id=1, operations=(op1,), due_date=10)
        self.instance = Instance(
            name="eval_test",
            num_jobs=2,
            num_machines=2,
            jobs=(self.job0, self.job1),
        )

        # Scheduled ops:
        # Job 0: starts at 0, completes at 10 (C_0 = 10, d_0 = 8 -> T_0 = 2, E = 6.0)
        # Job 1: starts at 0, completes at 7  (C_1 = 7,  d_1 = 10 -> T_1 = 0, E = 11.0)
        self.sched_op0 = ScheduledOperation(
            job_id=0,
            op_id=0,
            machine_id=0,
            mode_id=1,
            start=0,
            completion=10,
            duration=10,
            energy=6.0,
        )
        self.sched_op1 = ScheduledOperation(
            job_id=1,
            op_id=0,
            machine_id=1,
            mode_id=1,
            start=0,
            completion=7,
            duration=7,
            energy=11.0,
        )
        self.schedule = Schedule([self.sched_op0, self.sched_op1])
        self.evaluator = Evaluator()

    def test_hand_calculated_evaluation(self) -> None:
        # Cmax = max(10, 7) = 10
        # T = max(0, 10 - 8) + max(0, 7 - 10) = 2 + 0 = 2
        # E = 6.0 + 11.0 = 17.0
        objs = self.evaluator.evaluate(self.instance, self.schedule)

        self.assertEqual(objs.makespan, 10)
        self.assertEqual(objs.tardiness, 2)
        self.assertEqual(objs.energy, 17.0)

    def test_convenience_evaluate_function(self) -> None:
        objs = evaluate(self.instance, self.schedule)
        self.assertEqual(objs.makespan, 10)
        self.assertEqual(objs.tardiness, 2)
        self.assertEqual(objs.energy, 17.0)

    def test_zero_tardiness_when_early(self) -> None:
        # Both jobs finish well before due dates
        op0_early = ScheduledOperation(
            job_id=0, op_id=0, machine_id=0, mode_id=1, start=0, completion=5, duration=5, energy=5.0
        )
        op1_early = ScheduledOperation(
            job_id=1, op_id=0, machine_id=1, mode_id=1, start=0, completion=8, duration=8, energy=8.0
        )
        early_sched = Schedule([op0_early, op1_early])

        objs = evaluate(self.instance, early_sched)
        self.assertEqual(objs.tardiness, 0)
        self.assertEqual(objs.makespan, 8)
        self.assertEqual(objs.energy, 13.0)

    def test_all_jobs_tardy(self) -> None:
        # Job 0 finishes at 15 (d_0=8 -> T_0 = 7)
        # Job 1 finishes at 12 (d_1=10 -> T_1 = 2)
        # Total T = 9
        op0_late = ScheduledOperation(
            job_id=0, op_id=0, machine_id=0, mode_id=1, start=5, completion=15, duration=10, energy=4.0
        )
        op1_late = ScheduledOperation(
            job_id=1, op_id=0, machine_id=1, mode_id=1, start=2, completion=12, duration=10, energy=6.0
        )
        late_sched = Schedule([op0_late, op1_late])

        objs = evaluate(self.instance, late_sched)
        self.assertEqual(objs.makespan, 15)
        self.assertEqual(objs.tardiness, 9)
        self.assertEqual(objs.energy, 10.0)

    def test_empty_schedule(self) -> None:
        empty_sched = Schedule([])
        objs = evaluate(self.instance, empty_sched)

        self.assertEqual(objs.makespan, 0)
        self.assertEqual(objs.tardiness, 0)
        self.assertEqual(objs.energy, 0.0)

    def test_incompatible_schedule_job_raises(self) -> None:
        # Schedule has job_id=99 which does not exist in instance
        op_alien = ScheduledOperation(
            job_id=99, op_id=0, machine_id=0, mode_id=1, start=0, completion=5, duration=5, energy=2.0
        )
        alien_sched = Schedule([op_alien])

        with self.assertRaises(ValueError):
            evaluate(self.instance, alien_sched)

    def test_end_to_end_with_toy_dzn_and_decoder(self) -> None:
        toy_inst = load_dzn("data/validation/toy_instance.dzn")
        rng = random.Random(42)
        sol = Solution.random(toy_inst, rng=rng)

        decoder = Decoder()
        sched = decoder.decode(toy_inst, sol)

        objs = evaluate(toy_inst, sched)

        # Verify against direct manual sums from schedule
        expected_makespan = max(op.completion for op in sched.operations)
        expected_energy = sum(op.energy for op in sched.operations)
        expected_tardiness = sum(
            max(0, sched.get_job_completion_time(j.job_id) - j.due_date) for j in toy_inst.jobs
        )

        self.assertEqual(objs.makespan, expected_makespan)
        self.assertEqual(objs.energy, expected_energy)
        self.assertEqual(objs.tardiness, expected_tardiness)


if __name__ == "__main__":
    unittest.main()

