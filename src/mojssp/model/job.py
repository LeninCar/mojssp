"""Representation of a Job in a MO-JSSP instance."""

from dataclasses import dataclass
from typing import Tuple
from mojssp.model.operation import Operation


@dataclass(frozen=True)
class Job:
    """Represents a job j in a Job Shop scheduling problem.

    A job consists of an ordered sequence of operations (O_{j,1}, ..., O_{j,n_j})
    and an agreed due date d_j used to measure tardiness upon completion.

    Attributes:
        job_id: Identifier of the job (j in {1, ..., n}).
        operations: Ordered tuple of Operation instances belonging to this job.
        due_date: Agreed completion deadline d_j for the job (must be non-negative).
    """

    job_id: int
    operations: Tuple[Operation, ...]
    due_date: int

    def __post_init__(self) -> None:
        if not self.operations:
            raise ValueError(f"Job {self.job_id} must contain at least one operation.")
        if self.due_date < 0:
            raise ValueError(f"Job {self.job_id} due_date must be non-negative, got {self.due_date}.")
        for op in self.operations:
            if op.job_id != self.job_id:
                raise ValueError(
                    f"Operation ({op.job_id}, {op.op_id}) in Job {self.job_id} has mismatched job_id."
                )

    @property
    def num_operations(self) -> int:
        """Number of operations n_j comprising this job."""
        return len(self.operations)

    @property
    def last_operation(self) -> Operation:
        """The final operation of the job, whose completion defines C_j."""
        return self.operations[-1]

    def get_operation(self, op_id: int) -> Operation:
        """Retrieve an operation by its op_id."""
        for op in self.operations:
            if op.op_id == op_id:
                return op
        raise IndexError(f"Operation with op_id={op_id} not found in Job {self.job_id}.")
