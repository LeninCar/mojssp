"""MOEA/D (Multi-Objective Evolutionary Algorithm based on Decomposition) for MO-JSSP.

Decomposition-based multi-objective optimization algorithm mapping the 3-objective
MO-JSSP (Cmax, Total Tardiness, Energy Consumption) onto scalar subproblems via
uniform weight vectors and the augmented/normalized Tchebycheff aggregation function.
"""

from dataclasses import dataclass
import math
import random
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from .algorithm_contract import AlgorithmBlockResult, PortfolioArm
from .decoder import Decoder
from .cooperation import GuidedMatingArm
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


def generate_simplex_lattice_weights(
    divisions: int, num_objectives: int = 3, zero_replacement_eps: float = 1e-6
) -> List[Tuple[float, ...]]:
    """Generate canonical Das and Dennis simplex-lattice weight vectors.

    Generates all integer combinations (h_1, ..., h_m) such that sum(h_i) = divisions,
    with lambda_i = h_i / divisions. For m=3 objectives, yields exactly
    (divisions + 1) * (divisions + 2) / 2 uniform weight vectors on the unit simplex.

    Args:
        divisions: Number of divisions H along each objective axis (H >= 1).
        num_objectives: Dimension of objective space (m = 3 for MO-JSSP).
        zero_replacement_eps: Positive epsilon replacing 0-weight components to
            prevent weakly Pareto-optimal degeneration in Tchebycheff aggregation.

    Returns:
        List of strictly positive normalized weight vectors summing to 1.0.
    """
    if divisions < 1:
        raise ValueError(f"divisions must be at least 1, got {divisions}")
    if num_objectives != 3:
        raise ValueError(f"Currently supporting 3 objectives, got {num_objectives}")

    weights: List[Tuple[float, ...]] = []
    h = divisions
    for h1 in range(h + 1):
        for h2 in range(h + 1 - h1):
            h3 = h - h1 - h2
            w = [h1 / h, h2 / h, h3 / h]
            if zero_replacement_eps > 0.0:
                w = [max(v, zero_replacement_eps) for v in w]
                tot = sum(w)
                w = [v / tot for v in w]
            weights.append(tuple(w))

    return weights


def generate_uniform_weights(
    num_subproblems: int,
    num_objectives: int = 3,
    divisions: Optional[int] = None,
    zero_replacement_eps: float = 1e-6,
) -> List[Tuple[float, ...]]:
    """Generate uniformly distributed weight vectors for any requested population size.

    If divisions is explicitly provided, generates the exact Das-Dennis simplex lattice.
    If divisions is None and num_subproblems matches a simplex lattice size
    (H + 1)*(H + 2)/2, the exact lattice is returned. Otherwise, generates a fine
    lattice and selects num_subproblems points using deterministic Max-Min Euclidean
    Distance (farthest-first traversal) starting from the extreme corners.

    Args:
        num_subproblems: Requested number of weight vectors N (> 0).
        num_objectives: Dimension of objective space (m = 3).
        divisions: Optional explicit division parameter H.
        zero_replacement_eps: Epsilon replacing zero components to ensure strictly
            positive weights.

    Returns:
        List of N weight vectors on the unit simplex.
    """
    if num_subproblems <= 0:
        raise ValueError(f"num_subproblems must be positive, got {num_subproblems}")

    if divisions is not None:
        return generate_simplex_lattice_weights(
            divisions=divisions,
            num_objectives=num_objectives,
            zero_replacement_eps=zero_replacement_eps,
        )

    # Check if num_subproblems matches an exact Das-Dennis lattice size for m=3
    # N = (H + 1)(H + 2) / 2  <=>  H^2 + 3H + 2 - 2N = 0
    # Discriminant: 9 - 4(2 - 2N) = 1 + 8N
    disc = 1 + 8 * num_subproblems
    sqrt_disc = int(math.isqrt(disc))
    if sqrt_disc * sqrt_disc == disc and (sqrt_disc - 3) % 2 == 0:
        h_exact = (sqrt_disc - 3) // 2
        if h_exact >= 1:
            return generate_simplex_lattice_weights(
                divisions=h_exact,
                num_objectives=num_objectives,
                zero_replacement_eps=zero_replacement_eps,
            )

    # General case: Farthest Point Sampling on a fine simplex lattice
    fine_h = max(16, int(math.ceil(math.sqrt(2 * num_subproblems) * 2)))
    fine_lattice: List[Tuple[float, ...]] = []
    for h1 in range(fine_h + 1):
        for h2 in range(fine_h + 1 - h1):
            h3 = fine_h - h1 - h2
            fine_lattice.append((h1 / fine_h, h2 / fine_h, h3 / fine_h))

    # Extreme corners of the 3-simplex
    corners = [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)]
    selected: List[Tuple[float, ...]] = []
    for c in corners:
        if len(selected) < num_subproblems:
            selected.append(c)

    remaining = [p for p in fine_lattice if p not in selected]

    while len(selected) < num_subproblems and remaining:
        best_cand: Optional[Tuple[float, ...]] = None
        best_min_dist = -1.0
        for cand in remaining:
            min_d = min(
                math.dist(cand, s) for s in selected
            )
            if min_d > best_min_dist:
                best_min_dist = min_d
                best_cand = cand
        if best_cand is None:
            break
        selected.append(best_cand)
        remaining.remove(best_cand)

    # Apply epsilon zero-replacement and re-normalization
    final_weights: List[Tuple[float, ...]] = []
    for w in selected:
        w_adj = [max(v, zero_replacement_eps) for v in w]
        tot = sum(w_adj)
        final_weights.append(tuple(v / tot for v in w_adj))

    return final_weights


def compute_neighborhoods(
    weight_vectors: Sequence[Tuple[float, ...]], neighborhood_size: int
) -> List[Tuple[int, ...]]:
    """Compute topological Euclidean neighborhoods B(i) for each subproblem weight.

    Args:
        weight_vectors: Collection of N weight vectors.
        neighborhood_size: Number of neighbors T per subproblem (1 <= T <= N).

    Returns:
        List where index i contains the tuple of indices of the T closest weight
        vectors, ordered by Euclidean distance ascending (with i at index 0).
    """
    n = len(weight_vectors)
    t = max(1, min(neighborhood_size, n))
    neighborhoods: List[Tuple[int, ...]] = []

    for i, wi in enumerate(weight_vectors):
        distances = [
            (math.dist(wi, wj), j) for j, wj in enumerate(weight_vectors)
        ]
        distances.sort(key=lambda pair: pair[0])
        neighbors = tuple(pair[1] for pair in distances[:t])
        neighborhoods.append(neighbors)

    return neighborhoods


def tchebycheff_scalarizing(
    normalized_objectives: Tuple[float, float, float],
    weight_vector: Tuple[float, float, float],
    ideal_point: Sequence[float],
) -> float:
    """Compute the Tchebycheff scalarizing function value for a subproblem.

    g^te(f~ | lambda, z*) = max_{k=0..2} lambda_k * |f~_k - z*_k|

    Args:
        normalized_objectives: Objective vector f~ in normalized space [0, 1]^3.
        weight_vector: Subproblem weight vector lambda on unit simplex.
        ideal_point: Dynamic ideal reference point z* tracking best observed values.

    Returns:
        Scalar aggregation value (lower is better in minimization).
    """
    return max(
        weight_vector[k] * abs(normalized_objectives[k] - ideal_point[k])
        for k in range(3)
    )


@dataclass
class Subproblem:
    """A scalar subproblem in MOEA/D pairing a weight vector with its incumbent solution."""

    subproblem_id: int
    weight: Tuple[float, float, float]
    neighborhood: Tuple[int, ...]
    solution: Solution
    schedule: Schedule
    objectives: ObjectiveValues
    normalized_objectives: Tuple[float, float, float]


@dataclass(frozen=True)
class MOEADResult:
    """Result container of a MOEA/D optimization run."""

    non_dominated_solutions: Tuple[Solution, ...]
    non_dominated_schedules: Tuple[Schedule, ...]
    non_dominated_objectives: Tuple[ObjectiveValues, ...]
    population: Tuple[Solution, ...]
    population_objectives: Tuple[ObjectiveValues, ...]
    total_evaluations: int
    archive: ParetoArchive
    seed: Optional[int] = None


class MOEAD:
    """MOEA/D (Multi-Objective Evolutionary Algorithm based on Decomposition) for MO-JSSP.

    Decomposes the 3-objective problem into N scalar subproblems using Tchebycheff
    aggregation on normalized objectives, maintaining an external Pareto archive
    throughout execution.
    """

    def __init__(
        self,
        population_size: int = 30,
        neighborhood_size: int = 6,
        selection_neighborhood_prob: float = 0.9,
        max_replacements: int = 2,
        crossover_probability: float = 1.0,
        mutation_sequence_probability: float = 0.2,
        mutation_mode_per_gene_probability: Optional[float] = None,
        divisions: Optional[int] = None,
        seed: Optional[int] = None,
        max_evaluations: Optional[int] = 1000,
    ) -> None:
        if population_size <= 0:
            raise ValueError(f"population_size must be positive, got {population_size}")
        if neighborhood_size <= 0:
            raise ValueError(f"neighborhood_size must be positive, got {neighborhood_size}")
        if not (0.0 <= selection_neighborhood_prob <= 1.0):
            raise ValueError(
                f"selection_neighborhood_prob must be in [0, 1], got {selection_neighborhood_prob}"
            )
        if max_replacements <= 0:
            raise ValueError(f"max_replacements must be positive, got {max_replacements}")
        if max_evaluations is not None and max_evaluations <= 0:
            raise ValueError(f"max_evaluations must be positive, got {max_evaluations}")

        self.population_size = population_size
        self.neighborhood_size = min(neighborhood_size, population_size)
        self.selection_neighborhood_prob = selection_neighborhood_prob
        self.max_replacements = max_replacements
        self.crossover_probability = crossover_probability
        self.mutation_sequence_probability = mutation_sequence_probability
        self.mutation_mode_per_gene_probability = mutation_mode_per_gene_probability
        self.divisions = divisions
        self.seed = seed
        self.max_evaluations = max_evaluations

        self.decoder = Decoder()
        self.evaluator = Evaluator()

    def run(self, instance: Instance) -> MOEADResult:
        """Execute MOEA/D on the given instance up to max_evaluations.

        Args:
            instance: MO-JSSP instance with jobs, operations, and modes.

        Returns:
            MOEADResult containing non-dominated archive, final subproblem population,
            and evaluation metadata.
        """
        budget = self.max_evaluations if self.max_evaluations is not None else 1000
        arm = MOEADArm(
            instance=instance,
            population_size=self.population_size,
            neighborhood_size=self.neighborhood_size,
            selection_neighborhood_prob=self.selection_neighborhood_prob,
            max_replacements=self.max_replacements,
            crossover_probability=self.crossover_probability,
            mutation_sequence_probability=self.mutation_sequence_probability,
            mutation_mode_per_gene_probability=self.mutation_mode_per_gene_probability,
            divisions=self.divisions,
            seed=self.seed,
            max_evaluations=budget,
        )

        arm.run(budget)

        archive = arm.current_archive
        subs = arm.subproblems

        return MOEADResult(
            non_dominated_solutions=tuple(e.solution for e in archive.entries),
            non_dominated_schedules=tuple(e.schedule for e in archive.entries),
            non_dominated_objectives=tuple(e.objectives for e in archive.entries),
            population=tuple(s.solution for s in subs),
            population_objectives=tuple(s.objectives for s in subs),
            total_evaluations=arm.total_evaluations,
            archive=archive,
            seed=self.seed,
        )


class MOEADArm(GuidedMatingArm):
    """Stateful portfolio arm implementing MOEA/D under the common PortfolioArm protocol.

    Preserves internal algorithmic state (subproblems, ideal reference point z*,
    current subproblem index, external archive, RNG state) between calls to run(budget)
    to guarantee exact bit-for-bit trajectory continuity and zero budget overshoot.
    """

    def __init__(
        self,
        instance: Instance,
        population_size: int = 30,
        neighborhood_size: int = 6,
        selection_neighborhood_prob: float = 0.9,
        max_replacements: int = 2,
        crossover_probability: float = 1.0,
        mutation_sequence_probability: float = 0.2,
        mutation_mode_per_gene_probability: Optional[float] = None,
        divisions: Optional[int] = None,
        seed: Optional[int] = None,
        max_evaluations: Optional[int] = None,
    ) -> None:
        if population_size <= 0:
            raise ValueError(f"population_size must be positive, got {population_size}")
        if neighborhood_size <= 0:
            raise ValueError(f"neighborhood_size must be positive, got {neighborhood_size}")
        if max_replacements <= 0:
            raise ValueError(f"max_replacements must be positive, got {max_replacements}")
        if max_evaluations is not None and max_evaluations <= 0:
            raise ValueError(f"max_evaluations must be positive, got {max_evaluations}")

        self._instance = instance
        self._population_size = population_size
        self._neighborhood_size = min(neighborhood_size, population_size)
        self._selection_neighborhood_prob = selection_neighborhood_prob
        self._max_replacements = max_replacements
        self._crossover_probability = crossover_probability
        self._mutation_sequence_probability = mutation_sequence_probability
        self._mutation_mode_per_gene_probability = mutation_mode_per_gene_probability
        self._divisions = divisions
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

        # Generate weights and neighborhoods
        self._weights: List[Tuple[float, float, float]] = [
            (w[0], w[1], w[2])
            for w in generate_uniform_weights(
                num_subproblems=self._population_size,
                num_objectives=3,
                divisions=self._divisions,
            )
        ]
        # In case divisions produced a different lattice size, adjust population_size
        self._population_size = len(self._weights)
        self._neighborhood_size = min(self._neighborhood_size, self._population_size)
        self._neighborhoods = compute_neighborhoods(self._weights, self._neighborhood_size)

        # Persistent execution state
        self._subproblems: List[Subproblem] = []
        self._ideal_point: List[float] = [1.0, 1.0, 1.0]
        self._archive = ParetoArchive()
        self._current_subproblem_idx = 0
        self._generations_completed = 0
        self._total_evaluations = 0
        self._completed = False

    @property
    def arm_name(self) -> str:
        return "MOEA/D"

    @property
    def total_evaluations(self) -> int:
        return self._total_evaluations

    @property
    def is_completed(self) -> bool:
        return self._completed

    @property
    def current_subproblem_idx(self) -> int:
        return self._current_subproblem_idx

    @property
    def generations_completed(self) -> int:
        return self._generations_completed

    @property
    def ideal_point(self) -> Tuple[float, float, float]:
        return (self._ideal_point[0], self._ideal_point[1], self._ideal_point[2])

    @property
    def subproblems(self) -> Tuple[Subproblem, ...]:
        return tuple(self._subproblems)

    @property
    def weight_vectors(self) -> Tuple[Tuple[float, float, float], ...]:
        return tuple(self._weights)

    @property
    def current_archive(self) -> ParetoArchive:
        return self._get_archive_snapshot()

    def _get_archive_snapshot(self) -> ParetoArchive:
        return ParetoArchive(initial_entries=self._archive.entries)

    def reset(self) -> None:
        """Reset the arm to its initial unexecuted state with its initial seed."""
        self._archive_guidance = None
        self._rng = random.Random(self._seed)
        self._subproblems.clear()
        self._ideal_point = [1.0, 1.0, 1.0]
        self._archive = ParetoArchive()
        self._current_subproblem_idx = 0
        self._generations_completed = 0
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

        # Helper to decode, evaluate, normalize, update ideal point, and add to archive
        def _evaluate_candidate(sol: Solution) -> Tuple[Schedule, ObjectiveValues, Tuple[float, float, float]]:
            nonlocal evals_used
            sched = self._decoder.decode(self._instance, sol)
            objs = self._evaluator.evaluate(self._instance, sched)
            norm_objs = self._normalizer.normalize_tuple(objs)

            evals_used += 1
            self._total_evaluations += 1

            # Update ideal reference point z*
            for k in range(3):
                if norm_objs[k] < self._ideal_point[k]:
                    self._ideal_point[k] = norm_objs[k]

            # Update external non-dominated archive
            self._archive.add(sol, sched, objs)

            return sched, objs, norm_objs

        # 1. Initialization phase: evaluate initial solutions for each subproblem
        while len(self._subproblems) < self._population_size and evals_used < effective_budget:
            idx = len(self._subproblems)
            sol = Solution.random(self._instance, rng=self._rng)
            sched, objs, norm_objs = _evaluate_candidate(sol)

            sub = Subproblem(
                subproblem_id=idx,
                weight=self._weights[idx],
                neighborhood=self._neighborhoods[idx],
                solution=sol,
                schedule=sched,
                objectives=objs,
                normalized_objectives=norm_objs,
            )
            self._subproblems.append(sub)

        # 2. Generational evolution phase
        if len(self._subproblems) == self._population_size:
            while evals_used < effective_budget:
                if (
                    self._max_evaluations is not None
                    and self._total_evaluations >= self._max_evaluations
                ):
                    self._completed = True
                    break

                i = self._current_subproblem_idx

                # Determine mating pool (neighborhood with prob delta, else whole population)
                if self._rng.random() < self._selection_neighborhood_prob:
                    mating_pool = list(self._subproblems[i].neighborhood)
                else:
                    mating_pool = list(range(self._population_size))

                # Select two distinct parents from the pool
                if len(mating_pool) >= 2:
                    p1_idx, p2_idx = self._rng.sample(mating_pool, 2)
                else:
                    p1_idx = mating_pool[0]
                    p2_idx = (p1_idx + 1) % self._population_size

                parent1 = self._subproblems[p1_idx].solution
                parent2 = self._subproblems[p2_idx].solution

                # Crossover
                if self._rng.random() < self._crossover_probability:
                    c1, c2 = crossover_pox(parent1, self._guided_parent(parent2), self._instance, self._rng)
                    child_sol = c1 if self._rng.random() < 0.5 else c2
                else:
                    child_sol = parent1

                # Mutation
                if self._rng.random() < self._mutation_sequence_probability:
                    child_sol = mutate_sequence_swap(child_sol, self._rng)
                child_sol = mutate_modes_per_gene(
                    child_sol, self._instance, self._p_mut_mode, self._rng
                )

                # Decode & evaluate (consumes exactly 1 FE)
                child_sched, child_objs, child_norm = _evaluate_candidate(child_sol)

                # Replacement of neighbors
                replacement_pool = list(mating_pool)
                self._rng.shuffle(replacement_pool)
                replaced_count = 0

                for j in replacement_pool:
                    child_tch = tchebycheff_scalarizing(
                        child_norm, self._weights[j], self._ideal_point
                    )
                    current_tch = tchebycheff_scalarizing(
                        self._subproblems[j].normalized_objectives,
                        self._weights[j],
                        self._ideal_point,
                    )

                    if child_tch <= current_tch:
                        self._subproblems[j].solution = child_sol
                        self._subproblems[j].schedule = child_sched
                        self._subproblems[j].objectives = child_objs
                        self._subproblems[j].normalized_objectives = child_norm
                        replaced_count += 1
                        if replaced_count >= self._max_replacements:
                            break

                # Advance subproblem index
                self._current_subproblem_idx += 1
                if self._current_subproblem_idx >= self._population_size:
                    self._current_subproblem_idx = 0
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


def moead(
    instance: Instance,
    population_size: int = 30,
    neighborhood_size: int = 6,
    selection_neighborhood_prob: float = 0.9,
    max_replacements: int = 2,
    crossover_probability: float = 1.0,
    mutation_sequence_probability: float = 0.2,
    mutation_mode_per_gene_probability: Optional[float] = None,
    divisions: Optional[int] = None,
    seed: Optional[int] = None,
    max_evaluations: Optional[int] = 1000,
) -> MOEADResult:
    """Convenience function running MOEA/D on an instance."""
    algo = MOEAD(
        population_size=population_size,
        neighborhood_size=neighborhood_size,
        selection_neighborhood_prob=selection_neighborhood_prob,
        max_replacements=max_replacements,
        crossover_probability=crossover_probability,
        mutation_sequence_probability=mutation_sequence_probability,
        mutation_mode_per_gene_probability=mutation_mode_per_gene_probability,
        divisions=divisions,
        seed=seed,
        max_evaluations=max_evaluations,
    )
    return algo.run(instance)
