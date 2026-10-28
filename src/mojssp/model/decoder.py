"""Serial list-based decoder transforming a Solution genotype into a Schedule phenotype."""

from collections import defaultdict
from typing import Dict, List, Tuple

from mojssp.model.instance import Instance
from mojssp.model.operation import Operation
from mojssp.model.schedule import Schedule, ScheduledOperation
from mojssp.model.solution import Solution


class Decoder:
    """Serial list-based decoder for the Multi-Objective Job Shop Scheduling Problem.

    Converts a valid Solution (Bierwirth operation-based sequence and mode vector)
    into a deterministic, semi-active Schedule phenotype.

    For each operation O_{j,k}:
        S_{j,k} = max(C_{j,prev}, T_disp(M_{j,k}), r_{j,k})
        C_{j,k} = S_{j,k} + p_{j,k,v}
    where:
        - C_{j,prev} is the completion time of the previous operation of the same job (0 if first),
        - T_disp(M_{j,k}) is the earliest time machine M_{j,k} becomes available (0 initially),
        - r_{j,k} is the operation's release date,
        - p_{j,k,v} is the duration corresponding to the selected processing mode v.

    Time complexity: O(N) under O(1) job and machine availability tracking and mode lookup,
    where N is the total number of operations across all jobs.
    """

    def decode(self, instance: Instance, solution: Solution) -> Schedule:
        """Decode a candidate Solution into a Schedule phenotype for the given Instance.

        Args:
            instance: Instance defining jobs, operations, machines, and modes.
            solution: Solution genotype containing the operation sequence and modes.

        Returns:
            Schedule containing all ScheduledOperation objects.

        Raises:
            ValueError: If the solution is invalid or incompatible with the instance.
        """
        # Validate solution compatibility with the instance
        solution.validate_with_instance(instance)

        # Pre-index job operations and their canonical index in instance.all_operations
        # canonical_idx allows O(1) lookup of selected mode in solution.modes
        job_ops_with_idx: Dict[int, List[Tuple[Operation, int]]] = {}
        canonical_idx = 0
        for job in instance.jobs:
            job_ops_with_idx[job.job_id] = []
            for op in job.operations:
                job_ops_with_idx[job.job_id].append((op, canonical_idx))
                canonical_idx += 1

        # Track state for O(1) updates
        job_next_idx: Dict[int, int] = defaultdict(int)
        job_completion_time: Dict[int, int] = defaultdict(int)
        machine_availability: Dict[int, int] = defaultdict(int)

        scheduled_ops: List[ScheduledOperation] = []

        # Serial list decoding: iterate over the Bierwirth sequence
        for job_id in solution.sequence:
            op_idx = job_next_idx[job_id]
            op, can_idx = job_ops_with_idx[job_id][op_idx]

            selected_mode_id = solution.modes[can_idx]
            mode = op.get_mode(selected_mode_id)

            duration = mode.duration
            energy = mode.energy
            machine_id = op.machine_id
            release_date = op.release_date

            c_prev = job_completion_time[job_id]
            t_mach = machine_availability[machine_id]

            start_time = max(c_prev, t_mach, release_date)
            completion_time = start_time + duration

            # Update availability
            job_completion_time[job_id] = completion_time
            machine_availability[machine_id] = completion_time
            job_next_idx[job_id] += 1

            scheduled_op = ScheduledOperation(
                job_id=job_id,
                op_id=op.op_id,
                machine_id=machine_id,
                mode_id=selected_mode_id,
                start=start_time,
                completion=completion_time,
                duration=duration,
                energy=energy,
                release_date=release_date,
            )
            scheduled_ops.append(scheduled_op)

        return Schedule(scheduled_ops)


def decode(instance: Instance, solution: Solution) -> Schedule:
    """Convenience function to decode a candidate Solution into a Schedule.

    Args:
        instance: Instance defining jobs, operations, machines, and modes.
        solution: Solution genotype containing the operation sequence and modes.

    Returns:
        Schedule containing all ScheduledOperation objects.
    """
    return Decoder().decode(instance, solution)
