"""Evaluation of MO-JSSP schedules across multiple objectives (Cmax, Tardiness, Energy)."""

from dataclasses import dataclass
from typing import Iterator, Tuple

from .instance import Instance
from .schedule import Schedule


@dataclass(frozen=True)
class ObjectiveValues:
    """Immutable structure representing the three minimization objective values.

    Attributes:
        makespan: Maximum completion time Cmax >= 0.
        tardiness: Total tardiness T = sum_j max(0, C_j - d_j) >= 0.
        energy: Total consumed energy E = sum_o E_o >= 0.0.
    """

    makespan: int
    tardiness: int
    energy: float

    def __post_init__(self) -> None:
        if self.makespan < 0:
            raise ValueError(f"makespan must be non-negative, got {self.makespan}")
        if self.tardiness < 0:
            raise ValueError(f"tardiness must be non-negative, got {self.tardiness}")
        if self.energy < 0:
            raise ValueError(f"energy must be non-negative, got {self.energy}")

    def to_tuple(self) -> Tuple[int, int, float]:
        """Return objective values as a tuple (makespan, tardiness, energy)."""
        return (self.makespan, self.tardiness, self.energy)

    def __iter__(self) -> Iterator[float]:
        """Support tuple unpacking: cmax, tardiness, energy = obj_values."""
        return iter((self.makespan, self.tardiness, self.energy))


class Evaluator:
    """Evaluates a Schedule phenotype against an Instance, computing (Cmax, T, E).

    The evaluator is a pure function / stateless service:
    it measures the phenotype without modifying the schedule or the instance.
    """

    def evaluate(self, instance: Instance, schedule: Schedule) -> ObjectiveValues:
        """Calculate the three objective values for a given instance and schedule.

        Args:
            instance: Instance containing problem data, jobs, and due dates.
            schedule: Schedule containing scheduled operations and completion times.

        Returns:
            ObjectiveValues containing (makespan, tardiness, energy).

        Raises:
            ValueError: If the schedule contains job IDs not defined in the instance.
        """
        instance_job_ids = {job.job_id for job in instance.jobs}
        schedule_job_ids = set(schedule.job_ids)

        # Ensure schedule jobs are consistent with instance
        invalid_jobs = schedule_job_ids - instance_job_ids
        if invalid_jobs:
            raise ValueError(
                f"Schedule contains job IDs {sorted(invalid_jobs)} not present in instance '{instance.name}'."
            )

        # 1. Makespan: Cmax = max_j (C_j)
        makespan = schedule.makespan

        # 2. Total Tardiness: T = sum_j max(0, C_j - d_j)
        total_tardiness = 0
        for job in instance.jobs:
            if job.job_id in schedule.job_completion_times:
                c_j = schedule.get_job_completion_time(job.job_id)
            else:
                c_j = 0
            t_j = max(0, c_j - job.due_date)
            total_tardiness += t_j

        # 3. Consumed Energy: E = sum_o E_o
        total_energy = sum(op.energy for op in schedule.operations)

        return ObjectiveValues(
            makespan=makespan,
            tardiness=total_tardiness,
            energy=total_energy,
        )


def evaluate(instance: Instance, schedule: Schedule) -> ObjectiveValues:
    """Convenience function to evaluate a Schedule against an Instance.

    Args:
        instance: Instance containing problem data and due dates.
        schedule: Schedule containing scheduled operations.

    Returns:
        ObjectiveValues containing (makespan, tardiness, energy).
    """
    return Evaluator().evaluate(instance, schedule)

