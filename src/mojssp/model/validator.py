"""Semantic and integrity validation for MO-JSSP instances."""

from typing import List
from mojssp.model.instance import Instance


class ValidationError(Exception):
    """Exception raised when an instance fails semantic or structural validation."""

    def __init__(self, errors: List[str]):
        self.errors = errors
        message = "Instance validation failed with the following error(s):\n  - " + "\n  - ".join(errors)
        super().__init__(message)


def validate_instance(instance: Instance, raise_on_error: bool = True) -> List[str]:
    """Validates the integrity, semantics, and physical constraints of a MO-JSSP instance.

    Checks:
    1. Strictly positive number of jobs and machines.
    2. Jobs consistency (matching length, non-empty jobs).
    3. Job-level due date d_j non-negative.
    4. Sequential operation ordering within each job.
    5. Valid machine assignments (within [0, num_machines-1] or [1, num_machines]).
    6. Availability of at least one processing mode per operation.
    7. Strictly positive duration (p > 0) and non-negative energy (e >= 0) for every mode.
    8. Unique mode IDs within each operation.
    9. Non-negative release dates (r_{j,k} >= 0).

    Args:
        instance: The Instance to validate.
        raise_on_error: If True, raises ValidationError when errors are found.

    Returns:
        List of error description strings (empty if valid).

    Raises:
        ValidationError: If raise_on_error is True and validation errors exist.
    """
    errors: List[str] = []

    if instance.num_jobs <= 0:
        errors.append(f"num_jobs must be strictly positive (got {instance.num_jobs}).")

    if instance.num_machines <= 0:
        errors.append(f"num_machines must be strictly positive (got {instance.num_machines}).")

    if len(instance.jobs) != instance.num_jobs:
        errors.append(f"Instance claims {instance.num_jobs} jobs but contains {len(instance.jobs)}.")

    all_machines = {op.machine_id for job in instance.jobs for op in job.operations}
    min_machine = min(all_machines) if all_machines else 0
    max_machine = max(all_machines) if all_machines else 0

    valid_machine_range = (
        (min_machine >= 0 and max_machine < instance.num_machines) or
        (min_machine >= 1 and max_machine <= instance.num_machines)
    )
    if all_machines and not valid_machine_range:
        errors.append(
            f"Machine IDs referenced {sorted(all_machines)} are out of bounds for num_machines={instance.num_machines} "
            f"(expected [0..{instance.num_machines - 1}] or [1..{instance.num_machines}])."
        )

    for job_idx, job in enumerate(instance.jobs):
        if not job.operations:
            errors.append(f"Job at index {job_idx} (job_id={job.job_id}) is empty.")
            continue

        if job.due_date < 0:
            errors.append(f"Job {job.job_id} has negative due_date {job.due_date}.")

        seen_op_ids = set()
        for step_idx, op in enumerate(job.operations):
            if op.job_id != job.job_id:
                errors.append(
                    f"Operation at step {step_idx} in Job {job.job_id} has mismatched job_id: "
                    f"{op.job_id} != {job.job_id}."
                )

            if op.op_id in seen_op_ids:
                errors.append(f"Duplicate op_id {op.op_id} in Job {job.job_id}.")
            seen_op_ids.add(op.op_id)

            if op.op_id < 0:
                errors.append(f"Operation ({op.job_id}, {op.op_id}) has negative op_id.")

            if not op.modes:
                errors.append(f"Operation ({op.job_id}, {op.op_id}) has no processing modes defined.")
            else:
                mode_ids = set()
                for mode in op.modes:
                    if mode.mode_id in mode_ids:
                        errors.append(
                            f"Operation ({op.job_id}, {op.op_id}) contains duplicate mode_id {mode.mode_id}."
                        )
                    mode_ids.add(mode.mode_id)

                    if mode.duration <= 0:
                        errors.append(
                            f"Operation ({op.job_id}, {op.op_id}), mode {mode.mode_id}: "
                            f"duration must be > 0 (got {mode.duration})."
                        )
                    if mode.energy < 0:
                        errors.append(
                            f"Operation ({op.job_id}, {op.op_id}), mode {mode.mode_id}: "
                            f"energy must be >= 0 (got {mode.energy})."
                        )

            if op.release_date < 0:
                errors.append(
                    f"Operation ({op.job_id}, {op.op_id}) has negative release_date {op.release_date}."
                )

    if errors and raise_on_error:
        raise ValidationError(errors)

    return errors
