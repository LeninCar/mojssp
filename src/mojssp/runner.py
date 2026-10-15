"""Experimental runner, result containers, and CSV persistence for MO-JSSP experiments.

Phase 8.3 implementation supporting standalone arm benchmarking, adaptive portfolio
execution, budget allocation tracking, trajectory checkpointing, and raw CSV persistence.
"""

import csv
import json
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from .algorithm_contract import AlgorithmBlockResult, PortfolioArm
from .arms import MOPSOArm, NSGA2Arm, NSGA2LSArm
from .moead import MOEADArm
from .spea2 import SPEA2Arm
from .dmab import RoundRobinSelector, SlidingWindowUCB
from .hypervolume import compute_archive_hypervolume
from .instance import Instance
from .normalization import ObjectiveNormalizer, compute_instance_bounds
from .orchestrator import (
    AdaptiveExecutionResult,
    AdaptivePortfolioOrchestrator,
    BlockExecutionRecord,
    HypervolumeRewardTracker,
)
from .pareto_archive import ParetoArchive
from .portfolio import Portfolio


@dataclass(frozen=True)
class ArmAllocation:
    """Summary of budget allocated to a specific arm during a portfolio run.

    Attributes:
        arm_name: Canonical identifier of the arm.
        evaluations_assigned: Total evaluations consumed by this arm.
        percentage_of_budget: Percentage of total portfolio budget consumed.
        number_of_blocks: Number of blocks executed by this arm.
        cumulative_reward: Total reward obtained after warmup (probe_reward + ordinary_adaptive_reward).
        warmup_reward: Reward obtained during the neutral warmup block (Phase 1).
        probe_reward: Reward obtained during the initial adaptive probe block (Phase 2).
        ordinary_adaptive_reward: Reward obtained during ordinary SW-UCB selection (Phase 3).
        post_warmup_reward: Combined reward obtained during active search (probe_reward + ordinary_adaptive_reward).
        adaptive_reward: Alias for post_warmup_reward for backwards compatibility.
    """

    arm_name: str
    evaluations_assigned: int
    percentage_of_budget: float
    number_of_blocks: int
    cumulative_reward: float
    warmup_reward: float = 0.0
    probe_reward: float = 0.0
    ordinary_adaptive_reward: float = 0.0
    post_warmup_reward: float = 0.0
    adaptive_reward: float = 0.0


@dataclass(frozen=True)
class RunResult:
    """Standardized record of an experimental execution (standalone or portfolio)."""

    run_id: str
    instance: str
    run_type: str  # 'standalone' or 'portfolio'
    algorithm: str  # 'NSGA-II', 'MOPSO', 'NSGA-II+LS', 'Adaptive Portfolio'
    seed: int
    budget: int
    evaluations_used: int
    runtime_seconds: float
    hypervolume: float
    archive_size: int
    completed: bool
    pareto_front: Tuple[Tuple[float, float, float], ...]
    checkpoints: Tuple[Tuple[int, float], ...] = ()
    arm_allocations: Optional[Dict[str, ArmAllocation]] = None


def compute_arm_allocations(
    history: Sequence[BlockExecutionRecord],
    total_budget: int,
    arm_names: Sequence[str] = ("NSGA-II", "MOPSO", "NSGA-II+LS"),
) -> Dict[str, ArmAllocation]:
    """Aggregate evaluations, block counts, and rewards by arm across a portfolio run.

    Distinguishes neutral warmup rewards from active adaptive rewards so that
    cumulative_reward accurately reflects DMAB performance without initialization bias.

    Args:
        history: Sequence of BlockExecutionRecord detailing the blocks executed.
        total_budget: Total evaluation budget of the portfolio run.
        arm_names: Canonical arm identifiers.

    Returns:
        Mapping from arm name to ArmAllocation.
    """
    evals: Dict[str, int] = {name: 0 for name in arm_names}
    blocks: Dict[str, int] = {name: 0 for name in arm_names}
    warmup_rewards: Dict[str, float] = {name: 0.0 for name in arm_names}
    probe_rewards: Dict[str, float] = {name: 0.0 for name in arm_names}
    ordinary_rewards: Dict[str, float] = {name: 0.0 for name in arm_names}

    for b in history:
        arm = b.arm_name
        if arm not in evals:
            evals[arm] = 0
            blocks[arm] = 0
            warmup_rewards[arm] = 0.0
            probe_rewards[arm] = 0.0
            ordinary_rewards[arm] = 0.0
        evals[arm] += b.evaluations_used
        blocks[arm] += 1
        if b.phase == "warmup":
            warmup_rewards[arm] += b.reward
        elif b.phase == "initial_probe":
            probe_rewards[arm] += b.reward
        else:
            ordinary_rewards[arm] += b.reward

    allocations: Dict[str, ArmAllocation] = {}
    for arm in sorted(evals.keys()):
        pct = (evals[arm] / total_budget * 100.0) if total_budget > 0 else 0.0
        post_warmup = float(probe_rewards[arm] + ordinary_rewards[arm])
        allocations[arm] = ArmAllocation(
            arm_name=arm,
            evaluations_assigned=evals[arm],
            percentage_of_budget=pct,
            number_of_blocks=blocks[arm],
            cumulative_reward=post_warmup,
            warmup_reward=float(warmup_rewards[arm]),
            probe_reward=float(probe_rewards[arm]),
            ordinary_adaptive_reward=float(ordinary_rewards[arm]),
            post_warmup_reward=post_warmup,
            adaptive_reward=post_warmup,
        )

    return allocations


def run_standalone_experiment(
    instance: Instance,
    arm_name: str,
    seed: int,
    budget: int,
    block_size: int = 50,
    population_size: int = 30,
) -> RunResult:
    """Execute a standalone algorithm arm under a strict evaluation budget.

    Executes in synchronized increments of `block_size` evaluations to record
    trajectory checkpoints without altering the algorithm's bit-for-bit trajectory.

    Args:
        instance: Problem instance.
        arm_name: 'NSGA-II', 'MOPSO', or 'NSGA-II+LS'.
        seed: Pseudo-random seed.
        budget: Total evaluation budget (> 0).
        block_size: Checkpoint interval in evaluations (> 0).
        population_size: Population/swarm size for the algorithm.

    Returns:
        RunResult container with final metrics and intermediate checkpoints.
    """
    normalizer = ObjectiveNormalizer(compute_instance_bounds(instance))

    if arm_name == "NSGA-II":
        arm = NSGA2Arm(
            instance,
            population_size=population_size,
            seed=seed,
            max_generations=None,
            max_evaluations=budget,
        )
    elif arm_name == "MOPSO":
        arm = MOPSOArm(
            instance,
            population_size=population_size,
            seed=seed,
            max_evaluations=budget,
        )
    elif arm_name == "NSGA-II+LS":
        arm = NSGA2LSArm(
            instance,
            population_size=population_size,
            seed=seed,
            max_evaluations=budget,
            max_ls_iterations=10,
            max_ls_neighbors=10,
        )
    elif arm_name == "MOEA/D":
        arm = MOEADArm(
            instance,
            population_size=population_size,
            seed=seed,
            max_evaluations=budget,
        )
    elif arm_name == "SPEA2":
        arm = SPEA2Arm(
            instance,
            population_size=population_size,
            archive_size=population_size,
            seed=seed,
            max_evaluations=budget,
        )
    else:
        raise ValueError(f"Unknown standalone arm name: {arm_name}")

    checkpoints: List[Tuple[int, float]] = []
    evals_done = 0

    t0 = time.perf_counter()
    last_block_res: Optional[AlgorithmBlockResult] = None

    while evals_done < budget and not arm.is_completed:
        step_budget = min(block_size, budget - evals_done)
        last_block_res = arm.run(step_budget)
        evals_done = arm.total_evaluations

        # Compute checkpoint HV on intermediate archive snapshot
        current_hv = compute_archive_hypervolume(last_block_res.solutions, normalizer)
        checkpoints.append((evals_done, current_hv))

        if last_block_res.completed or last_block_res.evaluations_used == 0:
            break

    runtime_s = time.perf_counter() - t0

    archive = (
        last_block_res.solutions if last_block_res is not None else ParetoArchive()
    )
    final_hv = compute_archive_hypervolume(archive, normalizer)
    front_coords = tuple(
        (float(e.objectives.makespan), float(e.objectives.tardiness), float(e.objectives.energy))
        for e in archive.entries
    )

    run_id = f"{instance.name}_{arm_name.replace('+', '_')}_s{seed}_b{budget}"

    return RunResult(
        run_id=run_id,
        instance=instance.name,
        run_type="standalone",
        algorithm=arm_name,
        seed=seed,
        budget=budget,
        evaluations_used=arm.total_evaluations,
        runtime_seconds=runtime_s,
        hypervolume=final_hv,
        archive_size=len(archive),
        completed=arm.is_completed,
        pareto_front=front_coords,
        checkpoints=tuple(checkpoints),
        arm_allocations=None,
    )


def run_portfolio_experiment(
    instance: Instance,
    seed: int,
    total_budget: int,
    block_size: int = 50,
    population_size: int = 30,
    window_size: int = 10,
    exploration_factor: float = math.sqrt(2),
) -> Tuple[RunResult, Tuple[BlockExecutionRecord, ...]]:
    """Execute an adaptive portfolio run with dynamic DMAB selection.

    Args:
        instance: Problem instance.
        seed: Master seed for the portfolio and deterministic arm derivation.
        total_budget: Total evaluation budget for the portfolio (> 0).
        block_size: Evaluations allocated per block (> 0).
        population_size: Population/swarm size for constituent arms.
        window_size: Sliding window size W for SW-UCB.
        exploration_factor: Exploration coefficient c for SW-UCB.

    Returns:
        Tuple of (RunResult, history of BlockExecutionRecord).
    """
    normalizer = ObjectiveNormalizer(compute_instance_bounds(instance))

    # Deterministic seed derivation for independent pseudo-random streams
    seed_nsga2 = (seed * 10007 + 11) % (2**31 - 1)
    seed_mopso = (seed * 10007 + 23) % (2**31 - 1)
    seed_ls = (seed * 10007 + 37) % (2**31 - 1)

    arm_nsga2 = NSGA2Arm(instance, population_size=population_size, seed=seed_nsga2)
    arm_mopso = MOPSOArm(instance, population_size=population_size, seed=seed_mopso)
    arm_ls = NSGA2LSArm(
        instance,
        population_size=population_size,
        seed=seed_ls,
        max_ls_iterations=10,
        max_ls_neighbors=10,
    )

    arms: Dict[str, PortfolioArm] = {
        "NSGA-II": arm_nsga2,
        "MOPSO": arm_mopso,
        "NSGA-II+LS": arm_ls,
    }
    portfolio = Portfolio(arms)
    dmab = SlidingWindowUCB(
        arm_names=list(arms.keys()),
        window_size=window_size,
        exploration_factor=exploration_factor,
        seed=seed,
    )
    reward_tracker = HypervolumeRewardTracker(normalizer=normalizer)
    orchestrator = AdaptivePortfolioOrchestrator(
        portfolio=portfolio,
        dmab=dmab,
        reward_tracker=reward_tracker,
    )

    t0 = time.perf_counter()
    exec_res = orchestrator.run(total_budget=total_budget, block_size=block_size)
    runtime_s = time.perf_counter() - t0

    history = exec_res.history
    allocations = compute_arm_allocations(history, total_budget)

    checkpoints: List[Tuple[int, float]] = []
    cum_evals = 0
    for b in history:
        cum_evals += b.evaluations_used
        checkpoints.append((cum_evals, b.hv_after))

    final_archive = portfolio.global_archive
    final_hv = reward_tracker.current_hv
    front_coords = tuple(
        (float(e.objectives.makespan), float(e.objectives.tardiness), float(e.objectives.energy))
        for e in final_archive.entries
    )

    run_id = f"{instance.name}_Portfolio_s{seed}_b{total_budget}"

    result = RunResult(
        run_id=run_id,
        instance=instance.name,
        run_type="portfolio",
        algorithm="Adaptive Portfolio",
        seed=seed,
        budget=total_budget,
        evaluations_used=portfolio.total_evaluations,
        runtime_seconds=runtime_s,
        hypervolume=final_hv,
        archive_size=len(final_archive),
        completed=portfolio.total_evaluations >= total_budget,
        pareto_front=front_coords,
        checkpoints=tuple(checkpoints),
        arm_allocations=allocations,
    )

    return result, history


def run_phase2_portfolio_experiment(
    instance: Instance,
    seed: int,
    total_budget: int = 1000,
    block_size: int = 50,
    population_size: int = 30,
    policy: str = "adaptive",  # 'adaptive' (SW-UCB) or 'uniform' (Round-Robin)
    window_size: int = 10,
    exploration_factor: float = 0.07,
    neutral_warmup: bool = True,
) -> Tuple[RunResult, Tuple[BlockExecutionRecord, ...]]:
    """Execute a Phase 2 3-arm portfolio run [MOEA/D, NSGA-II, SPEA2].

    Supports both adaptive selection (SW-UCB) and uniform allocation (Round-Robin).
    Derives independent, deterministic pseudo-random seeds for each arm.
    Preserves exact budget accounting, Global Pareto Archive integration,
    and checkpoint telemetry without modifying historical functions.

    Args:
        instance: MO-JSSP problem instance.
        seed: Master seed for reproducible execution and arm derivation.
        total_budget: Total evaluation budget (> 0). Default: 1000.
        block_size: Evaluations allocated per block (> 0). Default: 50.
        population_size: Population size for constituent arms. Default: 30.
        policy: 'adaptive' for SW-UCB or 'uniform' for Round-Robin.
        window_size: Sliding window size W for SW-UCB. Default: 10.
        exploration_factor: Exploration parameter c for SW-UCB. Default: 0.07.
        neutral_warmup: Whether to execute neutral warm-up before adaptive selection. Default: True.

    Returns:
        Tuple of (RunResult, history of BlockExecutionRecord).

    Raises:
        ValueError: If policy is unknown, or budgets are non-positive.
    """
    if policy not in ("adaptive", "uniform"):
        raise ValueError(f"Unknown policy '{policy}'. Must be 'adaptive' or 'uniform'.")

    normalizer = ObjectiveNormalizer(compute_instance_bounds(instance))

    # Deterministic seed derivation for independent pseudo-random streams
    seed_moead = (seed * 10007 + 17) % (2**31 - 1)
    seed_nsga2 = (seed * 10007 + 29) % (2**31 - 1)
    seed_spea2 = (seed * 10007 + 43) % (2**31 - 1)

    arm_moead = MOEADArm(instance, population_size=population_size, seed=seed_moead)
    arm_nsga2 = NSGA2Arm(instance, population_size=population_size, max_generations=None, seed=seed_nsga2)
    arm_spea2 = SPEA2Arm(instance, population_size=population_size, archive_size=population_size, seed=seed_spea2)

    arms: Dict[str, PortfolioArm] = {
        "MOEA/D": arm_moead,
        "NSGA-II": arm_nsga2,
        "SPEA2": arm_spea2,
    }
    portfolio = Portfolio(arms)
    arm_names = list(arms.keys())

    if policy == "adaptive":
        selector = SlidingWindowUCB(
            arm_names=arm_names,
            window_size=window_size,
            exploration_factor=exploration_factor,
            seed=seed,
        )
        algo_label = "Adaptive Portfolio (DMAB)"
        policy_label = "adaptive"
    else:
        selector = RoundRobinSelector(arm_names=arm_names)
        algo_label = "Uniform Portfolio (Round-Robin)"
        policy_label = "uniform"

    reward_tracker = HypervolumeRewardTracker(normalizer=normalizer)
    orchestrator = AdaptivePortfolioOrchestrator(
        portfolio=portfolio,
        dmab=selector,
        reward_tracker=reward_tracker,
    )

    t0 = time.perf_counter()
    exec_res = orchestrator.run(
        total_budget=total_budget,
        block_size=block_size,
        neutral_warmup=neutral_warmup,
    )
    runtime_s = time.perf_counter() - t0

    history = exec_res.history
    allocations = compute_arm_allocations(history, total_budget, arm_names=arm_names)

    checkpoints: List[Tuple[int, float]] = []
    cum_evals = 0
    for b in history:
        cum_evals += b.evaluations_used
        checkpoints.append((cum_evals, b.hv_after))

    final_archive = portfolio.global_archive
    final_hv = reward_tracker.current_hv
    front_coords = tuple(
        (float(e.objectives.makespan), float(e.objectives.tardiness), float(e.objectives.energy))
        for e in final_archive.entries
    )

    run_id = f"{instance.name}_Portfolio_{policy_label}_s{seed}_b{total_budget}"

    result = RunResult(
        run_id=run_id,
        instance=instance.name,
        run_type="portfolio",
        algorithm=algo_label,
        seed=seed,
        budget=total_budget,
        evaluations_used=portfolio.total_evaluations,
        runtime_seconds=runtime_s,
        hypervolume=final_hv,
        archive_size=len(final_archive),
        completed=portfolio.total_evaluations >= total_budget,
        pareto_front=front_coords,
        checkpoints=tuple(checkpoints),
        arm_allocations=allocations,
    )

    return result, history


def export_results_to_csv(
    runs: Sequence[RunResult],
    portfolio_blocks: Sequence[Tuple[str, BlockExecutionRecord]],
    results_dir: Union[str, Path] = "results",
) -> None:
    """Export experimental runs and portfolio block traces to standardized CSV files.

    Directory structure created:
        results/
        ├── raw/
        │   ├── runs.csv
        │   ├── portfolio_blocks.csv
        │   └── checkpoints.csv
        ├── fronts/
        │   └── {run_id}.json
        ├── schedules/
        └── summaries/
            └── arm_allocations.csv

    Args:
        runs: Sequence of RunResult from standalone and portfolio executions.
        portfolio_blocks: Sequence of (run_id, BlockExecutionRecord) pairs.
        results_dir: Base directory for results storage.
    """
    base_dir = Path(results_dir)
    raw_dir = base_dir / "raw"
    fronts_dir = base_dir / "fronts"
    schedules_dir = base_dir / "schedules"
    summaries_dir = base_dir / "summaries"

    raw_dir.mkdir(parents=True, exist_ok=True)
    fronts_dir.mkdir(parents=True, exist_ok=True)
    schedules_dir.mkdir(parents=True, exist_ok=True)
    summaries_dir.mkdir(parents=True, exist_ok=True)

    # 1. Export runs.csv
    runs_csv_path = raw_dir / "runs.csv"
    with open(runs_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "run_id",
            "instance",
            "run_type",
            "algorithm",
            "seed",
            "budget",
            "evaluations_used",
            "runtime_seconds",
            "hypervolume",
            "archive_size",
            "completed",
            "total_blocks",
        ])
        for r in runs:
            total_blocks = len(r.checkpoints) if r.run_type == "portfolio" else ""
            writer.writerow([
                r.run_id,
                r.instance,
                r.run_type,
                r.algorithm,
                r.seed,
                r.budget,
                r.evaluations_used,
                f"{r.runtime_seconds:.6f}",
                f"{r.hypervolume:.8f}",
                r.archive_size,
                r.completed,
                total_blocks,
            ])

    # 2. Export portfolio_blocks.csv
    blocks_csv_path = raw_dir / "portfolio_blocks.csv"
    with open(blocks_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "run_id",
            "instance",
            "seed",
            "block_index",
            "arm_selected",
            "phase",
            "budget_allocated",
            "evaluations_used",
            "hv_before",
            "hv_after",
            "reward",
            "completed",
        ])
        for run_id, b in portfolio_blocks:
            # Parse instance and seed from run_id
            parts = run_id.split("_")
            writer.writerow([
                run_id,
                parts[0],
                parts[-2].replace("s", ""),
                b.block_index,
                b.arm_name,
                getattr(b, "phase", "adaptive"),
                b.budget_allocated,
                b.evaluations_used,
                f"{b.hv_before:.8f}",
                f"{b.hv_after:.8f}",
                f"{b.reward:.8f}",
                b.completed,
            ])

    # 3. Export checkpoints.csv
    checkpoints_csv_path = raw_dir / "checkpoints.csv"
    with open(checkpoints_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["run_id", "instance", "algorithm", "seed", "evaluations", "hypervolume"])
        for r in runs:
            for fe, hv in r.checkpoints:
                writer.writerow([r.run_id, r.instance, r.algorithm, r.seed, fe, f"{hv:.8f}"])

    # 4. Export arm_allocations.csv (summaries)
    alloc_csv_path = summaries_dir / "arm_allocations.csv"
    with open(alloc_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "run_id",
            "instance",
            "seed",
            "total_budget",
            "total_evaluations",
            "arm",
            "evaluations_assigned",
            "percentage_of_budget",
            "number_of_blocks",
            "cumulative_reward",
        ])
        for r in runs:
            if r.arm_allocations:
                for arm_name, alloc in sorted(r.arm_allocations.items()):
                    writer.writerow([
                        r.run_id,
                        r.instance,
                        r.seed,
                        r.budget,
                        r.evaluations_used,
                        alloc.arm_name,
                        alloc.evaluations_assigned,
                        f"{alloc.percentage_of_budget:.2f}",
                        alloc.number_of_blocks,
                        f"{alloc.cumulative_reward:.8f}",
                    ])

    # 5. Export Pareto fronts as JSON
    for r in runs:
        front_file = fronts_dir / f"{r.run_id}.json"
        with open(front_file, "w", encoding="utf-8") as f:
            json.dump({
                "run_id": r.run_id,
                "instance": r.instance,
                "algorithm": r.algorithm,
                "seed": r.seed,
                "budget": r.budget,
                "hypervolume": r.hypervolume,
                "archive_size": r.archive_size,
                "pareto_front": [
                    {"makespan": p[0], "tardiness": p[1], "energy": p[2]}
                    for p in r.pareto_front
                ],
            }, f, indent=2)
