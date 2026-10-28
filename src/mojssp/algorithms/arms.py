"""Stateful algorithm arms implementing the common portfolio arm contract.

Phase 7.2 implementation of stateful arms capable of pausing and resuming execution
under a common evaluation budget B (calls to Evaluator.evaluate()).
"""

from dataclasses import dataclass
import math
import random
from typing import Dict, List, Optional, Tuple

from mojssp.algorithms.algorithm_contract import AlgorithmBlockResult, PortfolioArm
from mojssp.model.critical_path import get_critical_sequence_indices
from mojssp.algorithms.cooperation import GuidedMatingArm
from mojssp.model.decoder import Decoder
from mojssp.model.evaluator import Evaluator, ObjectiveValues
from mojssp.model.instance import Instance
from mojssp.algorithms.local_search import LocalParetoArchive
from mojssp.algorithms.mopso import (
    Particle,
    PersonalParetoArchive,
    calculate_entries_crowding_distance,
    generate_mode_moves,
    generate_sequence_moves,
    select_guide_by_crowding,
)
from mojssp.algorithms.nsga2 import (
    Individual,
    binary_tournament,
    calculate_crowding_distance,
    crossover_pox,
    fast_non_dominated_sort,
    mutate_modes_per_gene,
    mutate_sequence_swap,
)
from mojssp.metrics.pareto_archive import ArchiveEntry, ParetoArchive
from mojssp.model.schedule import Schedule
from mojssp.model.solution import Solution


class NSGA2Arm(GuidedMatingArm):
    """Stateful portfolio arm wrapping NSGA-II under the common arm contract.

    Preserves internal search state (population, partial offspring, pending sibling,
    RNG state, generation count, evaluation count) between calls to run(budget) to
    ensure exact bit-for-bit trajectory continuity under arbitrary budget cuts.
    """

    def __init__(
        self,
        instance: Instance,
        population_size: int = 40,
        max_generations: Optional[int] = 50,
        max_evaluations: Optional[int] = None,
        crossover_probability: float = 0.9,
        mutation_sequence_probability: float = 0.2,
        mutation_mode_per_gene_probability: Optional[float] = None,
        seed: Optional[int] = None,
    ) -> None:
        self._instance = instance
        self._population_size = population_size
        self._max_generations = max_generations
        self._max_evaluations = max_evaluations
        self._crossover_probability = crossover_probability
        self._mutation_sequence_probability = mutation_sequence_probability
        self._mutation_mode_per_gene_probability = mutation_mode_per_gene_probability
        self._seed = seed

        self._p_mut_mode = (
            mutation_mode_per_gene_probability
            if mutation_mode_per_gene_probability is not None
            else (1.0 / instance.total_operations if instance.total_operations > 0 else 0.1)
        )

        self._decoder = Decoder()
        self._evaluator = Evaluator()

        self._archive = ParetoArchive()
        self._rng = random.Random(seed)

        # Internal persistent state
        self._population: List[Individual] = []
        self._offspring_in_progress: List[Individual] = []
        self._pending_sibling: Optional[Solution] = None
        self._p0_sorted: bool = False
        self._generations_completed: int = 0
        self._total_evaluations: int = 0
        self._completed: bool = False

    @property
    def arm_name(self) -> str:
        return "NSGA-II"

    @property
    def total_evaluations(self) -> int:
        return self._total_evaluations

    @property
    def is_completed(self) -> bool:
        return self._completed

    @property
    def generations_completed(self) -> int:
        return self._generations_completed

    @property
    def current_archive(self) -> ParetoArchive:
        """Return a defensive copy of the arm's current ParetoArchive."""
        return self._get_archive_snapshot()

    def _get_archive_snapshot(self) -> ParetoArchive:
        return ParetoArchive(initial_entries=self._archive.entries)

    def reset(self) -> None:
        """Reset the arm to its initial unexecuted state."""
        self._archive_guidance = None
        self._archive = ParetoArchive()
        self._rng = random.Random(self._seed)
        self._population.clear()
        self._offspring_in_progress.clear()
        self._pending_sibling = None
        self._p0_sorted = False
        self._generations_completed = 0
        self._total_evaluations = 0
        self._completed = False

    def run(self, budget: int) -> AlgorithmBlockResult:
        """Execute up to `budget` real evaluations and return the block result.

        Args:
            budget: Maximum number of calls to Evaluator.evaluate() allowed in this block.

        Returns:
            AlgorithmBlockResult with the updated archive snapshot, evaluations used,
            and completion status.
        """
        if budget <= 0:
            return AlgorithmBlockResult(
                solutions=self._get_archive_snapshot(),
                evaluations_used=0,
                completed=self._completed,
            )

        if self._completed:
            return AlgorithmBlockResult(
                solutions=self._get_archive_snapshot(),
                evaluations_used=0,
                completed=True,
            )

        # Apply global evaluation limit if specified
        if self._max_evaluations is not None:
            remaining = max(0, self._max_evaluations - self._total_evaluations)
            effective_budget = min(budget, remaining)
            if effective_budget == 0:
                self._completed = True
                return AlgorithmBlockResult(
                    solutions=self._get_archive_snapshot(),
                    evaluations_used=0,
                    completed=True,
                )
        else:
            effective_budget = budget

        evals_used = 0

        def _evaluate_sol(sol: Solution) -> Individual:
            nonlocal evals_used
            sched = self._decoder.decode(self._instance, sol)
            objs = self._evaluator.evaluate(self._instance, sched)
            evals_used += 1
            self._total_evaluations += 1
            self._archive.add(sol, sched, objs)
            return Individual(solution=sol, schedule=sched, objectives=objs)

        # 1. Initialize population P_0 if not yet complete
        while len(self._population) < self._population_size and evals_used < effective_budget:
            sol = Solution.random(self._instance, rng=self._rng)
            ind = _evaluate_sol(sol)
            self._population.append(ind)

        if len(self._population) == self._population_size and not self._p0_sorted:
            fronts = fast_non_dominated_sort(self._population)
            for front in fronts:
                calculate_crowding_distance(front)
            self._p0_sorted = True

        if self._max_generations is not None and self._generations_completed >= self._max_generations:
            self._completed = True

        # 2. Generational evolution loop
        while evals_used < effective_budget and not self._completed:
            if self._max_generations is not None and self._generations_completed >= self._max_generations:
                self._completed = True
                break

            while len(self._offspring_in_progress) < self._population_size and evals_used < effective_budget:
                if self._pending_sibling is not None:
                    c_sol = self._pending_sibling
                    self._pending_sibling = None
                    if self._rng.random() < self._mutation_sequence_probability:
                        c_sol = mutate_sequence_swap(c_sol, self._rng)
                    c_sol = mutate_modes_per_gene(c_sol, self._instance, self._p_mut_mode, self._rng)
                    ind = _evaluate_sol(c_sol)
                    self._offspring_in_progress.append(ind)
                    continue

                p1 = binary_tournament(
                    self._rng.choice(self._population),
                    self._rng.choice(self._population),
                    self._rng,
                )
                p2 = binary_tournament(
                    self._rng.choice(self._population),
                    self._rng.choice(self._population),
                    self._rng,
                )

                if self._rng.random() < self._crossover_probability:
                    c1_sol, c2_sol = crossover_pox(
                        p1.solution, self._guided_parent(p2.solution), self._instance, self._rng
                    )
                else:
                    c1_sol, c2_sol = p1.solution, p2.solution

                # Child 1
                c1 = c1_sol
                if self._rng.random() < self._mutation_sequence_probability:
                    c1 = mutate_sequence_swap(c1, self._rng)
                c1 = mutate_modes_per_gene(c1, self._instance, self._p_mut_mode, self._rng)
                ind1 = _evaluate_sol(c1)
                self._offspring_in_progress.append(ind1)

                if (
                    len(self._offspring_in_progress) >= self._population_size
                    or evals_used >= effective_budget
                ):
                    self._pending_sibling = c2_sol
                    break

                # Child 2
                c2 = c2_sol
                if self._rng.random() < self._mutation_sequence_probability:
                    c2 = mutate_sequence_swap(c2, self._rng)
                c2 = mutate_modes_per_gene(c2, self._instance, self._p_mut_mode, self._rng)
                ind2 = _evaluate_sol(c2)
                self._offspring_in_progress.append(ind2)

            if len(self._offspring_in_progress) == self._population_size:
                combined = self._population + self._offspring_in_progress
                fronts = fast_non_dominated_sort(combined)
                new_population: List[Individual] = []
                for front in fronts:
                    calculate_crowding_distance(front)
                    if len(new_population) + len(front) <= self._population_size:
                        new_population.extend(front)
                    else:
                        needed = self._population_size - len(new_population)
                        front.sort(key=lambda ind: ind.crowding_distance, reverse=True)
                        new_population.extend(front[:needed])
                        break
                self._population = new_population
                self._generations_completed += 1
                self._offspring_in_progress = []
                self._pending_sibling = None

                if self._max_generations is not None and self._generations_completed >= self._max_generations:
                    self._completed = True

        if self._max_evaluations is not None and self._total_evaluations >= self._max_evaluations:
            self._completed = True

        return AlgorithmBlockResult(
            solutions=self._get_archive_snapshot(),
            evaluations_used=evals_used,
            completed=self._completed,
        )


class MOPSOArm:
    """MOPSO algorithm encapsulated as a stateful PortfolioArm.

    Executes in granular evaluation budget blocks (run(B)), preserving all internal
    state across invocations to achieve exact bitwise equivalence with continuous runs:
    - Particle positions and personal archives (with personal bests).
    - Global Pareto archive.
    - Global crowding distance cache (maintained across pause/resume intervals).
    - Iteration counter and current particle index (for mid-iteration interruptions).
    - Exact evaluation counter (no overshoot, strictly evaluations_used <= B).
    - Deterministic RNG trajectory.
    """

    def __init__(
        self,
        instance: Instance,
        population_size: int = 50,
        max_evaluations: Optional[int] = 2500,
        personal_archive_size: int = 10,
        global_crowding_interval: int = 10,
        seed: Optional[int] = None,
    ) -> None:
        if population_size < 2:
            raise ValueError("population_size must be >= 2")
        if max_evaluations is not None and max_evaluations <= 0:
            raise ValueError("max_evaluations must be positive")
        if personal_archive_size <= 0:
            raise ValueError("personal_archive_size must be positive")
        if global_crowding_interval <= 0:
            raise ValueError("global_crowding_interval must be positive")

        self._instance = instance
        self._population_size = population_size
        self._max_evaluations = max_evaluations
        self._personal_archive_size = personal_archive_size
        self._global_crowding_interval = global_crowding_interval

        self._seed = seed if seed is not None else random.randint(0, 2**31 - 1)
        self._rng = random.Random(self._seed)

        self._decoder = Decoder()
        self._evaluator = Evaluator()

        n_ops = len(instance.all_operations)
        self._vseq_max = max(1, math.floor(0.15 * n_ops))
        self._vmode_max = max(1, math.floor(0.08 * n_ops))
        self._seq_pbest_budget = math.floor(self._vseq_max / 2)
        self._seq_gbest_budget = self._vseq_max - self._seq_pbest_budget
        self._mode_pbest_budget = math.floor(self._vmode_max / 2)
        self._mode_gbest_budget = self._vmode_max - self._mode_pbest_budget

        # Swarm and execution state
        self._particles: List[Particle] = []
        self._particle_objectives: List[ObjectiveValues] = []
        self._global_archive = ParetoArchive()
        self._global_crowding: Dict[ArchiveEntry, float] = {}

        self._iterations = 0
        self._current_particle_index = 0
        self._total_evaluations = 0
        self._completed = False

    @property
    def arm_name(self) -> str:
        return "MOPSO"

    @property
    def total_evaluations(self) -> int:
        return self._total_evaluations

    @property
    def is_completed(self) -> bool:
        return self._completed

    @property
    def iterations(self) -> int:
        return self._iterations

    @property
    def current_particle_index(self) -> int:
        return self._current_particle_index

    @property
    def particles(self) -> Tuple[Particle, ...]:
        return tuple(self._particles)

    @property
    def particle_objectives(self) -> Tuple[ObjectiveValues, ...]:
        return tuple(self._particle_objectives)

    @property
    def global_archive(self) -> ParetoArchive:
        return self._get_archive_snapshot()

    @property
    def global_crowding(self) -> Dict[ArchiveEntry, float]:
        return dict(self._global_crowding)

    @property
    def current_archive(self) -> ParetoArchive:
        return self._get_archive_snapshot()

    def _get_archive_snapshot(self) -> ParetoArchive:
        return ParetoArchive(initial_entries=self._global_archive.entries)

    def reset(self) -> None:
        """Reset the arm to its initial unexecuted state with its initial seed."""
        self._rng = random.Random(self._seed)
        self._particles.clear()
        self._particle_objectives.clear()
        self._global_archive = ParetoArchive()
        self._global_crowding.clear()
        self._iterations = 0
        self._current_particle_index = 0
        self._total_evaluations = 0
        self._completed = False

    def run(self, budget: int) -> AlgorithmBlockResult:
        """Execute up to `budget` real evaluations and return the block result.

        Args:
            budget: Maximum number of calls to Evaluator.evaluate() permitted in this block.

        Returns:
            AlgorithmBlockResult with the updated archive snapshot, evaluations consumed,
            and completion status.
        """
        if budget <= 0:
            return AlgorithmBlockResult(
                solutions=self._get_archive_snapshot(),
                evaluations_used=0,
                completed=self._completed,
            )

        if self._completed:
            return AlgorithmBlockResult(
                solutions=self._get_archive_snapshot(),
                evaluations_used=0,
                completed=True,
            )

        # Apply global evaluation limit if specified
        remaining_evals = (
            self._max_evaluations - self._total_evaluations if self._max_evaluations is not None else budget
        )
        if remaining_evals <= 0:
            self._completed = True
            return AlgorithmBlockResult(
                solutions=self._get_archive_snapshot(),
                evaluations_used=0,
                completed=True,
            )

        effective_budget = min(budget, remaining_evals)
        evals_used = 0

        # Helper to decode and evaluate a solution
        def _evaluate_sol(sol: Solution) -> Tuple[Schedule, ObjectiveValues]:
            nonlocal evals_used
            sched = self._decoder.decode(self._instance, sol)
            objs = self._evaluator.evaluate(self._instance, sched)
            evals_used += 1
            self._total_evaluations += 1
            return sched, objs

        # 1. Swarm initialization if not yet complete
        while len(self._particles) < self._population_size and evals_used < effective_budget:
            sol = Solution.random(self._instance, rng=self._rng)
            sched, objs = _evaluate_sol(sol)

            p_archive = PersonalParetoArchive(max_size=self._personal_archive_size)
            p_archive.add(sol, sched, objs)
            self._global_archive.add(sol, sched, objs)

            self._particles.append(Particle(position=sol, personal_archive=p_archive))
            self._particle_objectives.append(objs)

        if self._max_evaluations is not None and self._total_evaluations >= self._max_evaluations:
            self._completed = True

        # 2. Main swarm evolution loop
        while evals_used < effective_budget and not self._completed:
            if self._current_particle_index == 0:
                self._iterations += 1
                if (
                    self._iterations == 1
                    or self._iterations % self._global_crowding_interval == 0
                    or not self._global_crowding
                ):
                    self._global_crowding = calculate_entries_crowding_distance(self._global_archive.entries)

            while self._current_particle_index < self._population_size and evals_used < effective_budget:
                if self._max_evaluations is not None and self._total_evaluations >= self._max_evaluations:
                    self._completed = True
                    break

                particle = self._particles[self._current_particle_index]
                p_idx = self._current_particle_index

                # Select pbest from particle's personal archive
                p_crowding = calculate_entries_crowding_distance(particle.personal_archive.entries)
                pbest_entry = select_guide_by_crowding(
                    particle.personal_archive.entries,
                    p_crowding,
                    self._rng,
                )

                # Select gbest from global archive
                active_global_entries = [
                    e for e in self._global_archive.entries if e in self._global_crowding
                ]
                if not active_global_entries:
                    self._global_crowding = calculate_entries_crowding_distance(self._global_archive.entries)
                    active_global_entries = list(self._global_archive.entries)

                gbest_entry = select_guide_by_crowding(
                    active_global_entries,
                    self._global_crowding,
                    self._rng,
                )

                # Sequential movement: current -> pbest -> intermediate -> gbest -> new_solution
                intermediate_seq = generate_sequence_moves(
                    particle.position.sequence,
                    pbest_entry.solution.sequence,
                    self._seq_pbest_budget,
                )
                new_seq = generate_sequence_moves(
                    intermediate_seq,
                    gbest_entry.solution.sequence,
                    self._seq_gbest_budget,
                )

                intermediate_modes = generate_mode_moves(
                    particle.position.modes,
                    pbest_entry.solution.modes,
                    self._mode_pbest_budget,
                    self._instance,
                )
                new_modes = generate_mode_moves(
                    intermediate_modes,
                    gbest_entry.solution.modes,
                    self._mode_gbest_budget,
                    self._instance,
                )

                new_solution = Solution(sequence=new_seq, modes=new_modes)
                new_sched, new_objs = _evaluate_sol(new_solution)

                # Update archives
                particle.personal_archive.add(new_solution, new_sched, new_objs)
                self._global_archive.add(new_solution, new_sched, new_objs)

                # Update particle position
                particle.position = new_solution
                self._particle_objectives[p_idx] = new_objs

                self._current_particle_index += 1

            if self._current_particle_index >= self._population_size:
                self._current_particle_index = 0

            if self._max_evaluations is not None and self._total_evaluations >= self._max_evaluations:
                self._completed = True

        return AlgorithmBlockResult(
            solutions=self._get_archive_snapshot(),
            evaluations_used=evals_used,
            completed=self._completed,
        )


@dataclass
class ActiveLSState:
    """State of an active Local Search execution on a candidate solution.

    Preserves exact intra-candidate LS state across budget-interrupted blocks:
    - local_archive: current state of the candidate's non-dominated local Pareto archive.
    - current_iteration: 1-indexed counter of the current Local Search iteration.
    - consecutive_no_improvement: consecutive iterations without Pareto improvements.
    - iteration_improved: whether the current iteration found at least one Pareto improvement.
    - sampled_pairs: cached swap pairs sampled for the current iteration (avoids RNG divergence).
    - pair_index: index of the next pair to evaluate within sampled_pairs.
    - base_entry_solution: solution genotype used as base for the current iteration's neighborhood.
    - base_entry_schedule: schedule corresponding to base_entry_solution.
    """

    local_archive: LocalParetoArchive
    current_iteration: int
    consecutive_no_improvement: int
    iteration_improved: bool
    sampled_pairs: List[Tuple[int, int]]
    pair_index: int
    base_entry_solution: Solution
    base_entry_schedule: Schedule

    @property
    def local_archive_entries(self) -> Tuple[ArchiveEntry, ...]:
        """Return defensive snapshot of entries in local Pareto archive."""
        return tuple(self.local_archive.entries)


class NSGA2LSArm:
    """NSGA-II + Local Search (memetic algorithm) encapsulated as a PortfolioArm.

    Executes in granular evaluation budget blocks (run(B)), preserving all internal
    state across invocations to achieve exact bitwise equivalence with continuous runs:
    - Population, partial offspring, and pending sibling (genetic phase).
    - Candidates for local search and current candidate index (memetic phase).
    - Active Local Search state (intra-candidate iteration, sampled pairs, base entry).
    - Cumulative evaluation counts (both total and LS-specific, with strictly ls <= total).
    - Exact evaluation counter (no overshoot, strictly evaluations_used <= B).
    - Deterministic RNG trajectory without reseeding.
    """

    def __init__(
        self,
        instance: Instance,
        population_size: int = 40,
        max_generations: Optional[int] = 50,
        max_evaluations: Optional[int] = None,
        crossover_probability: float = 0.9,
        mutation_sequence_probability: float = 0.2,
        mutation_mode_per_gene_probability: Optional[float] = None,
        ls_non_f1_ratio: float = 0.25,
        max_ls_iterations: int = 50,
        max_ls_no_improvement: int = 20,
        max_ls_neighbors: int = 20,
        max_ls_archive_size: int = 10,
        seed: Optional[int] = None,
    ) -> None:
        if population_size < 4:
            raise ValueError(f"population_size must be at least 4, got {population_size}")
        if max_generations is not None and max_generations < 1:
            raise ValueError(f"max_generations must be at least 1, got {max_generations}")
        if max_evaluations is not None and max_evaluations <= 0:
            raise ValueError("max_evaluations must be positive")
        if not (0.0 <= crossover_probability <= 1.0):
            raise ValueError(f"crossover_probability must be in [0, 1], got {crossover_probability}")
        if not (0.0 <= mutation_sequence_probability <= 1.0):
            raise ValueError(
                f"mutation_sequence_probability must be in [0, 1], got {mutation_sequence_probability}"
            )
        if not (0.0 <= ls_non_f1_ratio <= 1.0):
            raise ValueError(f"ls_non_f1_ratio must be in [0, 1], got {ls_non_f1_ratio}")
        if max_ls_iterations < 1:
            raise ValueError("max_ls_iterations must be at least 1")
        if max_ls_no_improvement < 1:
            raise ValueError("max_ls_no_improvement must be at least 1")
        if max_ls_neighbors < 1:
            raise ValueError("max_ls_neighbors must be at least 1")
        if max_ls_archive_size < 1:
            raise ValueError("max_ls_archive_size must be at least 1")

        self._instance = instance
        self._population_size = population_size
        self._max_generations = max_generations
        self._max_evaluations = max_evaluations
        self._crossover_probability = crossover_probability
        self._mutation_sequence_probability = mutation_sequence_probability
        self._mutation_mode_per_gene_probability = mutation_mode_per_gene_probability
        self._ls_non_f1_ratio = ls_non_f1_ratio
        self._max_ls_iterations = max_ls_iterations
        self._max_ls_no_improvement = max_ls_no_improvement
        self._max_ls_neighbors = max_ls_neighbors
        self._max_ls_archive_size = max_ls_archive_size

        self._seed = seed if seed is not None else random.randint(0, 2**31 - 1)
        self._rng = random.Random(self._seed)

        self._p_mut_mode = (
            mutation_mode_per_gene_probability
            if mutation_mode_per_gene_probability is not None
            else (1.0 / instance.total_operations if instance.total_operations > 0 else 0.1)
        )

        self._decoder = Decoder()
        self._evaluator = Evaluator()

        self._archive = ParetoArchive()

        # State machine and execution state
        self._phase = "INIT"
        self._population: List[Individual] = []
        self._offspring_in_progress: List[Individual] = []
        self._pending_sibling: Optional[Solution] = None
        self._candidates_for_ls: List[Individual] = []
        self._current_candidate_index: int = 0
        self._refined_individuals: List[Individual] = []
        self._active_ls_state: Optional[ActiveLSState] = None

        self._generations_completed: int = 0
        self._total_evaluations: int = 0
        self._ls_evaluations: int = 0
        self._completed: bool = False

    @property
    def arm_name(self) -> str:
        return "NSGA-II+LS"

    @property
    def total_evaluations(self) -> int:
        return self._total_evaluations

    @property
    def ls_evaluations(self) -> int:
        return self._ls_evaluations

    @property
    def is_completed(self) -> bool:
        return self._completed

    @property
    def generations_completed(self) -> int:
        return self._generations_completed

    @property
    def phase(self) -> str:
        return self._phase

    @property
    def population(self) -> Tuple[Individual, ...]:
        return tuple(self._population)

    @property
    def offspring_in_progress(self) -> Tuple[Individual, ...]:
        return tuple(self._offspring_in_progress)

    @property
    def pending_sibling(self) -> Optional[Solution]:
        return self._pending_sibling

    @property
    def candidates_for_ls(self) -> Tuple[Individual, ...]:
        return tuple(self._candidates_for_ls)

    @property
    def current_candidate_index(self) -> int:
        return self._current_candidate_index

    @property
    def refined_individuals(self) -> Tuple[Individual, ...]:
        return tuple(self._refined_individuals)

    @property
    def active_ls_state(self) -> Optional[ActiveLSState]:
        return self._active_ls_state

    @property
    def current_archive(self) -> ParetoArchive:
        return self._get_archive_snapshot()

    @property
    def archive(self) -> ParetoArchive:
        return self._get_archive_snapshot()

    def _get_archive_snapshot(self) -> ParetoArchive:
        return ParetoArchive(initial_entries=self._archive.entries)

    def reset(self) -> None:
        """Reset the arm to its initial unexecuted state with its initial seed."""
        self._rng = random.Random(self._seed)
        self._archive = ParetoArchive()
        self._phase = "INIT"
        self._population.clear()
        self._offspring_in_progress.clear()
        self._pending_sibling = None
        self._candidates_for_ls.clear()
        self._current_candidate_index = 0
        self._refined_individuals.clear()
        self._active_ls_state = None
        self._generations_completed = 0
        self._total_evaluations = 0
        self._ls_evaluations = 0
        self._completed = False

    def _setup_ls_iteration(
        self,
        local_arch: LocalParetoArchive,
        current_iteration: int,
        consecutive_no_improvement: int,
    ) -> Optional[ActiveLSState]:
        base_entry = min(local_arch.entries, key=lambda e: e.objectives.makespan)
        seq = base_entry.solution.sequence
        seq_len = len(seq)
        critical_indices = get_critical_sequence_indices(base_entry.schedule, seq)

        if not critical_indices or seq_len < 2:
            return None

        valid_pairs: List[Tuple[int, int]] = []
        for i in critical_indices:
            for j in range(seq_len):
                if i != j and seq[i] != seq[j]:
                    valid_pairs.append((min(i, j), max(i, j)))

        valid_pairs = list(set(valid_pairs))
        if not valid_pairs:
            return None

        if len(valid_pairs) > self._max_ls_neighbors:
            sampled_pairs = self._rng.sample(valid_pairs, self._max_ls_neighbors)
        else:
            sampled_pairs = list(valid_pairs)
            self._rng.shuffle(sampled_pairs)

        return ActiveLSState(
            local_archive=local_arch,
            current_iteration=current_iteration,
            consecutive_no_improvement=consecutive_no_improvement,
            iteration_improved=False,
            sampled_pairs=sampled_pairs,
            pair_index=0,
            base_entry_solution=base_entry.solution,
            base_entry_schedule=base_entry.schedule,
        )

    def run(self, budget: int) -> AlgorithmBlockResult:
        """Execute up to `budget` real evaluations and return the block result.

        Args:
            budget: Maximum number of calls to Evaluator.evaluate() permitted in this block.

        Returns:
            AlgorithmBlockResult with the updated archive snapshot, evaluations consumed,
            and completion status.
        """
        if budget <= 0:
            return AlgorithmBlockResult(
                solutions=self._get_archive_snapshot(),
                evaluations_used=0,
                completed=self._completed,
            )

        if self._completed:
            return AlgorithmBlockResult(
                solutions=self._get_archive_snapshot(),
                evaluations_used=0,
                completed=True,
            )

        # Apply global evaluation limit if specified
        remaining_evals = (
            self._max_evaluations - self._total_evaluations if self._max_evaluations is not None else budget
        )
        if remaining_evals <= 0:
            self._completed = True
            return AlgorithmBlockResult(
                solutions=self._get_archive_snapshot(),
                evaluations_used=0,
                completed=True,
            )

        effective_budget = min(budget, remaining_evals)
        evals_used = 0

        def _evaluate_genetic(sol: Solution) -> Individual:
            nonlocal evals_used
            sched = self._decoder.decode(self._instance, sol)
            objs = self._evaluator.evaluate(self._instance, sched)
            evals_used += 1
            self._total_evaluations += 1
            self._archive.add(sol, sched, objs)
            return Individual(solution=sol, schedule=sched, objectives=objs)

        def _evaluate_ls(sol: Solution) -> Tuple[Schedule, ObjectiveValues]:
            nonlocal evals_used
            sched = self._decoder.decode(self._instance, sol)
            objs = self._evaluator.evaluate(self._instance, sched)
            evals_used += 1
            self._total_evaluations += 1
            self._ls_evaluations += 1
            self._archive.add(sol, sched, objs)
            return sched, objs

        # 1. INIT Phase: Initialize population P_0 if not yet complete
        if self._phase == "INIT":
            while len(self._population) < self._population_size and evals_used < effective_budget:
                sol = Solution.random(self._instance, rng=self._rng)
                ind = _evaluate_genetic(sol)
                self._population.append(ind)

            if len(self._population) == self._population_size:
                fronts = fast_non_dominated_sort(self._population)
                for front in fronts:
                    calculate_crowding_distance(front)
                self._phase = "OFFSPRING"
                if self._max_generations is not None and self._generations_completed >= self._max_generations:
                    self._completed = True

        # 2. Main Evolution Loop
        while evals_used < effective_budget and not self._completed:
            if self._max_generations is not None and self._generations_completed >= self._max_generations:
                self._completed = True
                break

            # Phase OFFSPRING: Create offspring Q_t
            if self._phase == "OFFSPRING":
                while (
                    len(self._offspring_in_progress) < self._population_size and evals_used < effective_budget
                ):
                    if self._pending_sibling is not None:
                        c_sol = self._pending_sibling
                        self._pending_sibling = None
                        if self._rng.random() < self._mutation_sequence_probability:
                            c_sol = mutate_sequence_swap(c_sol, self._rng)
                        c_sol = mutate_modes_per_gene(c_sol, self._instance, self._p_mut_mode, self._rng)
                        ind = _evaluate_genetic(c_sol)
                        self._offspring_in_progress.append(ind)
                        continue

                    p1 = binary_tournament(
                        self._rng.choice(self._population),
                        self._rng.choice(self._population),
                        self._rng,
                    )
                    p2 = binary_tournament(
                        self._rng.choice(self._population),
                        self._rng.choice(self._population),
                        self._rng,
                    )

                    if self._rng.random() < self._crossover_probability:
                        c1_sol, c2_sol = crossover_pox(p1.solution, p2.solution, self._instance, self._rng)
                    else:
                        c1_sol, c2_sol = p1.solution, p2.solution

                    # Child 1
                    c1 = c1_sol
                    if self._rng.random() < self._mutation_sequence_probability:
                        c1 = mutate_sequence_swap(c1, self._rng)
                    c1 = mutate_modes_per_gene(c1, self._instance, self._p_mut_mode, self._rng)
                    ind1 = _evaluate_genetic(c1)
                    self._offspring_in_progress.append(ind1)

                    if (
                        len(self._offspring_in_progress) >= self._population_size
                        or evals_used >= effective_budget
                    ):
                        self._pending_sibling = c2_sol
                        break

                    # Child 2
                    c2 = c2_sol
                    if self._rng.random() < self._mutation_sequence_probability:
                        c2 = mutate_sequence_swap(c2, self._rng)
                    c2 = mutate_modes_per_gene(c2, self._instance, self._p_mut_mode, self._rng)
                    ind2 = _evaluate_genetic(c2)
                    self._offspring_in_progress.append(ind2)

                if len(self._offspring_in_progress) == self._population_size:
                    # Q_t is complete! Reconstruct R_t = P_t U Q_t on the fly
                    r_t = self._population + self._offspring_in_progress
                    fronts = fast_non_dominated_sort(r_t)

                    f1 = fronts[0] if fronts else []
                    f2_plus = [ind for front in fronts[1:] for ind in front]

                    num_non_f1 = int(round(len(f2_plus) * self._ls_non_f1_ratio))
                    if num_non_f1 > len(f2_plus):
                        num_non_f1 = len(f2_plus)

                    non_f1 = self._rng.sample(f2_plus, num_non_f1) if num_non_f1 > 0 else []

                    self._candidates_for_ls = list(f1) + non_f1
                    self._current_candidate_index = 0
                    self._refined_individuals = []
                    self._active_ls_state = None
                    self._phase = "LS"

            # Phase LS: Execute Local Search on candidate solutions
            if self._phase == "LS":
                while (
                    self._current_candidate_index < len(self._candidates_for_ls)
                    and evals_used < effective_budget
                ):
                    candidate = self._candidates_for_ls[self._current_candidate_index]

                    if self._active_ls_state is None:
                        local_arch = LocalParetoArchive(max_size=self._max_ls_archive_size)
                        local_arch.add(candidate.solution, candidate.schedule, candidate.objectives)

                        self._active_ls_state = self._setup_ls_iteration(
                            local_arch=local_arch,
                            current_iteration=1,
                            consecutive_no_improvement=0,
                        )
                        if self._active_ls_state is None:
                            for entry in local_arch.entries:
                                self._refined_individuals.append(
                                    Individual(entry.solution, entry.schedule, entry.objectives)
                                )
                            self._current_candidate_index += 1
                            continue

                    while (
                        self._active_ls_state.pair_index < len(self._active_ls_state.sampled_pairs)
                        and evals_used < effective_budget
                    ):
                        i, j = self._active_ls_state.sampled_pairs[self._active_ls_state.pair_index]
                        seq_list = list(self._active_ls_state.base_entry_solution.sequence)
                        seq_list[i], seq_list[j] = seq_list[j], seq_list[i]
                        neighbor_sol = Solution(
                            sequence=tuple(seq_list),
                            modes=self._active_ls_state.base_entry_solution.modes,
                        )
                        neighbor_sched, neighbor_objs = _evaluate_ls(neighbor_sol)
                        add_res = self._active_ls_state.local_archive.add(
                            neighbor_sol, neighbor_sched, neighbor_objs
                        )
                        if add_res.pareto_improvement:
                            self._active_ls_state.iteration_improved = True
                        self._active_ls_state.pair_index += 1

                    if self._active_ls_state.pair_index >= len(self._active_ls_state.sampled_pairs):
                        if self._active_ls_state.iteration_improved:
                            new_consec = 0
                        else:
                            new_consec = self._active_ls_state.consecutive_no_improvement + 1

                        if (
                            new_consec >= self._max_ls_no_improvement
                            or self._active_ls_state.current_iteration >= self._max_ls_iterations
                        ):
                            for entry in self._active_ls_state.local_archive.entries:
                                self._refined_individuals.append(
                                    Individual(entry.solution, entry.schedule, entry.objectives)
                                )
                            self._active_ls_state = None
                            self._current_candidate_index += 1
                        else:
                            next_iter = self._active_ls_state.current_iteration + 1
                            next_state = self._setup_ls_iteration(
                                local_arch=self._active_ls_state.local_archive,
                                current_iteration=next_iter,
                                consecutive_no_improvement=new_consec,
                            )
                            if next_state is None:
                                for entry in self._active_ls_state.local_archive.entries:
                                    self._refined_individuals.append(
                                        Individual(entry.solution, entry.schedule, entry.objectives)
                                    )
                                self._active_ls_state = None
                                self._current_candidate_index += 1
                            else:
                                self._active_ls_state = next_state

                if self._current_candidate_index >= len(self._candidates_for_ls):
                    r_t = self._population + self._offspring_in_progress
                    selection_pool = r_t + self._refined_individuals
                    augmented_fronts = fast_non_dominated_sort(selection_pool)

                    new_population: List[Individual] = []
                    for front in augmented_fronts:
                        calculate_crowding_distance(front)
                        if len(new_population) + len(front) <= self._population_size:
                            new_population.extend(front)
                        else:
                            needed = self._population_size - len(new_population)
                            front.sort(key=lambda ind: ind.crowding_distance, reverse=True)
                            new_population.extend(front[:needed])
                            break

                    self._population = new_population
                    self._generations_completed += 1
                    self._offspring_in_progress = []
                    self._pending_sibling = None
                    self._candidates_for_ls = []
                    self._current_candidate_index = 0
                    self._refined_individuals = []
                    self._active_ls_state = None

                    if (
                        self._max_generations is not None
                        and self._generations_completed >= self._max_generations
                    ):
                        self._completed = True
                    else:
                        self._phase = "OFFSPRING"

        if self._max_evaluations is not None and self._total_evaluations >= self._max_evaluations:
            self._completed = True

        return AlgorithmBlockResult(
            solutions=self._get_archive_snapshot(),
            evaluations_used=evals_used,
            completed=self._completed,
        )
