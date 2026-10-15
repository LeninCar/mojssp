"""SPEA2 (Strength Pareto Evolutionary Algorithm 2) for MO-JSSP.

Multi-objective evolutionary algorithm utilizing fine-grained strength-based fitness
assignment, k-th nearest neighbor density estimation, and a deterministic archive
truncation procedure preserving non-dominated boundary extremes and diversity.
"""

from dataclasses import dataclass
import math
import random
from typing import Any, List, Optional, Sequence, Tuple, Union

from .algorithm_contract import AlgorithmBlockResult, PortfolioArm
from .decoder import Decoder
from .cooperation import GuidedMatingArm
from .dominance import dominates
from .evaluator import Evaluator, ObjectiveValues
from .instance import Instance
from .normalization import ObjectiveNormalizer, compute_instance_bounds
from .nsga2 import (
    crossover_pox,
    mutate_modes_per_gene,
    mutate_sequence_swap,
)
from .pareto_archive import ArchiveEntry, ParetoArchive
from .schedule import Schedule
from .solution import Solution


@dataclass
class SPEA2Individual:
    """Internal algorithmic individual pairing genotype, phenotype, objectives and SPEA2 fitness."""

    solution: Solution
    schedule: Schedule
    objectives: ObjectiveValues
    normalized_objectives: Tuple[float, float, float]
    strength: int = 0
    raw_fitness: float = 0.0
    density: float = 0.0
    fitness: float = 0.0


def calculate_spea2_fitness(
    individuals: Sequence[SPEA2Individual],
) -> None:
    """Compute SPEA2 fitness (Raw Fitness R + Density D) for a combined population.

    Algorithm:
    1. Strength S(i): count of individuals j in the population dominated by i.
    2. Raw Fitness R(i): sum of S(j) for all individuals j that dominate i.
       Non-dominated individuals in the set have R(i) = 0.
    3. Density D(i) = 1 / (sigma_i^k + 2), where sigma_i^k is the distance to the
       k-th nearest neighbor in normalized objective space, with k = floor(sqrt(|pop|)).
    4. Total Fitness F(i) = R(i) + D(i) (lower is better, F < 1 implies non-dominated).

    Args:
        individuals: Collection of SPEA2Individual to evaluate in-place.
    """
    n = len(individuals)
    if n == 0:
        return

    # 1. Compute Strength S(i) for each individual
    # S(i) = |{j in pop | i dominates j}|
    for i, ind_i in enumerate(individuals):
        s_count = 0
        for j, ind_j in enumerate(individuals):
            if i != j and dominates(ind_i.objectives, ind_j.objectives):
                s_count += 1
        ind_i.strength = s_count

    # 2. Compute Raw Fitness R(i)
    # R(i) = sum_{j | j dominates i} S(j)
    for i, ind_i in enumerate(individuals):
        r_sum = 0.0
        for j, ind_j in enumerate(individuals):
            if i != j and dominates(ind_j.objectives, ind_i.objectives):
                r_sum += ind_j.strength
        ind_i.raw_fitness = float(r_sum)

    # 3. Density Estimation D(i) via k-th nearest neighbor
    # k = floor(sqrt(n)), bounded by [1, n - 1]
    k_nn = max(1, min(int(math.floor(math.sqrt(n))), n - 1))

    for i, ind_i in enumerate(individuals):
        if n == 1:
            ind_i.density = 0.5
            ind_i.fitness = ind_i.raw_fitness + ind_i.density
            continue

        dists = [
            math.dist(ind_i.normalized_objectives, ind_j.normalized_objectives)
            for j, ind_j in enumerate(individuals)
            if i != j
        ]
        dists.sort()
        kth_dist = dists[k_nn - 1]
        density = 1.0 / (kth_dist + 2.0)
        ind_i.density = float(density)
        ind_i.fitness = ind_i.raw_fitness + ind_i.density


def truncate_archive(
    candidates: Sequence[SPEA2Individual], target_size: int
) -> List[SPEA2Individual]:
    """Deterministically truncate a set of non-dominated individuals to target_size.

    Iteratively removes the candidate with minimum distance to another individual.
    Ties in the first nearest distance are broken by comparing second nearest,
    third nearest, etc. (lexicographical distance vector ordering).

    Args:
        candidates: Sequence of non-dominated individuals to truncate.
        target_size: Target archive size (target_size < len(candidates)).

    Returns:
        List of target_size individuals with optimal boundary preservation.
    """
    remaining = list(candidates)

    while len(remaining) > target_size:
        min_distance_tuple: Optional[Tuple[float, ...]] = None
        worst_idx = -1

        for idx, ind in enumerate(remaining):
            # Compute sorted distances to all other remaining individuals
            dists = tuple(
                sorted(
                    math.dist(ind.normalized_objectives, other.normalized_objectives)
                    for j, other in enumerate(remaining)
                    if j != idx
                )
            )

            # Lexicographical comparison: smaller distance vector means more crowded
            if min_distance_tuple is None or dists < min_distance_tuple:
                min_distance_tuple = dists
                worst_idx = idx

        if worst_idx >= 0:
            remaining.pop(worst_idx)
        else:
            remaining.pop()

    return remaining


def environmental_selection(
    union_population: Sequence[SPEA2Individual], archive_size: int
) -> List[SPEA2Individual]:
    """Execute SPEA2 environmental selection from union population into next archive.

    Selects individuals into the environmental archive of size archive_size:
    - If non-dominated individuals count == archive_size: exact copy.
    - If non-dominated individuals count < archive_size: fill with best dominated
      individuals sorted by total fitness F ascending.
    - If non-dominated individuals count > archive_size: apply deterministic truncation.

    Args:
        union_population: Evaluated individuals from union (offspring + previous archive).
        archive_size: Fixed environmental archive capacity.

    Returns:
        List of exactly archive_size individuals.
    """
    # Non-dominated individuals in SPEA2 are strictly those with raw_fitness == 0 (F < 1)
    non_dominated = [ind for ind in union_population if ind.raw_fitness == 0.0]

    if len(non_dominated) == archive_size:
        return list(non_dominated)

    if len(non_dominated) < archive_size:
        # Fill remaining slots with best dominated individuals (lowest fitness F)
        dominated = [ind for ind in union_population if ind.raw_fitness > 0.0]
        dominated.sort(key=lambda ind: ind.fitness)
        needed = archive_size - len(non_dominated)
        return list(non_dominated) + dominated[:needed]

    # Overflow: apply deterministic truncation procedure
    return truncate_archive(non_dominated, target_size=archive_size)


def binary_tournament_spea2(
    p1: SPEA2Individual, p2: SPEA2Individual, rng: random.Random
) -> SPEA2Individual:
    """Binary tournament for SPEA2 based on total fitness F (lower is better)."""
    if p1.fitness < p2.fitness:
        return p1
    if p2.fitness < p1.fitness:
        return p2
    return p1 if rng.random() < 0.5 else p2


@dataclass(frozen=True)
class SPEA2Result:
    """Result container of a SPEA2 optimization run."""

    non_dominated_solutions: Tuple[Solution, ...]
    non_dominated_schedules: Tuple[Schedule, ...]
    non_dominated_objectives: Tuple[ObjectiveValues, ...]
    population: Tuple[Solution, ...]
    population_objectives: Tuple[ObjectiveValues, ...]
    archive_population: Tuple[Solution, ...]
    archive_objectives: Tuple[ObjectiveValues, ...]
    total_evaluations: int
    archive: ParetoArchive
    seed: Optional[int] = None


class SPEA2:
    """SPEA2 (Strength Pareto Evolutionary Algorithm 2) standalone implementation for MO-JSSP."""

    def __init__(
        self,
        population_size: int = 30,
        archive_size: int = 30,
        crossover_probability: float = 0.9,
        mutation_sequence_probability: float = 0.2,
        mutation_mode_per_gene_probability: Optional[float] = None,
        seed: Optional[int] = None,
        max_evaluations: Optional[int] = 1000,
    ) -> None:
        if population_size <= 0:
            raise ValueError(f"population_size must be positive, got {population_size}")
        if archive_size <= 0:
            raise ValueError(f"archive_size must be positive, got {archive_size}")
        if not (0.0 <= crossover_probability <= 1.0):
            raise ValueError(f"crossover_probability must be in [0, 1], got {crossover_probability}")
        if not (0.0 <= mutation_sequence_probability <= 1.0):
            raise ValueError(f"mutation_sequence_probability must be in [0, 1], got {mutation_sequence_probability}")
        if max_evaluations is not None and max_evaluations <= 0:
            raise ValueError(f"max_evaluations must be positive, got {max_evaluations}")

        self.population_size = population_size
        self.archive_size = archive_size
        self.crossover_probability = crossover_probability
        self.mutation_sequence_probability = mutation_sequence_probability
        self.mutation_mode_per_gene_probability = mutation_mode_per_gene_probability
        self.seed = seed
        self.max_evaluations = max_evaluations

    def run(self, instance: Instance) -> SPEA2Result:
        """Execute SPEA2 on the given instance up to max_evaluations."""
        budget = self.max_evaluations if self.max_evaluations is not None else 1000
        arm = SPEA2Arm(
            instance=instance,
            population_size=self.population_size,
            archive_size=self.archive_size,
            crossover_probability=self.crossover_probability,
            mutation_sequence_probability=self.mutation_sequence_probability,
            mutation_mode_per_gene_probability=self.mutation_mode_per_gene_probability,
            seed=self.seed,
            max_evaluations=budget,
        )

        arm.run(budget)

        archive = arm.current_archive
        pop = arm.population
        arch_pop = arm.archive_population

        return SPEA2Result(
            non_dominated_solutions=tuple(e.solution for e in archive.entries),
            non_dominated_schedules=tuple(e.schedule for e in archive.entries),
            non_dominated_objectives=tuple(e.objectives for e in archive.entries),
            population=tuple(ind.solution for ind in pop),
            population_objectives=tuple(ind.objectives for ind in pop),
            archive_population=tuple(ind.solution for ind in arch_pop),
            archive_objectives=tuple(ind.objectives for ind in arch_pop),
            total_evaluations=arm.total_evaluations,
            archive=archive,
            seed=self.seed,
        )


class SPEA2Arm(GuidedMatingArm):
    """Stateful portfolio arm implementing SPEA2 under the common PortfolioArm protocol.

    Preserves internal algorithmic state (population, environmental archive, partial
    offspring, pending sibling, RNG state) between calls to run(budget) to guarantee
    exact bit-for-bit trajectory continuity and zero budget overshoot.
    """

    def __init__(
        self,
        instance: Instance,
        population_size: int = 30,
        archive_size: int = 30,
        crossover_probability: float = 0.9,
        mutation_sequence_probability: float = 0.2,
        mutation_mode_per_gene_probability: Optional[float] = None,
        seed: Optional[int] = None,
        max_evaluations: Optional[int] = None,
    ) -> None:
        if population_size <= 0:
            raise ValueError(f"population_size must be positive, got {population_size}")
        if archive_size <= 0:
            raise ValueError(f"archive_size must be positive, got {archive_size}")
        if max_evaluations is not None and max_evaluations <= 0:
            raise ValueError(f"max_evaluations must be positive, got {max_evaluations}")

        self._instance = instance
        self._population_size = population_size
        self._archive_size = archive_size
        self._crossover_probability = crossover_probability
        self._mutation_sequence_probability = mutation_sequence_probability
        self._mutation_mode_per_gene_probability = mutation_mode_per_gene_probability
        self._max_evaluations = max_evaluations

        self._seed = seed if seed is not None else random.randint(0, 2**31 - 1)
        self._rng = random.Random(self._seed)

        self._p_mut_mode = (
            mutation_mode_per_gene_probability
            if mutation_mode_per_gene_probability is not None
            else (1.0 / instance.total_operations if instance.total_operations > 0 else 0.1)
        )

        self._decoder = Decoder()
        self._evaluator = Evaluator()
        self._normalizer = ObjectiveNormalizer(compute_instance_bounds(instance))

        # Persistent execution state
        self._population: List[SPEA2Individual] = []
        self._archive_population: List[SPEA2Individual] = []
        self._offspring_in_progress: List[SPEA2Individual] = []
        self._pending_sibling: Optional[Solution] = None
        self._external_archive = ParetoArchive()

        self._p0_initialized = False
        self._generations_completed = 0
        self._total_evaluations = 0
        self._completed = False

    @property
    def arm_name(self) -> str:
        return "SPEA2"

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
    def population(self) -> Tuple[SPEA2Individual, ...]:
        return tuple(self._population)

    @property
    def archive_population(self) -> Tuple[SPEA2Individual, ...]:
        return tuple(self._archive_population)

    @property
    def current_archive(self) -> ParetoArchive:
        return self._get_archive_snapshot()

    def _get_archive_snapshot(self) -> ParetoArchive:
        return ParetoArchive(initial_entries=self._external_archive.entries)

    def reset(self) -> None:
        """Reset the arm to its initial unexecuted state with its initial seed."""
        self._archive_guidance = None
        self._rng = random.Random(self._seed)
        self._population.clear()
        self._archive_population.clear()
        self._offspring_in_progress.clear()
        self._pending_sibling = None
        self._external_archive = ParetoArchive()
        self._p0_initialized = False
        self._generations_completed = 0
        self._total_evaluations = 0
        self._completed = False

    def run(self, budget: int) -> AlgorithmBlockResult:
        """Execute up to `budget` real evaluations and return the block result."""
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

        remaining_evals = (
            self._max_evaluations - self._total_evaluations
            if self._max_evaluations is not None
            else budget
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

        def _evaluate_sol(sol: Solution) -> SPEA2Individual:
            nonlocal evals_used
            sched = self._decoder.decode(self._instance, sol)
            objs = self._evaluator.evaluate(self._instance, sched)
            norm_objs = self._normalizer.normalize_tuple(objs)

            evals_used += 1
            self._total_evaluations += 1

            self._external_archive.add(sol, sched, objs)

            return SPEA2Individual(
                solution=sol,
                schedule=sched,
                objectives=objs,
                normalized_objectives=norm_objs,
            )

        # 1. Initialize population P_0
        while len(self._population) < self._population_size and evals_used < effective_budget:
            sol = Solution.random(self._instance, rng=self._rng)
            ind = _evaluate_sol(sol)
            self._population.append(ind)

        # First environmental selection on P_0 if not yet done
        if len(self._population) == self._population_size and not self._p0_initialized:
            calculate_spea2_fitness(self._population)
            self._archive_population = environmental_selection(self._population, self._archive_size)
            self._p0_initialized = True

        # 2. Generational evolution loop
        while evals_used < effective_budget and not self._completed:
            if (
                self._max_evaluations is not None
                and self._total_evaluations >= self._max_evaluations
            ):
                self._completed = True
                break

            while (
                len(self._offspring_in_progress) < self._population_size
                and evals_used < effective_budget
            ):
                # Check for pending sibling from prior block
                if self._pending_sibling is not None:
                    c_sol = self._pending_sibling
                    self._pending_sibling = None
                    if self._rng.random() < self._mutation_sequence_probability:
                        c_sol = mutate_sequence_swap(c_sol, self._rng)
                    c_sol = mutate_modes_per_gene(
                        c_sol, self._instance, self._p_mut_mode, self._rng
                    )
                    ind = _evaluate_sol(c_sol)
                    self._offspring_in_progress.append(ind)
                    continue

                # Select two parents from archive_population via binary tournament
                p1 = binary_tournament_spea2(
                    self._rng.choice(self._archive_population),
                    self._rng.choice(self._archive_population),
                    self._rng,
                )
                p2 = binary_tournament_spea2(
                    self._rng.choice(self._archive_population),
                    self._rng.choice(self._archive_population),
                    self._rng,
                )

                # Crossover
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

            # When offspring set is full, complete generation
            if len(self._offspring_in_progress) == self._population_size:
                union = self._offspring_in_progress + self._archive_population
                calculate_spea2_fitness(union)
                self._archive_population = environmental_selection(union, self._archive_size)
                self._population = self._offspring_in_progress
                self._offspring_in_progress = []
                self._generations_completed += 1

        if (
            self._max_evaluations is not None
            and self._total_evaluations >= self._max_evaluations
        ):
            self._completed = True

        return AlgorithmBlockResult(
            solutions=self._get_archive_snapshot(),
            evaluations_used=evals_used,
            completed=self._completed,
        )


def spea2(
    instance: Instance,
    population_size: int = 30,
    archive_size: int = 30,
    crossover_probability: float = 0.9,
    mutation_sequence_probability: float = 0.2,
    mutation_mode_per_gene_probability: Optional[float] = None,
    seed: Optional[int] = None,
    max_evaluations: Optional[int] = 1000,
) -> SPEA2Result:
    """Convenience function running SPEA2 on an instance."""
    algo = SPEA2(
        population_size=population_size,
        archive_size=archive_size,
        crossover_probability=crossover_probability,
        mutation_sequence_probability=mutation_sequence_probability,
        mutation_mode_per_gene_probability=mutation_mode_per_gene_probability,
        seed=seed,
        max_evaluations=max_evaluations,
    )
    return algo.run(instance)

