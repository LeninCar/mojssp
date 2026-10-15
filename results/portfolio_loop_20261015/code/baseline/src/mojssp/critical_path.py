"""Critical path analysis and sequence mapping for MO-JSSP schedules."""

from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple

from .schedule import Schedule, ScheduledOperation


def get_critical_operations(schedule: Schedule) -> Set[ScheduledOperation]:
    """Identify all operations that belong to at least one critical path in the schedule.

    A critical path is a sequence of operations from time t >= 0 to makespan where every
    transition between consecutive operations has zero slack (v.completion == u.start).
    This function accounts for multiple critical paths by performing a backward traversal
    from all operations completing at makespan.

    Args:
        schedule: The evaluated schedule phenotype.

    Returns:
        Set of all ScheduledOperation instances belonging to any critical path.
    """
    if schedule.num_operations == 0:
        return set()

    cmax = schedule.makespan

    # Pre-index predecessors using schedule's job and machine order
    # 1. Job predecessors: map operation -> immediate preceding operation in the same job
    job_prev_map: Dict[ScheduledOperation, ScheduledOperation] = {}
    for j_id in schedule.job_ids:
        j_ops = schedule.get_operations_by_job(j_id)
        for k in range(1, len(j_ops)):
            job_prev_map[j_ops[k]] = j_ops[k - 1]

    # 2. Machine predecessors: map operation -> immediate preceding operation on same machine
    machine_prev_map: Dict[ScheduledOperation, ScheduledOperation] = {}
    for m_id in schedule.machine_ids:
        m_ops = schedule.get_operations_by_machine(m_id)
        for p in range(1, len(m_ops)):
            machine_prev_map[m_ops[p]] = m_ops[p - 1]

    # Find all terminal operations ending at makespan
    terminals = [op for op in schedule.operations if op.completion == cmax]
    if not terminals:
        return set()

    critical_ops: Set[ScheduledOperation] = set(terminals)
    queue: List[ScheduledOperation] = list(terminals)

    while queue:
        curr = queue.pop()
        start_time = curr.start

        # Check job predecessor
        job_pred = job_prev_map.get(curr)
        if job_pred is not None and job_pred.completion == start_time:
            if job_pred not in critical_ops:
                critical_ops.add(job_pred)
                queue.append(job_pred)

        # Check machine predecessor
        mach_pred = machine_prev_map.get(curr)
        if mach_pred is not None and mach_pred.completion == start_time:
            if mach_pred not in critical_ops:
                critical_ops.add(mach_pred)
                queue.append(mach_pred)

    return critical_ops


def map_operation_to_sequence_index(
    operation: ScheduledOperation,
    schedule: Schedule,
    sequence: Tuple[int, ...],
) -> int:
    """Find the index in sequence corresponding to a ScheduledOperation.

    The technological index k of operation within its job is determined by
    its position in schedule.get_operations_by_job(operation.job_id).
    The corresponding position in sequence is the k-th occurrence of operation.job_id.

    Args:
        operation: ScheduledOperation to map.
        schedule: Schedule containing the operation.
        sequence: Operation-based sequence (Bierwirth permutation).

    Returns:
        Index in sequence where operation is placed.

    Raises:
        ValueError: If operation is not found in schedule or sequence.
    """
    job_ops = schedule.get_operations_by_job(operation.job_id)
    try:
        k = job_ops.index(operation)
    except ValueError:
        raise ValueError(
            f"Operation {operation} not found in schedule for job {operation.job_id}."
        )

    occurrence = 0
    for idx, j in enumerate(sequence):
        if j == operation.job_id:
            if occurrence == k:
                return idx
            occurrence += 1

    raise ValueError(
        f"Operation {operation} (occurrence {k}) not found in sequence."
    )


def get_critical_sequence_indices(
    schedule: Schedule, sequence: Tuple[int, ...]
) -> Set[int]:
    """Identify the set of positions in sequence that correspond to critical operations.

    Args:
        schedule: The evaluated schedule phenotype.
        sequence: The operation-based sequence genotype.

    Returns:
        Set of integer indices in sequence.
    """
    critical_ops = get_critical_operations(schedule)
    if not critical_ops:
        return set()

    # Pre-map all operations in schedule to sequence indices in a single O(N) pass
    job_occurrence: Dict[int, int] = defaultdict(int)
    job_ops_cache = {j_id: schedule.get_operations_by_job(j_id) for j_id in schedule.job_ids}

    critical_indices: Set[int] = set()
    for seq_idx, j_id in enumerate(sequence):
        k = job_occurrence[j_id]
        op = job_ops_cache[j_id][k]
        if op in critical_ops:
            critical_indices.add(seq_idx)
        job_occurrence[j_id] += 1

    return critical_indices

