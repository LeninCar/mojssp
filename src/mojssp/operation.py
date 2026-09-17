"""Representation of an individual operation in a Job Shop problem."""

from dataclasses import dataclass
from typing import Tuple
from .mode import ProcessingMode


@dataclass(frozen=True)
class Operation:
    """An operation O_{j,k} belonging to a specific job and requiring a designated machine.

    Attributes:
        job_id: Identifier j of the job to which this operation belongs.
        op_id: Sequential index k of this operation within the job.
        machine_id: The machine M_{j,k} required to process this operation.
        modes: Tuple of available ProcessingMode instances (V_{j,k}).
        release_date: Earliest time r_{j,k} at which this operation can start (default 0).
    """

    job_id: int
    op_id: int
    machine_id: int
    modes: Tuple[ProcessingMode, ...]
    release_date: int = 0

    def __post_init__(self) -> None:
        if not self.modes:
            raise ValueError(f"Operation ({self.job_id}, {self.op_id}) must have at least one processing mode.")
        if self.release_date < 0:
            raise ValueError(f"release_date must be non-negative, got {self.release_date}")

    @property
    def mode_ids(self) -> Tuple[int, ...]:
        """Return the available mode IDs for this operation."""
        return tuple(m.mode_id for m in self.modes)

    def get_mode(self, mode_id: int) -> ProcessingMode:
        """Retrieve a specific processing mode by ID.

        Raises:
            KeyError: If mode_id is not available for this operation.
        """
        for mode in self.modes:
            if mode.mode_id == mode_id:
                return mode
        raise KeyError(
            f"Mode ID {mode_id} not available for operation ({self.job_id}, {self.op_id}). "
            f"Available: {self.mode_ids}"
        )
