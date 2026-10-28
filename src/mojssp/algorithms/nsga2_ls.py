"""NSGA-II + Local Search (LS) memetic algorithm for MO-JSSP."""

from dataclasses import dataclass
import random
from typing import Dict, List, Optional, Sequence, Tuple

from mojssp.model.decoder import Decoder
from mojssp.model.evaluator import Evaluator, ObjectiveValues
from mojssp.model.instance import Instance
from mojssp.algorithms.local_search import LocalSearch
from mojssp.algorithms.nsga2 import (
    Individual,
    binary_tournament,
    calculate_crowding_distance,
    crossover_pox,
    fast_non_dominated_sort,
    mutate_modes_per_gene,
    mutate_sequence_swap,
)
from mojssp.model.schedule import Schedule
from mojssp.model.solution import Solution


@dataclass(frozen=True)
class NSGA2LSResult:
    """Result of an NSGA-II + Local Search optimization run.

    Attributes:
        non_dominated_solutions: Pareto-optimal solutions found in final front F1.
        non_dominated_schedules: Corresponding schedules.
        non_dominated_objectives: Corresponding objective values (Cmax, T, E).
        population: Entire final population of solutions.
        population_objectives: Corresponding objectives of the final population.
        total_evaluations: Total number of calls to Evaluator.evaluate().
        ls_evaluations: Number of evaluations expended strictly within Local Search.
    """

    non_dominated_solutions: Tuple[Solution, ...]
    non_dominated_schedules: Tuple[Schedule, ...]
    non_dominated_objectives: Tuple[ObjectiveValues, ...]
    population: Tuple[Solution, ...]
    population_objectives: Tuple[ObjectiveValues, ...]
    total_evaluations: int
    ls_evaluations: int


class NSGA2LS:
    """Hybrid NSGA-II with Cmax-focused Local Search for MO-JSSP."""

    def __init__(
        self,
        population_size: int = 40,
        generations: int = 50,
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
        if generations < 1:
            raise ValueError(f"generations must be at least 1, got {generations}")
        if not (0.0 <= crossover_probability <= 1.0):
            raise ValueError(f"crossover_probability must be in [0, 1], got {crossover_probability}")
        if not (0.0 <= mutation_sequence_probability <= 1.0):
            raise ValueError(f"mutation_sequence_probability must be in [0, 1], got {mutation_sequence_probability}")
        if not (0.0 <= ls_non_f1_ratio <= 1.0):
            raise ValueError(f"ls_non_f1_ratio must be in [0, 1], got {ls_non_f1_ratio}")

        self.population_size = population_size
        self.generations = generations
        self.crossover_probability = crossover_probability
        self.mutation_sequence_probability = mutation_sequence_probability
        self.mutation_mode_per_gene_probability = mutation_mode_per_gene_probability
        self.ls_non_f1_ratio = ls_non_f1_ratio
        self.seed = seed

        self.local_search = LocalSearch(
            max_iterations=max_ls_iterations,
            max_no_improvement=max_ls_no_improvement,
            max_neighbors=max_ls_neighbors,
            max_archive_size=max_ls_archive_size,
        )
        self.decoder = Decoder()
        self.evaluator = Evaluator()

    def run(self, instance: Instance) -> NSGA2LSResult:
        """Execute NSGA-II + Local Search on the given instance.

        Args:
            instance: MO-JSSP instance.

        Returns:
            NSGA2LSResult with non-dominated front, final population, and evaluation metrics.
        """
        rng = random.Random(self.seed)
        p_mut_mode = (
            self.mutation_mode_per_gene_probability
            if self.mutation_mode_per_gene_probability is not None
            else (1.0 / instance.total_operations if instance.total_operations > 0 else 0.1)
        )

        total_eval_counter = [0]
        ls_eval_counter = [0]

        def create_ind(sol: Solution) -> Individual:
            sched = self.decoder.decode(instance, sol)
            objs = self.evaluator.evaluate(instance, sched)
            total_eval_counter[0] += 1
            return Individual(solution=sol, schedule=sched, objectives=objs)

        # 1. Initialize population P_0
        population: List[Individual] = []
        for _ in range(self.population_size):
            sol = Solution.random(instance, rng=rng)
            population.append(create_ind(sol))

        fronts = fast_non_dominated_sort(population)
        for front in fronts:
            calculate_crowding_distance(front)

        # 2. Generational evolution loop
        for _ in range(self.generations):
            # Create offspring Q_t of size population_size
            offspring: List[Individual] = []
            while len(offspring) < self.population_size:
                p1 = binary_tournament(rng.choice(population), rng.choice(population), rng)
                p2 = binary_tournament(rng.choice(population), rng.choice(population), rng)

                if rng.random() < self.crossover_probability:
                    child1_sol, child2_sol = crossover_pox(p1.solution, p2.solution, instance, rng)
                else:
                    child1_sol, child2_sol = p1.solution, p2.solution

                for child_sol in (child1_sol, child2_sol):
                    if rng.random() < self.mutation_sequence_probability:
                        child_sol = mutate_sequence_swap(child_sol, rng)
                    child_sol = mutate_modes_per_gene(child_sol, instance, p_mut_mode, rng)

                    offspring.append(create_ind(child_sol))
                    if len(offspring) >= self.population_size:
                        break

            # Combine parents and offspring: R_t = P_t U Q_t
            r_t = population + offspring

            # Partition R_t into Pareto fronts
            fronts = fast_non_dominated_sort(r_t)

            # Identify candidates for Local Search:
            # - 100% of F1
            # - 25% of F2+ (ls_non_f1_ratio)
            f1 = fronts[0] if fronts else []
            f2_plus = [ind for front in fronts[1:] for ind in front]

            num_non_f1_candidates = int(round(len(f2_plus) * self.ls_non_f1_ratio))
            if num_non_f1_candidates > len(f2_plus):
                num_non_f1_candidates = len(f2_plus)

            non_f1_candidates = (
                rng.sample(f2_plus, num_non_f1_candidates)
                if num_non_f1_candidates > 0
                else []
            )

            candidates_for_ls = list(f1) + non_f1_candidates

            # Execute Local Search on each candidate
            refined_individuals: List[Individual] = []
            for candidate in candidates_for_ls:
                initial_evals = total_eval_counter[0]
                ls_res = self.local_search.search(
                    instance=instance,
                    solution=candidate.solution,
                    schedule=candidate.schedule,
                    objectives=candidate.objectives,
                    rng=rng,
                    decoder=self.decoder,
                    evaluator=self.evaluator,
                    eval_counter=total_eval_counter,
                )
                ls_eval_count = total_eval_counter[0] - initial_evals
                ls_eval_counter[0] += ls_eval_count

                # Collect all non-dominated refined solutions from local archive
                for entry in ls_res.local_archive.entries:
                    refined_individuals.append(
                        Individual(
                            solution=entry.solution,
                            schedule=entry.schedule,
                            objectives=entry.objectives,
                        )
                    )

            # Augmented selection pool: parents, offspring, and all refined solutions
            selection_pool = r_t + refined_individuals

            # Non-dominated sorting and crowding distance on selection pool
            augmented_fronts = fast_non_dominated_sort(selection_pool)

            new_population: List[Individual] = []
            for front in augmented_fronts:
                calculate_crowding_distance(front)
                if len(new_population) + len(front) <= self.population_size:
                    new_population.extend(front)
                else:
                    needed = self.population_size - len(new_population)
                    front.sort(key=lambda ind: ind.crowding_distance, reverse=True)
                    new_population.extend(front[:needed])
                    break

            population = new_population

        final_fronts = fast_non_dominated_sort(population)
        f1_final = final_fronts[0] if final_fronts else []

        return NSGA2LSResult(
            non_dominated_solutions=tuple(ind.solution for ind in f1_final),
            non_dominated_schedules=tuple(ind.schedule for ind in f1_final),
            non_dominated_objectives=tuple(ind.objectives for ind in f1_final),
            population=tuple(ind.solution for ind in population),
            population_objectives=tuple(ind.objectives for ind in population),
            total_evaluations=total_eval_counter[0],
            ls_evaluations=ls_eval_counter[0],
        )


def nsga2_ls(
    instance: Instance,
    population_size: int = 40,
    generations: int = 50,
    crossover_probability: float = 0.9,
    mutation_sequence_probability: float = 0.2,
    mutation_mode_per_gene_probability: Optional[float] = None,
    ls_non_f1_ratio: float = 0.25,
    max_ls_iterations: int = 50,
    max_ls_no_improvement: int = 20,
    max_ls_neighbors: int = 20,
    max_ls_archive_size: int = 10,
    seed: Optional[int] = None,
) -> NSGA2LSResult:
    """Convenience function running NSGA-II + Local Search on an instance."""
    algo = NSGA2LS(
        population_size=population_size,
        generations=generations,
        crossover_probability=crossover_probability,
        mutation_sequence_probability=mutation_sequence_probability,
        mutation_mode_per_gene_probability=mutation_mode_per_gene_probability,
        ls_non_f1_ratio=ls_non_f1_ratio,
        max_ls_iterations=max_ls_iterations,
        max_ls_no_improvement=max_ls_no_improvement,
        max_ls_neighbors=max_ls_neighbors,
        max_ls_archive_size=max_ls_archive_size,
        seed=seed,
    )
    return algo.run(instance)

