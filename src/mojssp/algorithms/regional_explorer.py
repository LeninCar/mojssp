"""Stateful global-archive explorer with objective-region-directed operators."""

import math
import random

from mojssp.algorithms.algorithm_contract import AlgorithmBlockResult
from mojssp.model.critical_path import get_critical_sequence_indices
from mojssp.model.decoder import Decoder
from mojssp.model.evaluator import Evaluator
from mojssp.metrics.pareto_archive import ArchiveEntry, ParetoArchive
from mojssp.portfolio.provenance import compute_genotype_id
from mojssp.model.solution import Solution


REFERENCES = [
    (1.0, 0.0, 0.0),
    (0.0, 1.0, 0.0),
    (0.0, 0.0, 1.0),
    (0.5, 0.5, 0.0),
    (0.5, 0.0, 0.5),
    (0.0, 0.5, 0.5),
    (1 / 3, 1 / 3, 1 / 3),
]


def region_geometry(points):
    """Associate unique objective vectors with normalized achievement directions.

    Achievement is (observed nadir - f)/(nadir - ideal), so an axis denotes
    excellence in that objective. Constant objectives are removed from reference
    vectors and duplicate projected directions are merged.
    """
    points = sorted(set(tuple(point) for point in points))
    if not points:
        raise ValueError("Regions require a nonempty archive")
    ideal = [min(p[i] for p in points) for i in range(3)]
    nadir = [max(p[i] for p in points) for i in range(3)]
    active = [nadir[i] - ideal[i] > 1e-12 for i in range(3)]
    weights = []
    if any(active):
        for reference in REFERENCES:
            projected = [reference[i] if active[i] else 0.0 for i in range(3)]
            mass = sum(projected)
            if mass:
                vector = tuple(round(v / mass, 12) for v in projected)
                if vector not in weights:
                    weights.append(vector)
    else:
        weights = [(1 / 3, 1 / 3, 1 / 3)]
    geometry = dict(ideal=ideal, nadir=nadir, active_objectives=active, weights=weights)
    densities = [0] * len(weights)
    for point in points:
        index = min(range(len(weights)), key=lambda i: region_distance(point, weights[i], geometry))
        densities[index] += 1
    geometry.update(densities=densities, unique_points=[list(p) for p in points])
    return geometry


def region_distance(point, weight, geometry):
    direction = [
        (geometry["nadir"][i] - point[i]) / (geometry["nadir"][i] - geometry["ideal"][i])
        if geometry["active_objectives"][i]
        else 0.0
        for i in range(3)
    ]
    norm = math.sqrt(sum(v * v for v in direction))
    weight_norm = math.sqrt(sum(v * v for v in weight))
    return 1 - sum(a * b for a, b in zip(direction, weight)) / (norm * weight_norm) if norm else 1.0


def regional_score(point, weight, geometry):
    return max(
        weight[i]
        * max(0.0, point[i] - geometry["ideal"][i])
        / max(1e-12, geometry["nadir"][i] - geometry["ideal"][i])
        for i in range(3)
    )


class RegionalExplorerArm:
    """Mutate evaluated global parents; every candidate consumes one real FE.

    Both controls use the same region geometry, parent selection and operators.
    Only choosing a random region versus a least populated region differs.
    Parents are not credited as newly evaluated explorer solutions.
    """

    def __init__(self, instance, normalizer, policy="sparse", seed=42, max_evaluations=600, parent_count=5):
        if policy not in ("random", "sparse") or parent_count < 1 or max_evaluations < 1:
            raise ValueError("Invalid explorer configuration")
        self._instance, self.normalizer, self.policy = instance, normalizer, policy
        self._seed, self._limit, self.parent_count = seed, max_evaluations, parent_count
        self._decoder, self._evaluator = Decoder(), Evaluator()
        self._operations = instance.all_operations
        self.reset()

    @property
    def arm_name(self):
        return "RegionExplorer"

    @property
    def total_evaluations(self):
        return self._total_evaluations

    @property
    def is_completed(self):
        return self._total_evaluations >= self._limit

    @property
    def current_archive(self):
        return ParetoArchive(self._archive.entries)

    def reset(self):
        self._rng = random.Random(self._seed)
        self._archive = ParetoArchive()
        self._total_evaluations = 0
        self.trace = []
        self._pool = []
        self._geometry, self._weight = None, None

    def prepare(self, global_archive):
        entries = list(global_archive.entries)
        points = [self.normalizer.normalize_tuple(entry.objectives) for entry in entries]
        geometry = region_geometry(points)
        choices = list(range(len(geometry["weights"])))
        if self.policy == "sparse":
            smallest = min(geometry["densities"])
            choices = [i for i in choices if geometry["densities"][i] == smallest]
        selected = self._rng.choice(choices)
        weight = geometry["weights"][selected]
        ranked = sorted(
            entries,
            key=lambda entry: (
                region_distance(self.normalizer.normalize_tuple(entry.objectives), weight, geometry),
                regional_score(self.normalizer.normalize_tuple(entry.objectives), weight, geometry),
                compute_genotype_id(entry.solution),
            ),
        )
        self._pool = ranked[: self.parent_count]
        self._geometry, self._weight = geometry, weight
        row = dict(
            explorer_fe_before=self.total_evaluations,
            policy=self.policy,
            geometry=geometry,
            selected_region=selected,
            selected_weight=list(weight),
            seed_parent_ids=[compute_genotype_id(entry.solution) for entry in self._pool],
            seed_parent_points=[
                list(self.normalizer.normalize_tuple(entry.objectives)) for entry in self._pool
            ],
            operators={},
            evaluations=0,
        )
        self.trace.append(row)
        return row

    def _mode_move(self, parent):
        time_weight = self._weight[0] + self._weight[1]
        energy_weight = self._weight[2]
        improvements, alternatives = [], []
        for index, op in enumerate(self._operations):
            current = op.get_mode(parent.solution.modes[index])

            def proxy(mode):
                return time_weight * mode.duration / max(
                    m.duration for m in op.modes
                ) + energy_weight * mode.energy / max(1, max(m.energy for m in op.modes))

            others = [m for m in op.modes if m.mode_id != current.mode_id]
            if not others:
                continue
            best = min(others, key=lambda m: (proxy(m), m.mode_id))
            alternatives.append((index, best.mode_id))
            improvement = proxy(current) - proxy(best)
            if improvement > 1e-12:
                improvements.append((improvement, index, best.mode_id))
        if improvements:
            improvements.sort(reverse=True)
            _, index, mode_id = self._rng.choice(improvements[: max(1, len(improvements) // 4)])
        elif alternatives:
            index, mode_id = self._rng.choice(alternatives)
        else:
            return parent.solution, "mode_noop"
        modes = list(parent.solution.modes)
        modes[index] = mode_id
        return Solution(parent.solution.sequence, tuple(modes)), "directed_mode"

    def _sequence_move(self, parent):
        sequence = list(parent.solution.sequence)
        if self._weight[1] > self._weight[0]:
            late = {
                job.job_id
                for job in self._instance.jobs
                if parent.schedule.job_completion_times[job.job_id] > job.due_date
            }
            possible = [
                i
                for i, job in enumerate(sequence)
                if job in late and any(sequence[j] != job for j in range(i))
            ]
            if possible:
                i = self._rng.choice(possible)
                j = self._rng.choice([j for j in range(i) if sequence[j] != sequence[i]])
                sequence[i], sequence[j] = sequence[j], sequence[i]
                return Solution(tuple(sequence), parent.solution.modes), "tardy_priority_swap"
        critical = sorted(get_critical_sequence_indices(parent.schedule, parent.solution.sequence))
        possible = critical or list(range(len(sequence)))
        i = self._rng.choice(possible)
        alternatives = [j for j in range(len(sequence)) if sequence[j] != sequence[i]]
        if not alternatives:
            return self._mode_move(parent)
        j = self._rng.choice(alternatives)
        sequence[i], sequence[j] = sequence[j], sequence[i]
        return Solution(tuple(sequence), parent.solution.modes), "critical_swap"

    def run(self, budget):
        if budget <= 0 or self.is_completed:
            return AlgorithmBlockResult(self.current_archive, 0, self.is_completed)
        if not self._pool:
            raise ValueError("Prepare evaluated global parents before running the explorer")
        used = 0
        amount = min(budget, self._limit - self._total_evaluations)
        while used < amount:
            parent = self._rng.choice(self._pool)
            mode_probability = (
                0.8 if self._weight[2] > 0.5 else (0.3 if self._weight[0] + self._weight[1] > 0.75 else 0.5)
            )
            child, operator = (
                self._mode_move(parent)
                if self._rng.random() < mode_probability
                else self._sequence_move(parent)
            )
            child.validate_with_instance(self._instance)
            schedule = self._decoder.decode(self._instance, child)
            objectives = self._evaluator.evaluate(self._instance, schedule)
            entry = ArchiveEntry(child, schedule, objectives)
            self._archive.add_entry(entry)
            used += 1
            self._total_evaluations += 1
            self.trace[-1]["operators"][operator] = self.trace[-1]["operators"].get(operator, 0) + 1
            self.trace[-1]["evaluations"] += 1
            pool = {compute_genotype_id(e.solution): e for e in self._pool}
            pool[compute_genotype_id(child)] = entry
            self._pool = sorted(
                pool.values(),
                key=lambda e: (
                    regional_score(
                        self.normalizer.normalize_tuple(e.objectives), self._weight, self._geometry
                    ),
                    compute_genotype_id(e.solution),
                ),
            )[: self.parent_count]
        return AlgorithmBlockResult(self.current_archive, used, self.is_completed)
