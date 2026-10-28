"""Local Search module (Cmax-focused) for MO-JSSP."""

from dataclasses import dataclass
import random
from typing import Dict, List, Optional, Sequence, Set, Tuple

from mojssp.model.critical_path import get_critical_sequence_indices
from mojssp.model.decoder import Decoder
from mojssp.metrics.dominance import dominates
from mojssp.model.evaluator import Evaluator, ObjectiveValues
from mojssp.model.instance import Instance
from mojssp.metrics.pareto_archive import ArchiveEntry
from mojssp.model.schedule import Schedule
from mojssp.model.solution import Solution


@dataclass(frozen=True)
class ArchiveAddResult:
    """Detailed result of attempting to add an entry to LocalParetoArchive.

    Attributes:
        accepted: True if the candidate was non-dominated and accepted into the archive.
        dominated_removed: Number of previously existing entries dominated and removed.
        pruned_by_capacity: True if an entry was removed to enforce max_size.
        candidate_remained: True if the candidate remains in the archive after capacity pruning.
        pareto_improvement: True if this candidate represents a genuine Pareto improvement:
            - it dominated and eliminated one or more existing members (dominated_removed > 0), OR
            - it entered an archive that had capacity (len < max_size) and remained,
              thus genuinely expanding the non-dominated front without being a crowding replacement.
    """

    accepted: bool
    dominated_removed: int
    pruned_by_capacity: bool
    candidate_remained: bool
    pareto_improvement: bool

    def __bool__(self) -> bool:
        return self.accepted


class LocalParetoArchive:
    """Bounded, independent Pareto Archive for Local Search.

    Attributes:
        max_size: Maximum capacity (default 10).
    """

    def __init__(self, max_size: int = 10) -> None:
        if max_size <= 0:
            raise ValueError(f"max_size must be positive, got {max_size}")
        self._max_size = max_size
        self._entries: List[ArchiveEntry] = []

    @property
    def max_size(self) -> int:
        return self._max_size

    @property
    def entries(self) -> Tuple[ArchiveEntry, ...]:
        return tuple(self._entries)

    @property
    def solutions(self) -> Tuple[Solution, ...]:
        return tuple(e.solution for e in self._entries)

    @property
    def schedules(self) -> Tuple[Schedule, ...]:
        return tuple(e.schedule for e in self._entries)

    @property
    def objectives(self) -> Tuple[ObjectiveValues, ...]:
        return tuple(e.objectives for e in self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    def __iter__(self):
        return iter(tuple(self._entries))

    def _prune_to_max_size(self) -> None:
        """Prune archive to max_size using Crowding Distance to maintain diversity.

        The mechanism calculates crowding distance across all objectives (Cmax, T, E),
        assigning infinite distance to the boundary solutions of each objective
        to prioritize the preservation of extreme solutions. When the archive exceeds
        max_size, the solution with the smallest crowding distance (the most crowded
        or redundant interior solution) is removed iteratively. Note that in the presence
        of multiple identical or tied objective values, extreme status is assigned to the
        boundary points detected along the sorted projections; the mechanism aims to preserve
        boundary diversity without guaranteeing all tied extremes in degenerate scenarios.
        """
        if len(self._entries) <= self._max_size:
            return

        n = len(self._entries)
        distances: Dict[int, float] = {i: 0.0 for i in range(n)}

        # Compute crowding distance across the 3 objectives
        obj_extractors = [
            lambda e: float(e.objectives.makespan),
            lambda e: float(e.objectives.tardiness),
            lambda e: float(e.objectives.energy),
        ]

        for extractor in obj_extractors:
            # Sort indices by objective
            sorted_indices = sorted(range(n), key=lambda idx: extractor(self._entries[idx]))
            # Boundary points get infinity
            distances[sorted_indices[0]] = float("inf")
            distances[sorted_indices[-1]] = float("inf")

            val_min = extractor(self._entries[sorted_indices[0]])
            val_max = extractor(self._entries[sorted_indices[-1]])
            norm = val_max - val_min

            if norm > 0.0:
                for k in range(1, n - 1):
                    prev_val = extractor(self._entries[sorted_indices[k - 1]])
                    next_val = extractor(self._entries[sorted_indices[k + 1]])
                    distances[sorted_indices[k]] += (next_val - prev_val) / norm

        # While over capacity, remove the entry with smallest crowding distance
        while len(self._entries) > self._max_size:
            min_idx = min(range(len(self._entries)), key=lambda idx: distances[idx])
            self._entries.pop(min_idx)
            if len(self._entries) > self._max_size:
                self._prune_to_max_size()
                break

    def add(
        self,
        solution: Solution,
        schedule: Schedule,
        objectives: ObjectiveValues,
    ) -> ArchiveAddResult:
        """Attempt to add a solution to the local archive.

        Returns:
            ArchiveAddResult containing detailed outcome and pareto_improvement flag.
        """
        entry = ArchiveEntry(solution=solution, schedule=schedule, objectives=objectives)
        return self.add_entry(entry)

    def add_entry(self, entry: ArchiveEntry) -> ArchiveAddResult:
        """Attempt to add an ArchiveEntry to the local archive.

        Returns:
            ArchiveAddResult with acceptance status, dominated count, pruning, and improvement flag.
        """
        # 1. Reject identical genotype duplicates
        for existing in self._entries:
            if existing.solution == entry.solution:
                return ArchiveAddResult(
                    accepted=False,
                    dominated_removed=0,
                    pruned_by_capacity=False,
                    candidate_remained=False,
                    pareto_improvement=False,
                )

        # 2. Check Pareto dominance: candidate dominated by existing member
        for existing in self._entries:
            if dominates(existing.objectives, entry.objectives):
                return ArchiveAddResult(
                    accepted=False,
                    dominated_removed=0,
                    pruned_by_capacity=False,
                    candidate_remained=False,
                    pareto_improvement=False,
                )

        # 3. Identify and remove existing entries dominated by the new entry
        dominated_entries = [
            existing for existing in self._entries if dominates(entry.objectives, existing.objectives)
        ]
        num_dominated = len(dominated_entries)

        self._entries = [
            existing for existing in self._entries if not dominates(entry.objectives, existing.objectives)
        ]

        # 4. Record capacity state before insertion and insert candidate
        size_before_insert = len(self._entries)
        self._entries.append(entry)

        # 5. Enforce capacity via crowding distance
        pruned = False
        if len(self._entries) > self._max_size:
            pruned = True
            self._prune_to_max_size()

        candidate_remained = entry in self._entries

        # Genuine Pareto improvement occurs if:
        # - candidate dominated one or more existing members (num_dominated > 0), OR
        # - candidate was accepted into an archive with available capacity (size_before_insert < max_size)
        #   and remained in the archive without being a crowding replacement.
        pareto_improvement = num_dominated > 0 or (candidate_remained and size_before_insert < self._max_size)

        return ArchiveAddResult(
            accepted=True,
            dominated_removed=num_dominated,
            pruned_by_capacity=pruned,
            candidate_remained=candidate_remained,
            pareto_improvement=pareto_improvement,
        )


@dataclass(frozen=True)
class LocalSearchResult:
    """Result of a Local Search execution on a candidate solution.

    Attributes:
        initial_solution: Genotype provided at the start of LS.
        initial_objectives: ObjectiveValues of the initial solution.
        local_archive: Independent LocalParetoArchive containing non-dominated solutions.
        refined_solutions: Tuple of non-dominated Solution genotypes discovered.
        iterations_run: Number of iterations executed.
        evaluations_count: Number of calls to Evaluator.evaluate() made during this LS run.
        stopped_reason: Reason for termination ("max_iterations", "no_improvement", "no_neighbors").
    """

    initial_solution: Solution
    initial_objectives: ObjectiveValues
    local_archive: LocalParetoArchive
    refined_solutions: Tuple[Solution, ...]
    iterations_run: int
    evaluations_count: int
    stopped_reason: str


class LocalSearch:
    """Cmax-focused Local Search for MO-JSSP.

    Operates exclusively via sequence swaps where at least one position
    belongs to a critical operation on the schedule. Modes remain invariant.
    """

    def __init__(
        self,
        max_iterations: int = 50,
        max_no_improvement: int = 20,
        max_neighbors: int = 20,
        max_archive_size: int = 10,
    ) -> None:
        self.max_iterations = max_iterations
        self.max_no_improvement = max_no_improvement
        self.max_neighbors = max_neighbors
        self.max_archive_size = max_archive_size

    def search(
        self,
        instance: Instance,
        solution: Solution,
        schedule: Optional[Schedule] = None,
        objectives: Optional[ObjectiveValues] = None,
        rng: Optional[random.Random] = None,
        decoder: Optional[Decoder] = None,
        evaluator: Optional[Evaluator] = None,
        eval_counter: Optional[List[int]] = None,
    ) -> LocalSearchResult:
        """Execute Cmax-focused Local Search starting from a solution.

        Args:
            instance: MO-JSSP instance.
            solution: Initial Solution genotype.
            schedule: Pre-decoded Schedule (optional).
            objectives: Pre-evaluated ObjectiveValues (optional).
            rng: random.Random instance for reproducible sampling.
            decoder: Decoder instance (optional).
            evaluator: Evaluator instance (optional).
            eval_counter: Optional mutable list [count] to increment for every evaluation.

        Returns:
            LocalSearchResult containing refined solutions and statistics.
        """
        if rng is None:
            rng = random.Random()
        if decoder is None:
            decoder = Decoder()
        if evaluator is None:
            evaluator = Evaluator()

        ls_evaluations = 0

        # Initial evaluation if not provided
        if schedule is None or objectives is None:
            schedule = decoder.decode(instance, solution)
            objectives = evaluator.evaluate(instance, schedule)
            ls_evaluations += 1
            if eval_counter is not None:
                eval_counter[0] += 1

        local_archive = LocalParetoArchive(max_size=self.max_archive_size)
        local_archive.add(solution, schedule, objectives)

        consecutive_no_improvement = 0
        iterations_run = 0
        stopped_reason = "max_iterations"

        for iteration in range(1, self.max_iterations + 1):
            iterations_run = iteration

            # Seleccionar solución base del archivo local Pareto:
            # - Selección de base -> Cmax-focused (orientada a menor Cmax para intensificar)
            # - Evaluación -> (Cmax, T, E) puramente multiobjetivo
            # - Aceptación -> Dominancia de Pareto estricta sobre (Cmax, T, E)
            # - Archivo local -> Conjunto de soluciones no dominadas
            # La intensificación focalizada en Cmax NO convierte la búsqueda en monoobjetivo.
            base_entry = min(local_archive.entries, key=lambda e: e.objectives.makespan)

            seq = base_entry.solution.sequence
            seq_len = len(seq)
            critical_indices = get_critical_sequence_indices(base_entry.schedule, seq)

            if not critical_indices or seq_len < 2:
                stopped_reason = "no_neighbors"
                break

            # Find all valid swap pairs (i, j) where i != j, seq[i] != seq[j],
            # and at least one position belongs to critical_indices
            valid_pairs: List[Tuple[int, int]] = []
            for i in critical_indices:
                for j in range(seq_len):
                    if i != j and seq[i] != seq[j]:
                        pair = (min(i, j), max(i, j))
                        valid_pairs.append(pair)

            # Deduplicate pairs
            valid_pairs = list(set(valid_pairs))

            if not valid_pairs:
                stopped_reason = "no_neighbors"
                break

            # Sample at most max_neighbors
            if len(valid_pairs) > self.max_neighbors:
                sampled_pairs = rng.sample(valid_pairs, self.max_neighbors)
            else:
                sampled_pairs = list(valid_pairs)
                rng.shuffle(sampled_pairs)

            iteration_improved = False

            for i, j in sampled_pairs:
                # Perform swap on sequence
                seq_list = list(seq)
                seq_list[i], seq_list[j] = seq_list[j], seq_list[i]
                neighbor_solution = Solution(sequence=tuple(seq_list), modes=base_entry.solution.modes)

                # Decode and evaluate
                neighbor_schedule = decoder.decode(instance, neighbor_solution)
                neighbor_objectives = evaluator.evaluate(instance, neighbor_schedule)

                ls_evaluations += 1
                if eval_counter is not None:
                    eval_counter[0] += 1

                # Attempt insertion into local archive
                add_result = local_archive.add(neighbor_solution, neighbor_schedule, neighbor_objectives)
                if add_result.pareto_improvement:
                    iteration_improved = True

            if iteration_improved:
                consecutive_no_improvement = 0
            else:
                consecutive_no_improvement += 1
                if consecutive_no_improvement >= self.max_no_improvement:
                    stopped_reason = "no_improvement"
                    break

        return LocalSearchResult(
            initial_solution=solution,
            initial_objectives=objectives,
            local_archive=local_archive,
            refined_solutions=local_archive.solutions,
            iterations_run=iterations_run,
            evaluations_count=ls_evaluations,
            stopped_reason=stopped_reason,
        )
