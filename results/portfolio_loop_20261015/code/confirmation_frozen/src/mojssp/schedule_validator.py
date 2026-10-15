"""Independent auditor verifying that a Schedule is semantically and temporally valid for an Instance."""

import math
from typing import List

from .instance import Instance
from .schedule import Schedule


class ScheduleValidationError(Exception):
    """Exception raised when a Schedule fails semantic, constraint, or temporal validation."""

    def __init__(self, errors: List[str]) -> None:
        self.errors = errors
        message = "Schedule validation failed with the following error(s):\n  - " + "\n  - ".join(errors)
        super().__init__(message)


class ScheduleValidator:
    """Audits a Schedule phenotype independently against an Instance.

    Verifies:
    1. Operation completeness: Schedule contains exactly the operations defined in the instance.
    2. Machine assignment: Operations are processed on the machine specified by the instance.
    3. Mode validity: The selected mode exists in the available modes for that operation.
    4. Duration consistency: Scheduled duration matches the mode definition in the instance.
    5. Energy consistency: Scheduled energy matches the mode definition in the instance.
    6. Release dates: Operation start time respects the instance release date.
    7. Technological precedence: Operations within each job are strictly sequential.
    8. Machine capacity: No two operations on the same machine overlap in time.
    """

    def __init__(self, energy_tolerance: float = 1e-6) -> None:
        self.energy_tolerance = energy_tolerance

    def validate(
        self,
        instance: Instance,
        schedule: Schedule,
        raise_on_error: bool = True,
    ) -> List[str]:
        """Validate a Schedule against an Instance.

        Args:
            instance: Instance defining problem data, operations, and constraints.
            schedule: Schedule phenotype to audit.
            raise_on_error: If True, raises ScheduleValidationError on any detected error.

        Returns:
            List of error description strings (empty if schedule is valid).

        Raises:
            ScheduleValidationError: If raise_on_error is True and validation errors are found.
        """
        errors: List[str] = []

        # 1. Check operation counts
        if schedule.num_operations != instance.total_operations:
            errors.append(
                f"Operation count mismatch: schedule has {schedule.num_operations}, "
                f"instance expects {instance.total_operations}."
            )

        # Build lookup of expected operations: (job_id, op_id) -> Operation
        expected_ops = {(op.job_id, op.op_id): op for op in instance.all_operations}
        schedule_ops = {(op.job_id, op.op_id): op for op in schedule.operations}

        # 2. Check for missing operations
        for key, inst_op in expected_ops.items():
            if key not in schedule_ops:
                errors.append(f"Missing operation (job {inst_op.job_id}, op {inst_op.op_id}) in schedule.")

        # 3. Check for foreign / unexpected operations
        for key, sched_op in schedule_ops.items():
            if key not in expected_ops:
                errors.append(
                    f"Unexpected operation (job {sched_op.job_id}, op {sched_op.op_id}) in schedule "
                    f"not defined in instance '{instance.name}'."
                )

        # 4. Semantic check for each scheduled operation matching instance definition
        for sched_op in schedule.operations:
            key = (sched_op.job_id, sched_op.op_id)
            if key not in expected_ops:
                continue  # already reported as unexpected

            inst_op = expected_ops[key]

            # Machine assignment
            if sched_op.machine_id != inst_op.machine_id:
                errors.append(
                    f"Machine mismatch for operation ({sched_op.job_id}, {sched_op.op_id}): "
                    f"scheduled on machine {sched_op.machine_id}, instance specifies {inst_op.machine_id}."
                )

            # Mode validity
            if sched_op.mode_id not in inst_op.mode_ids:
                errors.append(
                    f"Invalid mode {sched_op.mode_id} for operation ({sched_op.job_id}, {sched_op.op_id}). "
                    f"Available modes: {inst_op.mode_ids}."
                )
            else:
                # Mode exists: check duration and energy consistency
                inst_mode = inst_op.get_mode(sched_op.mode_id)
                if sched_op.duration != inst_mode.duration:
                    errors.append(
                        f"Duration mismatch for operation ({sched_op.job_id}, {sched_op.op_id}) under mode "
                        f"{sched_op.mode_id}: scheduled has {sched_op.duration}, instance specifies {inst_mode.duration}."
                    )
                if not math.isclose(sched_op.energy, inst_mode.energy, abs_tol=self.energy_tolerance):
                    errors.append(
                        f"Energy mismatch for operation ({sched_op.job_id}, {sched_op.op_id}) under mode "
                        f"{sched_op.mode_id}: scheduled has {sched_op.energy}, instance specifies {inst_mode.energy}."
                    )

            # Release date consistency and adherence
            if sched_op.release_date != inst_op.release_date:
                errors.append(
                    f"Release date mismatch for operation ({sched_op.job_id}, {sched_op.op_id}): "
                    f"scheduled has {sched_op.release_date}, instance specifies {inst_op.release_date}."
                )
            if sched_op.start < inst_op.release_date:
                errors.append(
                    f"Release date violation for operation ({sched_op.job_id}, {sched_op.op_id}): "
                    f"starts at {sched_op.start} before instance release date {inst_op.release_date}."
                )

        # 5. Technological precedence verification within each job
        for job in instance.jobs:
            job_ops = schedule.get_operations_by_job(job.job_id)
            for i in range(len(job_ops) - 1):
                prev_op = job_ops[i]
                next_op = job_ops[i + 1]
                if next_op.start < prev_op.completion:
                    errors.append(
                        f"Technological precedence violation in job {job.job_id}: operation {next_op.op_id} "
                        f"starts at {next_op.start} before operation {prev_op.op_id} completes at {prev_op.completion}."
                    )

        # 6. Machine non-overlap verification
        for machine_id in schedule.machine_ids:
            mach_ops = sorted(
                schedule.get_operations_by_machine(machine_id),
                key=lambda op: (op.start, op.completion),
            )
            for i in range(len(mach_ops) - 1):
                curr_op = mach_ops[i]
                next_op = mach_ops[i + 1]
                if next_op.start < curr_op.completion:
                    errors.append(
                        f"Machine {machine_id} overlap: operation ({curr_op.job_id}, {curr_op.op_id}) "
                        f"[{curr_op.start}, {curr_op.completion}] overlaps with operation "
                        f"({next_op.job_id}, {next_op.op_id}) [{next_op.start}, {next_op.completion}]."
                    )

        if raise_on_error and errors:
            raise ScheduleValidationError(errors)

        return errors


def validate_schedule(
    instance: Instance,
    schedule: Schedule,
    raise_on_error: bool = True,
    energy_tolerance: float = 1e-6,
) -> List[str]:
    """Convenience function to audit a Schedule against an Instance.

    Args:
        instance: Instance defining problem data, operations, and constraints.
        schedule: Schedule phenotype to audit.
        raise_on_error: If True, raises ScheduleValidationError on any detected error.
        energy_tolerance: Maximum absolute tolerance when comparing float energy values.

    Returns:
        List of error description strings (empty if schedule is valid).
    """
    validator = ScheduleValidator(energy_tolerance=energy_tolerance)
    return validator.validate(instance, schedule, raise_on_error=raise_on_error)

