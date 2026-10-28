"""The methods compared in the final campaigns, under the names stored in their run files.

Portfolios: early_moead_600 (PS-MB), passive (dynamic rounds without cut), moead_blmr_scaled
and cut_<FE> (PS-MB with another cut). Individuals: explorer_solo (BLMR) and the five native arms.
"""

import random
import time

from mojssp.algorithms.arms import MOPSOArm, NSGA2Arm, NSGA2LSArm
from mojssp.model.decoder import Decoder
from mojssp.model.evaluator import Evaluator
from mojssp.metrics.hypervolume import compute_archive_hypervolume, compute_hypervolume
from mojssp.algorithms.moead import MOEADArm
from mojssp.metrics.normalization import ObjectiveNormalizer, compute_instance_bounds
from mojssp.metrics.pareto_archive import ParetoArchive
from mojssp.algorithms.regional_explorer import RegionalExplorerArm
from mojssp.portfolio.regional_portfolio import run_regional_policy_experiment
from mojssp.metrics.reward import HypervolumeRewardTracker
from mojssp.model.solution import Solution
from mojssp.algorithms.spea2 import SPEA2Arm

from .common import auc

PAIR = ["MOEA/D", "RegionExplorer"]
# Arm class and seed offset of each native individual
NATIVE = {
    "moead": (MOEADArm, 17),
    "nsga2_individual": (NSGA2Arm, 29),
    "spea2_individual": (SPEA2Arm, 43),
    "nsga2_ls_individual": (NSGA2LSArm, 59),
    "mopso_individual": (MOPSOArm, 97),
}
PORTFOLIOS = ["early_moead_600", "passive", "moead_blmr_scaled"]
METHODS = PORTFOLIOS + ["explorer_solo"] + list(NATIVE)


def entry_rows(entries):
    return [
        dict(sequence=list(e.solution.sequence), modes=list(e.solution.modes), objectives=list(e.objectives))
        for e in entries
    ]


def run_psmb(instance, seed, budget=3000, cut=600):
    """MOEA/D and BLMR in dynamic rounds until `cut` FE, then only BLMR."""
    return run_regional_policy_experiment(
        instance,
        seed,
        PAIR,
        "dynamic",
        False,
        budget,
        dynamic_options=dict(exclusive_arm="RegionExplorer", exclusive_after=cut),
    )


def run_blmr(instance, seed, budget=3000, population_size=30, block_size=50, policy="random"):
    """BLMR alone from a random population, in blocks of 50 FE (the campaigns use policy 'random')."""
    if not 0 < population_size < block_size or budget % block_size:
        raise ValueError("Initialization must fit the first full block")
    norm = ObjectiveNormalizer(compute_instance_bounds(instance))
    explorer = RegionalExplorerArm(
        instance,
        norm,
        policy=policy,
        seed=(seed * 10007 + 71) % (2**31 - 1),
        max_evaluations=budget - population_size,
        parent_count=5,
    )
    archive = ParetoArchive()
    rng = random.Random((seed * 10007 + 83) % (2**31 - 1))
    decoder, evaluator = Decoder(), Evaluator()
    started = time.perf_counter()
    for _ in range(population_size):
        solution = Solution.random(instance, rng=rng)
        schedule = decoder.decode(instance, solution)
        archive.add(solution, schedule, evaluator.evaluate(instance, schedule))
    total = population_size
    checkpoints = []
    tracker = HypervolumeRewardTracker(norm)
    while total < budget:
        amount = block_size - population_size if total == population_size else min(block_size, budget - total)
        explorer.prepare(archive)["global_fe_before"] = total  # stored in the region trace
        result = explorer.run(amount)
        assert result.evaluations_used == amount
        total += amount
        archive.update(result.solutions.entries)
        tracker.compute_reward(archive)
        checkpoints.append([total, tracker.current_hv])
    assert total == population_size + explorer.total_evaluations == budget
    front = [list(entry.objectives) for entry in archive.entries]
    assert abs(compute_hypervolume([norm.normalize_tuple(p) for p in front]) - tracker.current_hv) < 1e-12
    return dict(
        budget=budget,
        evaluations_used=total,
        hypervolume=tracker.current_hv,
        pareto_front=front,
        front_entries=entry_rows(archive.entries),
        initialization_fe=population_size,
        evolution_fe=explorer.total_evaluations,
        region_trace=explorer.trace,
        checkpoints=checkpoints,
        auc_hv=auc(checkpoints, budget),
        runtime_seconds=time.perf_counter() - started,
        completed=True,
    )


def run_native(instance, seed, method, budget=3000):
    """One of the native arms alone, population 30, in blocks of 50 FE."""
    cls, offset = NATIVE[method]
    kwargs = dict(population_size=30, seed=(seed * 10007 + offset) % (2**31 - 1), max_evaluations=budget)
    if cls in (NSGA2Arm, NSGA2LSArm):
        kwargs["max_generations"] = None
    if cls is SPEA2Arm:
        kwargs["archive_size"] = 30
    if cls is NSGA2LSArm:
        kwargs.update(max_ls_iterations=10, max_ls_neighbors=10)
    arm = cls(instance, **kwargs)
    norm = ObjectiveNormalizer(compute_instance_bounds(instance))
    checkpoints = []
    started = time.perf_counter()
    while arm.total_evaluations < budget:
        result = arm.run(min(50, budget - arm.total_evaluations))
        assert result.evaluations_used > 0
        checkpoints.append([arm.total_evaluations, compute_archive_hypervolume(result.solutions, norm)])
    entries = list(result.solutions.entries)
    return dict(
        budget=budget,
        evaluations_used=arm.total_evaluations,
        checkpoints=checkpoints,
        hypervolume=checkpoints[-1][1],
        runtime_seconds=time.perf_counter() - started,
        front_entries=entry_rows(entries),
        pareto_front=[list(e.objectives) for e in entries],
        completed=True,
    )


def run_method(instance, seed, method, budget=3000):
    """Runs a method by its campaign name; cut_<FE> is the PS-MB with that cut."""
    if method == "early_moead_600":
        return run_psmb(instance, seed, budget)
    if method.startswith("cut_"):
        return run_psmb(instance, seed, budget, cut=int(method[4:]))
    if method == "passive":
        return run_regional_policy_experiment(instance, seed, PAIR, "dynamic", False, budget)
    if method == "moead_blmr_scaled":
        return run_regional_policy_experiment(instance, seed, PAIR, "scaled", False, budget)
    if method == "explorer_solo":
        return run_blmr(instance, seed, budget)
    return run_native(instance, seed, method, budget)
