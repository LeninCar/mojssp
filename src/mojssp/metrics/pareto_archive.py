"""Pareto Archive for accumulating and preserving non-dominated solutions across algorithm runs."""

import math
from dataclasses import dataclass
from typing import Iterator, List, Optional, Sequence, Tuple, Union

from mojssp.metrics.dominance import dominates
from mojssp.model.evaluator import ObjectiveValues
from mojssp.model.schedule import Schedule
from mojssp.model.solution import Solution


@dataclass(frozen=True)
class ArchiveEntry:
    """An entry in the Pareto Archive preserving genotype, phenotype, and objective values.

    Attributes:
        solution: Genotype (sequence, modes).
        schedule: Phenotype (temporal realization).
        objectives: Evaluated criteria (Cmax, T, E).
    """

    solution: Solution
    schedule: Schedule
    objectives: ObjectiveValues

    def __post_init__(self) -> None:
        if not isinstance(self.solution, Solution):
            raise TypeError(f"solution must be an instance of Solution, got {type(self.solution)}")
        if not isinstance(self.schedule, Schedule):
            raise TypeError(f"schedule must be an instance of Schedule, got {type(self.schedule)}")
        if not isinstance(self.objectives, ObjectiveValues):
            raise TypeError(f"objectives must be an instance of ObjectiveValues, got {type(self.objectives)}")
        if self.schedule.makespan != self.objectives.makespan:
            raise ValueError(
                f"Makespan mismatch: schedule has {self.schedule.makespan}, "
                f"objectives has {self.objectives.makespan}"
            )
        schedule_energy = sum(op.energy for op in self.schedule.operations)
        if not math.isclose(self.objectives.energy, schedule_energy, abs_tol=1e-5):
            raise ValueError(
                f"Energy mismatch: schedule has {schedule_energy}, objectives has {self.objectives.energy}"
            )


class ParetoArchive:
    """Cumulative, unbounded Pareto Archive for MO-JSSP.

    Maintains the non-dominated set of solutions discovered across algorithms and iterations.

    Rules:
    - If a candidate is dominated by any existing member in the archive, it is discarded.
    - If a candidate is not dominated by any member, it is accepted into the archive,
      and all existing members that are now dominated by the candidate are removed.
    - If a candidate has the exact same objective vector as an existing solution, but represents
      a different solution (different sequence or modes), IT IS NOT DISCARDED. Both solutions
      are preserved to retain structural diversity.
    - If a candidate represents the exact same solution (identical genotype) already in the archive,
      it is not duplicated.
    """

    def __init__(self, initial_entries: Optional[Sequence[ArchiveEntry]] = None) -> None:
        self._entries: List[ArchiveEntry] = []
        if initial_entries:
            for entry in initial_entries:
                self.add_entry(entry)

    @property
    def entries(self) -> Tuple[ArchiveEntry, ...]:
        """Return an immutable snapshot of all entries currently in the archive."""
        return tuple(self._entries)

    @property
    def solutions(self) -> Tuple[Solution, ...]:
        """Return all solution genotypes currently in the archive."""
        return tuple(e.solution for e in self._entries)

    @property
    def schedules(self) -> Tuple[Schedule, ...]:
        """Return all schedule phenotypes currently in the archive."""
        return tuple(e.schedule for e in self._entries)

    @property
    def objectives(self) -> Tuple[ObjectiveValues, ...]:
        """Return all objective values currently in the archive."""
        return tuple(e.objectives for e in self._entries)

    @property
    def is_empty(self) -> bool:
        """True if the archive contains no entries, False otherwise."""
        return len(self._entries) == 0

    def __len__(self) -> int:
        return len(self._entries)

    def __iter__(self) -> Iterator[ArchiveEntry]:
        return iter(tuple(self._entries))

    def __contains__(self, item: Union[ArchiveEntry, Solution]) -> bool:
        if isinstance(item, ArchiveEntry):
            return item in self._entries
        if isinstance(item, Solution):
            return any(e.solution == item for e in self._entries)
        return False

    def clear(self) -> None:
        """Empty the archive."""
        self._entries.clear()

    def add(
        self,
        solution: Solution,
        schedule: Schedule,
        objectives: ObjectiveValues,
    ) -> bool:
        """Attempt to add a new solution to the archive.

        Args:
            solution: Solution genotype.
            schedule: Schedule phenotype.
            objectives: ObjectiveValues.

        Returns:
            True if the solution was accepted into the archive, False if discarded.
        """
        entry = ArchiveEntry(solution=solution, schedule=schedule, objectives=objectives)
        return self.add_entry(entry)

    def add_entry(self, entry: ArchiveEntry) -> bool:
        """Attempt to add an ArchiveEntry to the archive.

        Returns:
            True if the entry was added, False if discarded or duplicate.
        """
        # 1. Do not duplicate identical solution genotypes
        for existing in self._entries:
            if existing.solution == entry.solution:
                return False

        # 2. Check if candidate is dominated by any existing member
        for existing in self._entries:
            if dominates(existing.objectives, entry.objectives):
                return False

        # 3. Candidate is non-dominated: eliminate existing members dominated by the candidate
        self._entries = [
            existing for existing in self._entries if not dominates(entry.objectives, existing.objectives)
        ]

        # 4. Insert candidate into archive
        self._entries.append(entry)
        return True

    def update(
        self,
        entries: Sequence[Union[ArchiveEntry, Tuple[Solution, Schedule, ObjectiveValues]]],
    ) -> int:
        """Update the archive with multiple entries.

        Args:
            entries: Sequence of ArchiveEntry objects or (Solution, Schedule, ObjectiveValues) tuples.

        Returns:
            Number of entries accepted into the archive.
        """
        added_count = 0
        for item in entries:
            if isinstance(item, ArchiveEntry):
                if self.add_entry(item):
                    added_count += 1
            elif isinstance(item, (tuple, list)) and len(item) == 3:
                sol, sched, objs = item
                if self.add(sol, sched, objs):
                    added_count += 1
            else:
                raise TypeError(
                    f"Expected ArchiveEntry or (Solution, Schedule, ObjectiveValues) tuple, got {type(item)}"
                )
        return added_count
