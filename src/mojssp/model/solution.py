"""Representation of a MO-JSSP solution genotype."""

import random
from dataclasses import dataclass
from typing import List, Optional, Tuple
from mojssp.model.instance import Instance


@dataclass(frozen=True)
class Solution:
    """Genotypic representation of a candidate solution for MO-JSSP.

    Composed strictly of two decision vectors:
    1. sequence: An operation-based permutation (Bierwirth representation),
       where each job_id j appears exactly n_j times. The k-th occurrence of j
       represents the k-th operation O_{j,k} in the technological route of job j.
    2. modes: A tuple of selected mode IDs v_{j,k} for each operation in the instance,
       ordered according to the canonical sequence defined by instance.all_operations,
       establishing a strict bijective correspondence: modes[i] <-> instance.all_operations[i].

    In accordance with the project architecture, Solution is purely a genotype
    and does not store phenotype schedules, fitness, or objective values.

    Attributes:
        sequence: Tuple of job IDs representing the operation dispatch sequence.
        modes: Tuple of selected mode IDs aligned with instance.all_operations.
    """

    sequence: Tuple[int, ...]
    modes: Tuple[int, ...]

    def validate_with_instance(self, instance: Instance) -> None:
        """Validate that this solution matches the structure and constraints of the given instance.

        Raises:
            ValueError: If the sequence length, job frequencies, mode length, or mode IDs
                        are inconsistent with the instance.
        """
        if len(self.sequence) != instance.total_operations:
            raise ValueError(
                f"Solution sequence length ({len(self.sequence)}) does not match "
                f"instance total operations ({instance.total_operations})."
            )

        if len(self.modes) != instance.total_operations:
            raise ValueError(
                f"Solution modes length ({len(self.modes)}) does not match "
                f"instance total operations ({instance.total_operations})."
            )

        # Check job occurrences count (each job j must appear exactly n_j times)
        for job in instance.jobs:
            count = self.sequence.count(job.job_id)
            if count != job.num_operations:
                raise ValueError(
                    f"Job {job.job_id} appears {count} times in sequence; expected {job.num_operations}."
                )

        # Check mode validity for each operation using the canonical all_operations order
        for op, selected_mode_id in zip(instance.all_operations, self.modes):
            if selected_mode_id not in op.mode_ids:
                raise ValueError(
                    f"Mode {selected_mode_id} is not valid for operation ({op.job_id}, {op.op_id}). "
                    f"Available modes: {op.mode_ids}."
                )

    def get_mode_for_operation(self, job_id: int, op_id: int, instance: Instance) -> int:
        """Retrieve the selected mode ID for a specific operation (job_id, op_id)

        using the canonical order of instance.all_operations.
        """
        for idx, op in enumerate(instance.all_operations):
            if op.job_id == job_id and op.op_id == op_id:
                return self.modes[idx]
        raise IndexError(f"Operation ({job_id}, {op_id}) not found in instance '{instance.name}'.")

    @classmethod
    def random(cls, instance: Instance, rng: Optional[random.Random] = None) -> "Solution":
        """Generate a random feasible candidate solution for a given instance.

        Args:
            instance: Problem instance defining jobs, operations, and available modes.
            rng: Optional random.Random generator instance for reproducibility.

        Returns:
            A new valid Solution instance.
        """
        if rng is None:
            rng = random.Random()

        # Build list of job IDs with correct repetitions (n_j times each)
        seq_list: List[int] = []
        for job in instance.jobs:
            seq_list.extend([job.job_id] * job.num_operations)

        rng.shuffle(seq_list)

        # Select a random available mode for each operation in instance.all_operations
        modes_list: List[int] = []
        for op in instance.all_operations:
            chosen_mode = rng.choice(op.modes)
            modes_list.append(chosen_mode.mode_id)

        return cls(sequence=tuple(seq_list), modes=tuple(modes_list))
