"""Representation of a MO-JSSP instance with Speed Scaling."""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple
from mojssp.model.job import Job
from mojssp.model.operation import Operation


@dataclass(frozen=True)
class Instance:
    """Represents a complete Multi-Objective Job Shop Scheduling Problem instance with Speed Scaling.

    Attributes:
        name: Name or identifier of the instance.
        num_jobs: Number of jobs n in the instance.
        num_machines: Number of physical machines m available.
        jobs: Tuple of Job objects, where each job encapsulates its operations and due date.
        metadata: Optional dictionary with additional metadata or notes.
    """

    name: str
    num_jobs: int
    num_machines: int
    jobs: Tuple[Job, ...]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.num_jobs <= 0:
            raise ValueError(f"num_jobs must be strictly positive, got {self.num_jobs}")
        if self.num_machines <= 0:
            raise ValueError(f"num_machines must be strictly positive, got {self.num_machines}")
        if len(self.jobs) != self.num_jobs:
            raise ValueError(f"len(jobs) ({len(self.jobs)}) does not match num_jobs ({self.num_jobs})")

    @property
    def total_operations(self) -> int:
        """Total number of operations across all jobs."""
        return sum(job.num_operations for job in self.jobs)

    @property
    def all_operations(self) -> Tuple[Operation, ...]:
        """Flattened tuple of all operations in the instance."""
        return tuple(op for job in self.jobs for op in job.operations)

    def get_job(self, job_id: int) -> Job:
        """Retrieve a Job by its job_id."""
        for job in self.jobs:
            if job.job_id == job_id:
                return job
        # Index fallback if aligned
        if 0 <= job_id < len(self.jobs):
            return self.jobs[job_id]
        raise IndexError(f"Job ID {job_id} not found in instance '{self.name}'.")

    def get_operation(self, job_id: int, op_id: int) -> Operation:
        """Retrieve a specific operation by its job_id and op_id."""
        job = self.get_job(job_id)
        return job.get_operation(op_id)

    def get_operations_for_machine(self, machine_id: int) -> Tuple[Operation, ...]:
        """Return all operations requiring the specified machine."""
        return tuple(op for op in self.all_operations if op.machine_id == machine_id)
