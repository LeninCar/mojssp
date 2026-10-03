"""Unit tests for Critical Path identification and sequence index mapping (Phase 5)."""

from pathlib import Path
import sys
import unittest

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mojssp import (
    Decoder,
    Instance,
    Job,
    Operation,
    ProcessingMode,
    Schedule,
    ScheduledOperation,
    Solution,
    decode,
    get_critical_operations,
    get_critical_sequence_indices,
    load_dzn,
    map_operation_to_sequence_index,
)


class TestCriticalPath(unittest.TestCase):
    """Test suite for Critical Path identification and sequence mapping."""

    def setUp(self) -> None:
        toy_dzn = Path(__file__).resolve().parent.parent / "data" / "validation" / "toy_instance.dzn"
        self.instance = load_dzn(str(toy_dzn))

    def test_empty_schedule(self) -> None:
        """An empty schedule has no critical operations."""
        sched = Schedule([])
        crit_ops = get_critical_operations(sched)
        self.assertEqual(crit_ops, set())

    def test_single_critical_path_chain(self) -> None:
        """Test schedule where a single chain determines the makespan."""
        # Job 1: Op 0 (M1, dur 5) -> Op 1 (M2, dur 7)
        # Job 2: Op 0 (M2, dur 2) -> Op 1 (M1, dur 2)
        # Sequence: (1, 2, 1, 2)
        # M1: Job 1 Op 0 [0, 5], Job 2 Op 1 [5, 7]
        # M2: Job 2 Op 0 [0, 2], Job 1 Op 1 [5, 12]
        # Makespan = 12, achieved by Job 1 Op 1.
        # Job 1 Op 1 start=5, completion=12.
        # Its job_prev is Job 1 Op 0 with completion=5 (slack 0).
        # Its mach_prev is Job 2 Op 0 with completion=2 (slack 3 > 0).
        # Thus the critical chain is Job 1 Op 0 -> Job 1 Op 1.
        mode1 = ProcessingMode(mode_id=1, duration=5, energy=10.0)
        mode2 = ProcessingMode(mode_id=1, duration=7, energy=15.0)
        mode3 = ProcessingMode(mode_id=1, duration=2, energy=5.0)
        mode4 = ProcessingMode(mode_id=1, duration=2, energy=5.0)

        op1 = Operation(job_id=1, op_id=0, machine_id=1, modes=(mode1,))
        op2 = Operation(job_id=1, op_id=1, machine_id=2, modes=(mode2,))
        op3 = Operation(job_id=2, op_id=0, machine_id=2, modes=(mode3,))
        op4 = Operation(job_id=2, op_id=1, machine_id=1, modes=(mode4,))

        j1 = Job(job_id=1, operations=(op1, op2), due_date=20)
        j2 = Job(job_id=2, operations=(op3, op4), due_date=20)
        inst = Instance(name="chain_test", num_jobs=2, num_machines=2, jobs=(j1, j2))

        sol = Solution(sequence=(1, 2, 1, 2), modes=(1, 1, 1, 1))
        sched = decode(inst, sol)

        self.assertEqual(sched.makespan, 12)
        crit_ops = get_critical_operations(sched)
        crit_keys = {(op.job_id, op.op_id) for op in crit_ops}

        # The critical operations must be Job 1 Op 0 and Job 1 Op 1
        self.assertIn((1, 0), crit_keys)
        self.assertIn((1, 1), crit_keys)
        # Job 2 Op 0 finished at 2 while Job 1 Op 1 started at 5 -> not critical
        self.assertNotIn((2, 0), crit_keys)
        self.assertNotIn((2, 1), crit_keys)

    def test_multiple_critical_paths(self) -> None:
        """Test schedule where two completely independent branches reach makespan."""
        # Job 1 on M1 finishes at 10.
        # Job 2 on M2 finishes at 10.
        # Both operations are terminal and both paths must be in critical operations.
        mode1 = ProcessingMode(mode_id=1, duration=10, energy=10.0)
        mode2 = ProcessingMode(mode_id=1, duration=10, energy=10.0)

        op1 = Operation(job_id=1, op_id=0, machine_id=1, modes=(mode1,))
        op2 = Operation(job_id=2, op_id=0, machine_id=2, modes=(mode2,))

        j1 = Job(job_id=1, operations=(op1,), due_date=20)
        j2 = Job(job_id=2, operations=(op2,), due_date=20)
        inst = Instance(name="multi_cp", num_jobs=2, num_machines=2, jobs=(j1, j2))

        sol = Solution(sequence=(1, 2), modes=(1, 1))
        sched = decode(inst, sol)

        self.assertEqual(sched.makespan, 10)
        crit_ops = get_critical_operations(sched)
        self.assertEqual(len(crit_ops), 2)
        crit_keys = {(op.job_id, op.op_id) for op in crit_ops}
        self.assertEqual(crit_keys, {(1, 0), (2, 0)})

    def test_mapping_operation_to_sequence_index(self) -> None:
        """Test exact mapping of operation to position in sequence."""
        sol = Solution(sequence=(2, 1, 2, 1), modes=(1, 1, 1, 1))
        sched = decode(self.instance, sol)
        seq = sol.sequence

        j2_ops = sched.get_operations_by_job(2)
        j1_ops = sched.get_operations_by_job(1)

        # Job 2, 1st op -> first occurrence of 2 (index 0)
        self.assertEqual(map_operation_to_sequence_index(j2_ops[0], sched, seq), 0)
        # Job 1, 1st op -> first occurrence of 1 (index 1)
        self.assertEqual(map_operation_to_sequence_index(j1_ops[0], sched, seq), 1)
        # Job 2, 2nd op -> second occurrence of 2 (index 2)
        self.assertEqual(map_operation_to_sequence_index(j2_ops[1], sched, seq), 2)
        # Job 1, 2nd op -> second occurrence of 1 (index 3)
        self.assertEqual(map_operation_to_sequence_index(j1_ops[1], sched, seq), 3)

        # Alien operation raises ValueError
        alien_op = ScheduledOperation(
            job_id=99,
            op_id=0,
            machine_id=1,
            mode_id=1,
            start=0,
            completion=5,
            duration=5,
            energy=10.0,
            release_date=0,
        )
        with self.assertRaises(ValueError):
            map_operation_to_sequence_index(alien_op, sched, seq)

    def test_get_critical_sequence_indices(self) -> None:
        """Test get_critical_sequence_indices on toy instance."""
        sol = Solution(sequence=(1, 2, 1, 2), modes=(1, 1, 1, 1))
        sched = decode(self.instance, sol)

        crit_indices = get_critical_sequence_indices(sched, sol.sequence)
        self.assertTrue(len(crit_indices) > 0)
        # Every critical index must be in range of sequence
        for idx in crit_indices:
            self.assertTrue(0 <= idx < len(sol.sequence))


if __name__ == "__main__":
    unittest.main()
