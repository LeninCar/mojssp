"""Phenotype representation of scheduled operations and schedules."""

from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Tuple


@dataclass(frozen=True)
class ScheduledOperation:
    """An operation scheduled in time on a specific machine with a selected processing mode.

    Attributes:
        job_id: Identifier j of the job to which this operation belongs.
        op_id: Sequential index k of this operation within the job.
        machine_id: Machine M_{j,k} processing this operation.
        mode_id: Selected processing mode ID v.
        start: Start time S_{j,k} >= 0.
        completion: Completion time C_{j,k} = start + duration.
        duration: Duration p_{j,k,v} > 0.
        energy: Energy consumed E_{j,k,v} >= 0.
        release_date: Earliest available time r_{j,k} >= 0.
    """

    job_id: int
    op_id: int
    machine_id: int
    mode_id: int
    start: int
    completion: int
    duration: int
    energy: float
    release_date: int = 0

    def __post_init__(self) -> None:
        if self.job_id < 0:
            raise ValueError(f"job_id must be non-negative, got {self.job_id}")
        if self.op_id < 0:
            raise ValueError(f"op_id must be non-negative, got {self.op_id}")
        if self.machine_id < 0:
            raise ValueError(f"machine_id must be non-negative, got {self.machine_id}")
        if self.start < 0:
            raise ValueError(f"start must be non-negative, got {self.start}")
        if self.duration <= 0:
            raise ValueError(f"duration must be strictly positive, got {self.duration}")
        if self.completion != self.start + self.duration:
            raise ValueError(
                f"completion ({self.completion}) must equal start ({self.start}) + duration ({self.duration})"
            )
        if self.release_date < 0:
            raise ValueError(f"release_date must be non-negative, got {self.release_date}")
        if self.start < self.release_date:
            raise ValueError(
                f"start ({self.start}) cannot be strictly less than release_date ({self.release_date})"
            )
        if self.energy < 0:
            raise ValueError(f"energy must be non-negative, got {self.energy}")


@dataclass(frozen=True)
class Schedule:
    """Immutable collection of scheduled operations representing a schedule phenotype.

    Attributes:
        operations: Tuple of all ScheduledOperation instances.
    """

    operations: Tuple[ScheduledOperation, ...]

    def __init__(self, operations: Iterable[ScheduledOperation]) -> None:
        ops_tuple = tuple(operations)
        object.__setattr__(self, "operations", ops_tuple)

        by_job: Dict[int, List[ScheduledOperation]] = {}
        by_machine: Dict[int, List[ScheduledOperation]] = {}
        seen_ops = set()

        for op in ops_tuple:
            key = (op.job_id, op.op_id)
            if key in seen_ops:
                raise ValueError(f"Duplicate operation (job {op.job_id}, op {op.op_id}) in schedule.")
            seen_ops.add(key)

            by_job.setdefault(op.job_id, []).append(op)
            by_machine.setdefault(op.machine_id, []).append(op)

        frozen_by_job: Dict[int, Tuple[ScheduledOperation, ...]] = {
            j: tuple(sorted(ops, key=lambda x: x.op_id)) for j, ops in by_job.items()
        }
        frozen_by_machine: Dict[int, Tuple[ScheduledOperation, ...]] = {
            m: tuple(sorted(ops, key=lambda x: x.start)) for m, ops in by_machine.items()
        }

        job_completion_times: Dict[int, int] = {}
        for j, ops in frozen_by_job.items():
            job_completion_times[j] = max(op.completion for op in ops)

        object.__setattr__(self, "_operations_by_job", frozen_by_job)
        object.__setattr__(self, "_operations_by_machine", frozen_by_machine)
        object.__setattr__(self, "_job_completion_times", job_completion_times)

    @property
    def num_operations(self) -> int:
        """Total number of scheduled operations."""
        return len(self.operations)

    @property
    def job_ids(self) -> Tuple[int, ...]:
        """IDs of all jobs present in the schedule."""
        return tuple(self._operations_by_job.keys())

    @property
    def machine_ids(self) -> Tuple[int, ...]:
        """IDs of all machines utilized in the schedule."""
        return tuple(self._operations_by_machine.keys())

    @property
    def makespan(self) -> int:
        """Maximum completion time across all scheduled operations (Cmax)."""
        if not self.operations:
            return 0
        return max(op.completion for op in self.operations)

    @property
    def job_completion_times(self) -> Mapping[int, int]:
        """Mapping of job_id to its completion time C_j (completion of its last operation)."""
        return dict(self._job_completion_times)

    def get_operations_by_job(self, job_id: int) -> Tuple[ScheduledOperation, ...]:
        """Retrieve all scheduled operations of a job, ordered by op_id."""
        return self._operations_by_job.get(job_id, ())

    def get_operations_by_machine(self, machine_id: int) -> Tuple[ScheduledOperation, ...]:
        """Retrieve all scheduled operations on a machine, ordered by start time."""
        return self._operations_by_machine.get(machine_id, ())

    def get_job_completion_time(self, job_id: int) -> int:
        """Retrieve the completion time C_j of a specific job.

        Raises:
            KeyError: If the job has no scheduled operations in this schedule.
        """
        if job_id not in self._job_completion_times:
            raise KeyError(f"Job {job_id} not found in schedule.")
        return self._job_completion_times[job_id]

