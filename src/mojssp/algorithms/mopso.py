"""Discrete Multi-Objective Particle Swarm Optimization (MOPSO) for MO-JSSP.

Phase 6 implementation of the algorithm portfolio (Algorithm A3).
Optimizes three independent criteria under SpeedScaling without scalarization:
    min F(S) = (Cmax, T, E)
"""

import math
import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from mojssp.model.decoder import Decoder, decode
from mojssp.metrics.dominance import dominates
from mojssp.model.evaluator import Evaluator, ObjectiveValues, evaluate
from mojssp.model.instance import Instance
from mojssp.metrics.pareto_archive import ArchiveEntry, ParetoArchive
from mojssp.model.schedule import Schedule
from mojssp.model.solution import Solution


class PersonalParetoArchive:
    """Bounded, personal Pareto Archive for an individual particle.

    Maintains up to `max_size` (default 10) non-dominated solutions discovered by
    a single particle. Pruning uses Crowding Distance to maintain diversity
    across the objective space (Cmax, T, E).
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
        """Prune archive to max_size using Crowding Distance.

        Assigns infinite crowding distance to boundary points in each objective,
        and iteratively evicts the interior entry with the smallest crowding distance.
        """
        if len(self._entries) <= self._max_size:
            return

        distances = calculate_entries_crowding_distance(self._entries)

        while len(self._entries) > self._max_size:
            min_entry = min(self._entries, key=lambda e: distances.get(e, 0.0))
            self._entries.remove(min_entry)
            if len(self._entries) > self._max_size:
                distances = calculate_entries_crowding_distance(self._entries)

    def add(
        self,
        solution: Solution,
        schedule: Schedule,
        objectives: ObjectiveValues,
    ) -> bool:
        """Attempt to add a solution to the particle's personal archive.

        Args:
            solution: Genotype.
            schedule: Phenotype.
            objectives: Evaluated criteria (Cmax, T, E).

        Returns:
            True if the entry was added and retained, False otherwise.
        """
        entry = ArchiveEntry(solution=solution, schedule=schedule, objectives=objectives)
        return self.add_entry(entry)

    def add_entry(self, entry: ArchiveEntry) -> bool:
        """Attempt to add a pre-constructed ArchiveEntry.

        Rejects duplicate genotypes and solutions dominated by existing entries.
        Removes any existing entries dominated by the new candidate.
        Prunes to max_size using crowding distance if necessary.
        """
        # Reject duplicate genotype
        for existing in self._entries:
            if existing.solution == entry.solution:
                return False

        # Check dominance against existing entries
        dominated_indices: List[int] = []
        for i, existing in enumerate(self._entries):
            if dominates(existing.objectives, entry.objectives):
                return False
            if dominates(entry.objectives, existing.objectives):
                dominated_indices.append(i)

        # Remove dominated solutions
        if dominated_indices:
            self._entries = [e for i, e in enumerate(self._entries) if i not in dominated_indices]

        self._entries.append(entry)

        if len(self._entries) > self._max_size:
            self._prune_to_max_size()

        return any(e.solution == entry.solution for e in self._entries)


@dataclass
class Particle:
    """A particle in the discrete swarm.

    Attributes:
        position: Current solution genotype (sequence, modes).
        personal_archive: Bounded archive of non-dominated solutions discovered by this particle.
    """

    position: Solution
    personal_archive: PersonalParetoArchive


def calculate_entries_crowding_distance(entries: Sequence[ArchiveEntry]) -> Dict[ArchiveEntry, float]:
    """Compute 3D crowding distance for a sequence of ArchiveEntry objects.

    Assigns float('inf') to boundary extreme points along each objective (Cmax, T, E)
    and sums normalized neighbor distances for interior solutions.

    Args:
        entries: Sequence of non-dominated archive entries.

    Returns:
        Mapping from ArchiveEntry to its crowding distance.
    """
    if not entries:
        return {}

    n = len(entries)
    if n <= 2:
        return {e: float("inf") for e in entries}

    distances: Dict[ArchiveEntry, float] = {e: 0.0 for e in entries}

    obj_extractors = [
        lambda e: float(e.objectives.makespan),
        lambda e: float(e.objectives.tardiness),
        lambda e: float(e.objectives.energy),
    ]

    for extractor in obj_extractors:
        sorted_entries = sorted(entries, key=extractor)
        distances[sorted_entries[0]] = float("inf")
        distances[sorted_entries[-1]] = float("inf")

        val_min = extractor(sorted_entries[0])
        val_max = extractor(sorted_entries[-1])
        span = val_max - val_min

        if span > 0.0:
            for k in range(1, n - 1):
                if not math.isinf(distances[sorted_entries[k]]):
                    prev_val = extractor(sorted_entries[k - 1])
                    next_val = extractor(sorted_entries[k + 1])
                    distances[sorted_entries[k]] += (next_val - prev_val) / span

    return distances


def select_guide_by_crowding(
    entries: Sequence[ArchiveEntry],
    crowding_distances: Dict[ArchiveEntry, float],
    rng: random.Random,
) -> ArchiveEntry:
    """Select a guide entry using crowding-based probabilistic selection.

    Rule:
    - If there are solutions with infinite crowding distance, select uniformly among them.
    - Otherwise, select with probability proportional to Crowding Distance:
      P_i = CD_i / sum(CD_j).
    - If all crowding distances are zero, select uniformly among all candidates.

    Args:
        entries: Available candidates to select from.
        crowding_distances: Mapping of candidate to crowding distance.
        rng: Deterministic random generator.

    Returns:
        Selected ArchiveEntry.
    """
    if not entries:
        raise ValueError("Cannot select guide from empty entries.")

    inf_candidates = [e for e in entries if math.isinf(crowding_distances.get(e, 0.0))]
    if inf_candidates:
        return rng.choice(inf_candidates)

    weights = [crowding_distances.get(e, 0.0) for e in entries]
    total_weight = sum(weights)

    if total_weight <= 0.0:
        return rng.choice(list(entries))

    return rng.choices(list(entries), weights=weights, k=1)[0]


def generate_sequence_moves(
    current_seq: Sequence[int],
    guide_seq: Sequence[int],
    budget: int,
) -> Tuple[int, ...]:
    """Generate and apply sequential swaps to move current_seq toward guide_seq.

    Scans positions k where current_seq[k] != guide_seq[k], finds the earliest
    subsequent position j > k with current_seq[j] == guide_seq[k], and swaps them.
    Applies swaps directly to a mutable working sequence until reaching guide_seq
    or exhausting the budget.

    Preserves exact job multiplicities of Bierwirth representation.

    Args:
        current_seq: Current operation-based sequence.
        guide_seq: Target guide sequence.
        budget: Maximum number of swaps allowed.

    Returns:
        New valid sequence resulting from the applied swaps.
    """
    if budget <= 0:
        return tuple(current_seq)

    working = list(current_seq)
    n = len(working)
    swaps_applied = 0

    for k in range(n):
        if swaps_applied >= budget:
            break
        if working[k] != guide_seq[k]:
            target_job = guide_seq[k]
            # Find earliest j > k where working[j] == target_job
            swap_j = -1
            for j in range(k + 1, n):
                if working[j] == target_job:
                    swap_j = j
                    break
            if swap_j != -1:
                working[k], working[swap_j] = working[swap_j], working[k]
                swaps_applied += 1

    return tuple(working)


def generate_mode_moves(
    current_modes: Sequence[int],
    guide_modes: Sequence[int],
    budget: int,
    instance: Instance,
) -> Tuple[int, ...]:
    """Generate and apply ChangeMode moves to move current_modes toward guide_modes.

    Compares current_modes with guide_modes, identifies differences, and changes
    mode at index k to guide_modes[k] provided it is valid for operation k.
    Stops when the budget is reached or no more differences exist.

    Args:
        current_modes: Current mode vector.
        guide_modes: Target guide mode vector.
        budget: Maximum number of mode changes allowed.
        instance: Problem instance for mode validity verification.

    Returns:
        New valid mode tuple resulting from the applied mode changes.
    """
    if budget <= 0:
        return tuple(current_modes)

    working = list(current_modes)
    n = len(working)
    moves_applied = 0

    for k in range(n):
        if moves_applied >= budget:
            break
        if working[k] != guide_modes[k]:
            target_mode = guide_modes[k]
            op = instance.all_operations[k]
            valid_mode_ids = {m.mode_id for m in op.modes}
            if target_mode in valid_mode_ids:
                working[k] = target_mode
                moves_applied += 1

    return tuple(working)


@dataclass(frozen=True)
class MOPSOResult:
    """Result of a discrete MOPSO optimization run.

    Attributes:
        archive: Global Pareto Archive containing non-dominated solutions.
        iterations: Number of swarm iterations completed.
        total_evaluations: Total real calls to Evaluator.evaluate().
        seed: Random seed used for reproducibility.
        population: Final positions of the swarm particles.
        population_objectives: Evaluated criteria of the final swarm positions.
    """

    archive: ParetoArchive
    iterations: int
    total_evaluations: int
    seed: int
    population: Tuple[Solution, ...]
    population_objectives: Tuple[ObjectiveValues, ...]

    @property
    def non_dominated_solutions(self) -> Tuple[Solution, ...]:
        return tuple(e.solution for e in self.archive.entries)

    @property
    def non_dominated_schedules(self) -> Tuple[Schedule, ...]:
        return tuple(e.schedule for e in self.archive.entries)

    @property
    def non_dominated_objectives(self) -> Tuple[ObjectiveValues, ...]:
        return tuple(e.objectives for e in self.archive.entries)


class MOPSO:
    """Discrete Multi-Objective Particle Swarm Optimization for MO-JSSP.

    Parameters:
        population_size: Swarm size (aligned with NSGA-II population_size).
        max_evaluations: Total computational evaluation budget.
        personal_archive_size: Capacity of each particle's personal archive (default 10).
        global_crowding_interval: Iteration interval for recomputing global crowding (default 10).
    """

    def __init__(
        self,
        population_size: int = 50,
        max_evaluations: int = 2500,
        personal_archive_size: int = 10,
        global_crowding_interval: int = 10,
    ) -> None:
        if population_size < 2:
            raise ValueError(f"population_size must be at least 2, got {population_size}")
        if max_evaluations < population_size:
            raise ValueError(
                f"max_evaluations ({max_evaluations}) must be at least population_size ({population_size})"
            )
        if personal_archive_size < 1:
            raise ValueError(f"personal_archive_size must be at least 1, got {personal_archive_size}")
        if global_crowding_interval < 1:
            raise ValueError(f"global_crowding_interval must be at least 1, got {global_crowding_interval}")

        self._population_size = population_size
        self._max_evaluations = max_evaluations
        self._personal_archive_size = personal_archive_size
        self._global_crowding_interval = global_crowding_interval

    @property
    def population_size(self) -> int:
        return self._population_size

    @property
    def max_evaluations(self) -> int:
        return self._max_evaluations

    def run(self, instance: Instance, seed: Optional[int] = None) -> MOPSOResult:
        """Execute discrete MOPSO on the given instance.

        Args:
            instance: MO-JSSP instance.
            seed: Optional integer seed for deterministic reproducibility.

        Returns:
            MOPSOResult containing global Pareto archive, final swarm, and metrics.
        """
        resolved_seed = seed if seed is not None else random.randint(0, 2**31 - 1)
        rng = random.Random(resolved_seed)

        decoder = Decoder()
        evaluator = Evaluator()
        global_archive = ParetoArchive()

        n_ops = len(instance.all_operations)

        # Velocity limits:
        # Vseq_max = max(1, floor(0.15 * N))
        # Vmode_max = max(1, floor(0.08 * N))
        vseq_max = max(1, math.floor(0.15 * n_ops))
        vmode_max = max(1, math.floor(0.08 * n_ops))

        # 50/50 budget distribution (odd remainder assigned to gbest):
        seq_pbest_budget = math.floor(vseq_max / 2)
        seq_gbest_budget = vseq_max - seq_pbest_budget

        mode_pbest_budget = math.floor(vmode_max / 2)
        mode_gbest_budget = vmode_max - mode_pbest_budget

        # Swarm initialization
        particles: List[Particle] = []
        particle_objectives: List[ObjectiveValues] = []
        total_evaluations = 0

        for _ in range(self._population_size):
            if total_evaluations >= self._max_evaluations:
                break
            sol = Solution.random(instance, rng)
            sched = decoder.decode(instance, sol)
            objs = evaluator.evaluate(instance, sched)
            total_evaluations += 1

            p_archive = PersonalParetoArchive(max_size=self._personal_archive_size)
            p_archive.add(sol, sched, objs)
            global_archive.add(sol, sched, objs)

            particles.append(Particle(position=sol, personal_archive=p_archive))
            particle_objectives.append(objs)

        iterations = 0
        global_crowding: Dict[ArchiveEntry, float] = {}

        # Swarm iterations
        while total_evaluations < self._max_evaluations:
            iterations += 1

            # Recalculate global crowding every global_crowding_interval iterations and at iteration 1.
            # Metodología de eficiencia deliberada:
            # 1. El crowding global se calcula periódicamente (iteración 1 y cada global_crowding_interval).
            # 2. El archivo global puede recibir nuevas soluciones entre recálculos periódicos.
            # 3. Las entradas agregadas entre dos recálculos no provocan un recálculo anticipado y permanecen
            #    en ParetoArchive, pero no son elegibles temporalmente como gbest hasta el siguiente recálculo.
            # 4. Esta política es intencional para evitar recálculos O(N log N) por partícula o por inserción.
            if iterations == 1 or iterations % self._global_crowding_interval == 0 or not global_crowding:
                global_crowding = calculate_entries_crowding_distance(global_archive.entries)

            stopped_early = False

            for p_idx, particle in enumerate(particles):
                if total_evaluations >= self._max_evaluations:
                    stopped_early = True
                    break

                # 1. Select pbest from particle's personal archive
                p_crowding = calculate_entries_crowding_distance(particle.personal_archive.entries)
                pbest_entry = select_guide_by_crowding(
                    particle.personal_archive.entries,
                    p_crowding,
                    rng,
                )

                # 2. Select gbest from global archive
                # Filtrado intencional de candidatos para gbest:
                # Solo son elegibles las soluciones que existen tanto en global_archive como en global_crowding.
                # Las soluciones nuevas descubiertas durante iteraciones intermedias esperan al siguiente
                # recálculo periódico del crowding global para participar como gbest.
                # Asimismo, si una solución previa fue eliminada de global_archive por dominancia,
                # se excluye aquí inmediatamente mediante la condición 'e in global_archive.entries'.
                active_global_entries = [e for e in global_archive.entries if e in global_crowding]
                if not active_global_entries:
                    # En el caso extremo de que todas las entradas del cálculo anterior hayan sido dominadas,
                    # se recalcula inmediatamente para garantizar un conjunto no vacío de guías.
                    global_crowding = calculate_entries_crowding_distance(global_archive.entries)
                    active_global_entries = list(global_archive.entries)

                gbest_entry = select_guide_by_crowding(
                    active_global_entries,
                    global_crowding,
                    rng,
                )

                # 3. Sequential movement: current -> pbest -> intermediate -> gbest -> new_solution
                # Sequence moves
                intermediate_seq = generate_sequence_moves(
                    particle.position.sequence,
                    pbest_entry.solution.sequence,
                    seq_pbest_budget,
                )
                new_seq = generate_sequence_moves(
                    intermediate_seq,
                    gbest_entry.solution.sequence,
                    seq_gbest_budget,
                )

                # Mode moves
                intermediate_modes = generate_mode_moves(
                    particle.position.modes,
                    pbest_entry.solution.modes,
                    mode_pbest_budget,
                    instance,
                )
                new_modes = generate_mode_moves(
                    intermediate_modes,
                    gbest_entry.solution.modes,
                    mode_gbest_budget,
                    instance,
                )

                new_solution = Solution(sequence=new_seq, modes=new_modes)
                new_sched = decoder.decode(instance, new_solution)
                new_objs = evaluator.evaluate(instance, new_sched)
                total_evaluations += 1

                # Update archives
                particle.personal_archive.add(new_solution, new_sched, new_objs)
                global_archive.add(new_solution, new_sched, new_objs)

                # Update particle position
                particle.position = new_solution
                particle_objectives[p_idx] = new_objs

            if stopped_early:
                break

        return MOPSOResult(
            archive=global_archive,
            iterations=iterations,
            total_evaluations=total_evaluations,
            seed=resolved_seed,
            population=tuple(p.position for p in particles),
            population_objectives=tuple(particle_objectives),
        )


def mopso(
    instance: Instance,
    population_size: int = 50,
    max_evaluations: int = 2500,
    personal_archive_size: int = 10,
    global_crowding_interval: int = 10,
    seed: Optional[int] = None,
) -> MOPSOResult:
    """Convenience function to run discrete MOPSO on an instance."""
    algo = MOPSO(
        population_size=population_size,
        max_evaluations=max_evaluations,
        personal_archive_size=personal_archive_size,
        global_crowding_interval=global_crowding_interval,
    )
    return algo.run(instance, seed=seed)
