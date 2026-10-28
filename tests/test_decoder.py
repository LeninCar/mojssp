"""Unit tests for Serial List-Based Decoder."""

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
    Solution,
    decode,
    load_dzn,
)


class TestDecoder(unittest.TestCase):
    """Test suite for the Serial List-Based Decoder."""

    def setUp(self) -> None:
        # Build a controlled 2-job, 2-machine instance
        # Job 0:
        #   Op 0: machine 0, modes: [(1, dur=3, energy=5.0), (2, dur=2, energy=8.0)], r=0
        #   Op 1: machine 1, modes: [(1, dur=4, energy=6.0)], r=0
        # Job 1:
        #   Op 0: machine 1, modes: [(1, dur=5, energy=10.0), (2, dur=3, energy=15.0)], r=2
        #   Op 1: machine 0, modes: [(1, dur=2, energy=4.0)], r=0
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
            name="test_inst",
            num_jobs=2,
            num_machines=2,
            jobs=(self.job0, self.job1),
        )

        # Canonical all_operations order:
        # 0: (0, 0), 1: (0, 1), 2: (1, 0), 3: (1, 1)
        self.decoder = Decoder()

    def test_basic_decoding_and_num_operations(self) -> None:
        # Sequence: J0-O0, J1-O0, J0-O1, J1-O1
        # Modes: (0,0)->1, (0,1)->1, (1,0)->2, (1,1)->1
        sol = Solution(sequence=(0, 1, 0, 1), modes=(1, 1, 2, 1))
        sched = self.decoder.decode(self.instance, sol)

        self.assertIsInstance(sched, Schedule)
        self.assertEqual(sched.num_operations, 4)

    def test_job_appearances_and_mode_mapping(self) -> None:
        sol = Solution(sequence=(0, 1, 0, 1), modes=(1, 1, 2, 1))
        sched = self.decoder.decode(self.instance, sol)

        # Verify operations
        ops_j0 = sched.get_operations_by_job(0)
        ops_j1 = sched.get_operations_by_job(1)

        self.assertEqual(len(ops_j0), 2)
        self.assertEqual(len(ops_j1), 2)

        # Op (0,0): mode 1 -> dur 3, energy 5.0
        self.assertEqual(ops_j0[0].op_id, 0)
        self.assertEqual(ops_j0[0].mode_id, 1)
        self.assertEqual(ops_j0[0].duration, 3)
        self.assertEqual(ops_j0[0].energy, 5.0)

        # Op (0,1): mode 1 -> dur 4, energy 6.0
        self.assertEqual(ops_j0[1].op_id, 1)
        self.assertEqual(ops_j0[1].mode_id, 1)
        self.assertEqual(ops_j0[1].duration, 4)
        self.assertEqual(ops_j0[1].energy, 6.0)

        # Op (1,0): mode 2 -> dur 3, energy 15.0
        self.assertEqual(ops_j1[0].op_id, 0)
        self.assertEqual(ops_j1[0].mode_id, 2)
        self.assertEqual(ops_j1[0].duration, 3)
        self.assertEqual(ops_j1[0].energy, 15.0)

        # Op (1,1): mode 1 -> dur 2, energy 4.0
        self.assertEqual(ops_j1[1].op_id, 1)
        self.assertEqual(ops_j1[1].mode_id, 1)
        self.assertEqual(ops_j1[1].duration, 2)
        self.assertEqual(ops_j1[1].energy, 4.0)

    def test_hand_calculated_timeline_delays(self) -> None:
        # Step-by-step trace:
        # 1. J0-O0 (M0, dur 3): start=max(0,0,0)=0, comp=3.
        # 2. J1-O0 (M1, dur 3, r=2): start=max(0,0,2)=2, comp=5.
        # 3. J0-O1 (M1, dur 4): c_prev=3, mach1_avail=5 -> start=max(3,5,0)=5, comp=9.
        #    (Delayed by machine availability!)
        # 4. J1-O1 (M0, dur 2): c_prev=5, mach0_avail=3 -> start=max(5,3,0)=5, comp=7.
        #    (Delayed by technological precedence!)
        sol = Solution(sequence=(0, 1, 0, 1), modes=(1, 1, 2, 1))
        sched = decode(self.instance, sol)

        op0_0 = sched.get_operations_by_job(0)[0]
        op0_1 = sched.get_operations_by_job(0)[1]
        op1_0 = sched.get_operations_by_job(1)[0]
        op1_1 = sched.get_operations_by_job(1)[1]

        self.assertEqual(op0_0.start, 0)
        self.assertEqual(op0_0.completion, 3)

        self.assertEqual(op1_0.start, 2)
        self.assertEqual(op1_0.completion, 5)

        self.assertEqual(op0_1.start, 5)
        self.assertEqual(op0_1.completion, 9)

        self.assertEqual(op1_1.start, 5)
        self.assertEqual(op1_1.completion, 7)

        self.assertEqual(sched.makespan, 9)

    def test_technological_precedence_respected(self) -> None:
        sol = Solution(sequence=(1, 0, 1, 0), modes=(2, 1, 1, 1))
        sched = self.decoder.decode(self.instance, sol)

        for job_id in (0, 1):
            ops = sched.get_operations_by_job(job_id)
            for i in range(len(ops) - 1):
                self.assertGreaterEqual(ops[i + 1].start, ops[i].completion)

    def test_machine_no_overlap(self) -> None:
        sol = Solution(sequence=(0, 1, 0, 1), modes=(1, 1, 1, 1))
        sched = self.decoder.decode(self.instance, sol)

        for machine_id in (0, 1):
            mach_ops = sched.get_operations_by_machine(machine_id)
            for i in range(len(mach_ops) - 1):
                self.assertGreaterEqual(mach_ops[i + 1].start, mach_ops[i].completion)

    def test_release_date_delay(self) -> None:
        # Create instance where op has a high release date
        op_late = Operation(job_id=0, op_id=0, machine_id=0, modes=(self.mode0_0_1,), release_date=10)
        job_late = Job(job_id=0, operations=(op_late,), due_date=20)
        inst_late = Instance(name="late", num_jobs=1, num_machines=1, jobs=(job_late,))

        sol = Solution(sequence=(0,), modes=(1,))
        sched = decode(inst_late, sol)

        op = sched.operations[0]
        self.assertEqual(op.start, 10)
        self.assertEqual(op.completion, 13)

    def test_determinism(self) -> None:
        sol = Solution(sequence=(0, 1, 1, 0), modes=(2, 1, 2, 1))
        sched1 = self.decoder.decode(self.instance, sol)
        sched2 = self.decoder.decode(self.instance, sol)

        self.assertEqual(sched1.operations, sched2.operations)
        self.assertEqual(sched1.makespan, sched2.makespan)

    def test_invalid_solution_raises(self) -> None:
        # Sequence length mismatch
        sol_bad_seq = Solution(sequence=(0, 1, 0), modes=(1, 1, 1, 1))
        with self.assertRaises(ValueError):
            self.decoder.decode(self.instance, sol_bad_seq)

        # Invalid mode ID
        sol_bad_mode = Solution(sequence=(0, 1, 0, 1), modes=(1, 99, 1, 1))
        with self.assertRaises(ValueError):
            self.decoder.decode(self.instance, sol_bad_mode)

    def test_different_modes_produce_different_durations(self) -> None:
        # Op (0,0) mode 1 (dur=3, energy=5.0) vs mode 2 (dur=2, energy=8.0)
        sol1 = Solution(sequence=(0, 0, 1, 1), modes=(1, 1, 1, 1))
        sol2 = Solution(sequence=(0, 0, 1, 1), modes=(2, 1, 1, 1))

        sched1 = self.decoder.decode(self.instance, sol1)
        sched2 = self.decoder.decode(self.instance, sol2)

        op1 = sched1.get_operations_by_job(0)[0]
        op2 = sched2.get_operations_by_job(0)[0]

        self.assertEqual(op1.duration, 3)
        self.assertEqual(op1.energy, 5.0)

        self.assertEqual(op2.duration, 2)
        self.assertEqual(op2.energy, 8.0)

    def test_decoding_with_dzn_toy_instance(self) -> None:
        toy_inst = load_dzn("data/validation/toy_instance.dzn")
        rng = random.Random(42)

        # Generate a random solution and decode it
        sol = Solution.random(toy_inst, rng=rng)
        sched = decode(toy_inst, sol)

        self.assertEqual(sched.num_operations, toy_inst.total_operations)

        # Verify precedence
        for job in toy_inst.jobs:
            ops = sched.get_operations_by_job(job.job_id)
            for i in range(len(ops) - 1):
                self.assertGreaterEqual(ops[i + 1].start, ops[i].completion)

        # Verify no machine overlap
        for m in range(1, toy_inst.num_machines + 1):
            m_ops = sched.get_operations_by_machine(m)
            for i in range(len(m_ops) - 1):
                self.assertGreaterEqual(m_ops[i + 1].start, m_ops[i].completion)


if __name__ == "__main__":
    unittest.main()
