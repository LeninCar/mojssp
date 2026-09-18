"""NSGA-II (Non-dominated Sorting Genetic Algorithm II) for MO-JSSP."""

import random
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence, Set, Tuple

from .decoder import Decoder
from .evaluator import Evaluator, ObjectiveValues
from .instance import Instance
from .schedule import Schedule
from .solution import Solution


@dataclass(eq=False)
class Individual:
    """Internal algorithmic individual pairing genotype, phenotype, and NSGA-II metadata.

    The problem representation Solution remains a pure genotype; Individual wraps it
    with its evaluated Schedule, ObjectiveValues, Pareto rank, and crowding distance.
    """

    solution: Solution
    schedule: Schedule
    objectives: ObjectiveValues
    rank: int = 0
    crowding_distance: float = 0.0


@dataclass(frozen=True)
class NSGA2Result:
    """Result of an NSGA-II optimization run.

    Rationale for retaining Solution, Schedule, and ObjectiveValues:
    - Solution (Genotype): Allows downstream operators (e.g. Local Search, portfolio algorithms)
      to continue manipulating the combinatorial representation directly.
    - Schedule (Phenotype): Retains the concrete timeline allocation, enabling immediate
      auditing via ScheduleValidator, Gantt charting, and machine utilization analysis
      without requiring re-decoding.
    - ObjectiveValues (Objective Space): Provides coordinates (Cmax, T, E) for Pareto front
      characterization, hypervolume computation, and multi-criteria decision making.
    """

    non_dominated_solutions: Tuple[Solution, ...]
    non_dominated_schedules: Tuple[Schedule, ...]
    non_dominated_objectives: Tuple[ObjectiveValues, ...]
    population: Tuple[Solution, ...]
    population_objectives: Tuple[ObjectiveValues, ...]


def dominates(a: ObjectiveValues, b: ObjectiveValues) -> bool:
    """Check if objective vector a dominates objective vector b in minimization.

    a dominates b iff:
        a_i <= b_i for all objectives i, and
        a_j < b_j for at least one objective j.
    """
    a_vals = (a.makespan, a.tardiness, a.energy)
    b_vals = (b.makespan, b.tardiness, b.energy)
    all_le = all(x <= y for x, y in zip(a_vals, b_vals))
    any_lt = any(x < y for x, y in zip(a_vals, b_vals))
    return all_le and any_lt


def fast_non_dominated_sort(population: Sequence[Individual]) -> List[List[Individual]]:
    """Partition a population into Pareto fronts (F1, F2, ...) using Deb's fast sorting.

    Assigns 1-based rank to each individual (F1 -> rank 1, F2 -> rank 2, etc.).

    Args:
        population: Collection of Individual instances to sort.

    Returns:
        List of fronts, where each front is a list of Individuals.
    """
    front_indices: List[List[int]] = [[]]
    # S[p]: list of indices dominated by p
    dominated_by_p: Dict[int, List[int]] = {i: [] for i in range(len(population))}
    # n[p]: number of individuals that dominate p
    domination_counter: Dict[int, int] = {i: 0 for i in range(len(population))}

    for i, p in enumerate(population):
        for j, q in enumerate(population):
            if i == j:
                continue
            if dominates(p.objectives, q.objectives):
                dominated_by_p[i].append(j)
            elif dominates(q.objectives, p.objectives):
                domination_counter[i] += 1

        if domination_counter[i] == 0:
            p.rank = 1
            front_indices[0].append(i)

    curr_idx = 0
    while curr_idx < len(front_indices) and front_indices[curr_idx]:
        next_front: List[int] = []
        for p_idx in front_indices[curr_idx]:
            for q_idx in dominated_by_p[p_idx]:
                domination_counter[q_idx] -= 1
                if domination_counter[q_idx] == 0:
                    population[q_idx].rank = curr_idx + 2
                    next_front.append(q_idx)
        if next_front:
            front_indices.append(next_front)
        curr_idx += 1

    return [[population[idx] for idx in f] for f in front_indices if f]



def calculate_crowding_distance(front: List[Individual]) -> None:
    """Compute and assign the crowding distance to all individuals within a front.

    Handles boundary extremes with float('inf') and prevents zero-division
    when all solutions in a front have identical values for an objective.
    """
    if not front:
        return

    n = len(front)
    if n <= 2:
        for ind in front:
            ind.crowding_distance = float("inf")
        return

    for ind in front:
        ind.crowding_distance = 0.0

    getters: List[Callable[[Individual], float]] = [
        lambda ind: ind.objectives.makespan,
        lambda ind: ind.objectives.tardiness,
        lambda ind: ind.objectives.energy,
    ]

    for getter in getters:
        front.sort(key=getter)
        front[0].crowding_distance = float("inf")
        front[-1].crowding_distance = float("inf")

        min_val = getter(front[0])
        max_val = getter(front[-1])
        span = max_val - min_val

        if span > 0:
            for i in range(1, n - 1):
                if front[i].crowding_distance != float("inf"):
                    front[i].crowding_distance += (getter(front[i + 1]) - getter(front[i - 1])) / span


def binary_tournament(p1: Individual, p2: Individual, rng: random.Random) -> Individual:
    """Crowded comparison operator: lower rank wins; higher crowding distance breaks ties."""
    if p1.rank < p2.rank:
        return p1
    if p2.rank < p1.rank:
        return p2
    if p1.crowding_distance > p2.crowding_distance:
        return p1
    if p2.crowding_distance > p1.crowding_distance:
        return p2
    return p1 if rng.random() < 0.5 else p2


def crossover_pox(
    parent1: Solution,
    parent2: Solution,
    instance: Instance,
    rng: random.Random,
) -> Tuple[Solution, Solution]:
    """Precedence-Preserving Order Crossover (POX) for Bierwirth operation-based representation.

    POX preserva el orden relativo de las apariciones de cada Job, manteniendo la interpretación
    tecnológica de la representación Operation-Based/Bierwirth. El orden relativo entre Jobs
    diferentes puede cambiar y forma parte del espacio de búsqueda.

    1. A subset of jobs J1 is selected at random. J2 is the complement.
    2. In Child 1, operations belonging to jobs in J1 are copied from Parent 1 in their exact positions.
    3. The remaining slots in Child 1 are filled with operations belonging to J2 in the relative order
       they appear in Parent 2.
    4. Child 2 is constructed symmetrically (J1 from Parent 2, J2 from Parent 1).
    5. The mode vector inherits modes corresponding to jobs in J1 from Parent 1 and J2 from Parent 2
       (and vice-versa for Child 2).

    This strictly preserves the exact n_j frequencies for every job without repair.
    """
    all_job_ids = [job.job_id for job in instance.jobs]
    k = max(1, len(all_job_ids) // 2)
    j1: Set[int] = set(rng.sample(all_job_ids, k))

    n = len(parent1.sequence)

    # Construct Child 1 sequence
    c1_seq: List[Optional[int]] = [None] * n
    for i, j_id in enumerate(parent1.sequence):
        if j_id in j1:
            c1_seq[i] = j_id

    fill_idx_c1 = 0
    for j_id in parent2.sequence:
        if j_id not in j1:
            while c1_seq[fill_idx_c1] is not None:
                fill_idx_c1 += 1
            c1_seq[fill_idx_c1] = j_id

    # Construct Child 2 sequence
    c2_seq: List[Optional[int]] = [None] * n
    for i, j_id in enumerate(parent2.sequence):
        if j_id in j1:
            c2_seq[i] = j_id

    fill_idx_c2 = 0
    for j_id in parent1.sequence:
        if j_id not in j1:
            while c2_seq[fill_idx_c2] is not None:
                fill_idx_c2 += 1
            c2_seq[fill_idx_c2] = j_id

    # Inherit modes aligned with instance.all_operations
    c1_modes: List[int] = []
    c2_modes: List[int] = []
    for idx, op in enumerate(instance.all_operations):
        if op.job_id in j1:
            c1_modes.append(parent1.modes[idx])
            c2_modes.append(parent2.modes[idx])
        else:
            c1_modes.append(parent2.modes[idx])
            c2_modes.append(parent1.modes[idx])

    child1 = Solution(sequence=tuple(c1_seq), modes=tuple(c1_modes))  # type: ignore
    child2 = Solution(sequence=tuple(c2_seq), modes=tuple(c2_modes))  # type: ignore
    return child1, child2


def mutate_sequence_swap(solution: Solution, rng: random.Random) -> Solution:
    """Swap mutation for sequence: swaps two distinct positions, preserving job frequencies."""
    seq_len = len(solution.sequence)
    if seq_len < 2:
        return solution

    seq_list = list(solution.sequence)
    i, j = rng.sample(range(seq_len), 2)
    seq_list[i], seq_list[j] = seq_list[j], seq_list[i]
    return Solution(sequence=tuple(seq_list), modes=solution.modes)


def mutate_modes_per_gene(
    solution: Solution,
    instance: Instance,
    p_mut_mode: float,
    rng: random.Random,
) -> Solution:
    """Mutate processing modes per gene with probability p_mut_mode.

    For each gene (operation) in instance.all_operations, with probability p_mut_mode,
    selects uniformly at random an alternative valid mode if more than one mode exists.
    """
    modes_list = list(solution.modes)
    for idx, op in enumerate(instance.all_operations):
        if len(op.modes) > 1 and rng.random() < p_mut_mode:
            current_mode_id = modes_list[idx]
            alt_modes = [m.mode_id for m in op.modes if m.mode_id != current_mode_id]
            if alt_modes:
                modes_list[idx] = rng.choice(alt_modes)

    return Solution(sequence=solution.sequence, modes=tuple(modes_list))


class NSGA2:
    """NSGA-II Multi-Objective Optimization Algorithm for MO-JSSP.

    Parameters:
        population_size: Number of candidate solutions in each generation.
        generations: Total number of evolutionary generations.
        crossover_probability: Probability of applying POX crossover to parents.
        mutation_sequence_probability: Probability of applying swap mutation to sequence.
        mutation_mode_per_gene_probability: Probability of mutating mode per gene.
            Defaults to 1 / N where N is instance.total_operations.
        seed: Optional integer seed for deterministic reproducibility.
    """

    def __init__(
        self,
        population_size: int = 40,
        generations: int = 50,
        crossover_probability: float = 0.9,
        mutation_sequence_probability: float = 0.2,
        mutation_mode_per_gene_probability: Optional[float] = None,
        seed: Optional[int] = None,
    ) -> None:
        if population_size < 4:
            raise ValueError(f"population_size must be >= 4, got {population_size}")
        if generations < 1:
            raise ValueError(f"generations must be >= 1, got {generations}")
        if not (0.0 <= crossover_probability <= 1.0):
            raise ValueError("crossover_probability must be between 0.0 and 1.0")
        if not (0.0 <= mutation_sequence_probability <= 1.0):
            raise ValueError("mutation_sequence_probability must be between 0.0 and 1.0")
        if mutation_mode_per_gene_probability is not None and not (
            0.0 <= mutation_mode_per_gene_probability <= 1.0
        ):
            raise ValueError("mutation_mode_per_gene_probability must be between 0.0 and 1.0")

        self.population_size = population_size
        self.generations = generations
        self.crossover_probability = crossover_probability
        self.mutation_sequence_probability = mutation_sequence_probability
        self.mutation_mode_per_gene_probability = mutation_mode_per_gene_probability
        self.seed = seed

        self.decoder = Decoder()
        self.evaluator = Evaluator()

    def _create_individual(self, instance: Instance, solution: Solution) -> Individual:
        schedule = self.decoder.decode(instance, solution)
        objectives = self.evaluator.evaluate(instance, schedule)
        return Individual(solution=solution, schedule=schedule, objectives=objectives)

    def run(self, instance: Instance) -> NSGA2Result:
        """Execute the NSGA-II algorithm on the given instance.

        Args:
            instance: MO-JSSP instance with jobs, operations, and modes.

        Returns:
            NSGA2Result with non-dominated set and final population.
        """
        rng = random.Random(self.seed)
        p_mut_mode = (
            self.mutation_mode_per_gene_probability
            if self.mutation_mode_per_gene_probability is not None
            else (1.0 / instance.total_operations if instance.total_operations > 0 else 0.1)
        )

        # 1. Initialize population P_0
        population: List[Individual] = []
        for _ in range(self.population_size):
            sol = Solution.random(instance, rng=rng)
            ind = self._create_individual(instance, sol)
            population.append(ind)

        # Non-dominated sort and crowding distance for P_0
        fronts = fast_non_dominated_sort(population)
        for front in fronts:
            calculate_crowding_distance(front)

        # 2. Generational evolution loop
        for _ in range(self.generations):
            # Create offspring Q_t of size population_size
            offspring: List[Individual] = []
            while len(offspring) < self.population_size:
                # Binary tournament selection for 2 parents
                p1 = binary_tournament(rng.choice(population), rng.choice(population), rng)
                p2 = binary_tournament(rng.choice(population), rng.choice(population), rng)

                # Crossover
                if rng.random() < self.crossover_probability:
                    child1_sol, child2_sol = crossover_pox(p1.solution, p2.solution, instance, rng)
                else:
                    child1_sol, child2_sol = p1.solution, p2.solution

                # Mutation
                for child_sol in (child1_sol, child2_sol):
                    if rng.random() < self.mutation_sequence_probability:
                        child_sol = mutate_sequence_swap(child_sol, rng)
                    child_sol = mutate_modes_per_gene(child_sol, instance, p_mut_mode, rng)

                    ind = self._create_individual(instance, child_sol)
                    offspring.append(ind)
                    if len(offspring) >= self.population_size:
                        break

            # 3. Combine R_t = P_t U Q_t (size 2 * population_size)
            combined = population + offspring
            fronts = fast_non_dominated_sort(combined)

            # 4. Form P_{t+1} via elitism
            new_population: List[Individual] = []
            for front in fronts:
                calculate_crowding_distance(front)
                if len(new_population) + len(front) <= self.population_size:
                    new_population.extend(front)
                else:
                    # Sort remaining front by crowding distance descending
                    needed = self.population_size - len(new_population)
                    front.sort(key=lambda ind: ind.crowding_distance, reverse=True)
                    new_population.extend(front[:needed])
                    break

            population = new_population

        # Extract final non-dominated set (Front 1)
        final_fronts = fast_non_dominated_sort(population)
        f1 = final_fronts[0] if final_fronts else []

        return NSGA2Result(
            non_dominated_solutions=tuple(ind.solution for ind in f1),
            non_dominated_schedules=tuple(ind.schedule for ind in f1),
            non_dominated_objectives=tuple(ind.objectives for ind in f1),
            population=tuple(ind.solution for ind in population),
            population_objectives=tuple(ind.objectives for ind in population),
        )


def nsga2(
    instance: Instance,
    population_size: int = 40,
    generations: int = 50,
    crossover_probability: float = 0.9,
    mutation_sequence_probability: float = 0.2,
    mutation_mode_per_gene_probability: Optional[float] = None,
    seed: Optional[int] = None,
) -> NSGA2Result:
    """Convenience function running NSGA-II on an instance."""
    algo = NSGA2(
        population_size=population_size,
        generations=generations,
        crossover_probability=crossover_probability,
        mutation_sequence_probability=mutation_sequence_probability,
        mutation_mode_per_gene_probability=mutation_mode_per_gene_probability,
        seed=seed,
    )
    return algo.run(instance)
