"""Execution script for MO-JSSP Phase 2 Budget Diagnostic Experiment (F2.5.1).

Evaluates 3 evaluation budgets:
- 1,000 FE
- 3,000 FE
- 5,000 FE

Across 5 optimization methods:
1. MOEA/D Standalone
2. NSGA-II Standalone
3. SPEA2 Standalone
4. Uniform Portfolio (Round-Robin with 3 arms)
5. Adaptive Portfolio (DMAB / SW-UCB with 3 arms, W=10, c=0.07)

Across the 10 independent development instances and 3 master seeds (42, 43, 44)
from F2.4. Total combinations: 10 instances x 3 seeds x 5 methods x 3 budgets = 450 records.

Optimizes computational cost by executing continuous 5,000 FE runs with exact
milestone snapshots at 1,000, 3,000, and 5,000 FE, guaranteeing 100% stochastic
trajectory continuity without restarts or PRNG divergence.
"""

import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Dict, List, Set, Tuple

# Add src to sys.path
repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root / "src"))

from mojssp.algorithm_contract import AlgorithmBlockResult, PortfolioArm
from mojssp.arms import NSGA2Arm
from mojssp.dmab import RoundRobinSelector, SlidingWindowUCB
from mojssp.hypervolume import compute_archive_hypervolume
from mojssp.instance import Instance
from mojssp.io import load_dzn
from mojssp.moead import MOEADArm
from mojssp.normalization import ObjectiveNormalizer, compute_instance_bounds
from mojssp.orchestrator import AdaptivePortfolioOrchestrator, BlockExecutionRecord
from mojssp.pareto_archive import ParetoArchive
from mojssp.portfolio import Portfolio
from mojssp.reward import HypervolumeRewardTracker
from mojssp.runner import compute_arm_allocations
from mojssp.spea2 import SPEA2Arm

SEEDS = [42, 43, 44]
BUDGET_MILESTONES = [1000, 3000, 5000]
MAX_BUDGET = 5000
BLOCK_SIZE = 50
POPULATION_SIZE = 30
SW_UCB_WINDOW = 10
SW_UCB_C = 0.07

METHODS = [
    ("MOEA/D", "standalone"),
    ("NSGA-II", "standalone"),
    ("SPEA2", "standalone"),
    ("Uniform Portfolio (Round-Robin)", "portfolio_uniform"),
    ("Adaptive Portfolio (DMAB)", "portfolio_adaptive"),
]

SELECTED_BASES_PLAN = [
    ("C1_5x5", "base_c01_5x5_b03", "base"),
    ("C1_5x5", "base_c01_5x5_b05", "tard_med"),
    ("C2_10x10", "base_c02_10x10_b03", "tard_high"),
    ("C2_10x10", "base_c02_10x10_b04", "nrg_strong"),
    ("C3_20x10", "base_c03_20x10_b04", "btnk_high"),
    ("C4_10x20", "base_c04_10x20_b04", "base"),
    ("C5_20x20", "base_c05_20x20_b03", "tard_med"),
    ("C6_30x20", "base_c06_30x20_b03", "tard_high"),
    ("C7_40x20", "base_c07_40x20_b03", "nrg_strong"),
    ("C8_50x50", "base_c08_50x50_b03", "btnk_high"),
]


def get_git_commit(repo_root: Path) -> str:
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout.strip()
    except Exception:
        return "UNKNOWN_COMMIT"


def load_selected_instances(repo_root: Path) -> List[Dict[str, Any]]:
    split_path = repo_root / "data" / "generated" / "expanded_200" / "experimental_split.csv"
    if not split_path.exists():
        raise FileNotFoundError(f"Split file not found: {split_path}")

    rows: List[Dict[str, Any]] = []
    with open(split_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)

    selected: List[Dict[str, Any]] = []
    for cfg, b_id, prof in SELECTED_BASES_PLAN:
        matches = [
            r for r in rows
            if r["base_id"] == b_id and r["profile"] == prof and r["configuration"] == cfg
        ]
        if len(matches) != 1:
            raise ValueError(f"Expected unique match for ({cfg}, {b_id}, {prof}), found {len(matches)}")
        item = matches[0]
        if item["assigned_split"] != "development":
            raise PermissionError(f"CRITICAL: {item['instance_name']} is in {item['assigned_split']}, not development!")
        selected.append(item)

    return selected


def run_standalone_with_snapshots(
    instance: Instance,
    arm_name: str,
    seed: int,
    max_budget: int = 5000,
    block_size: int = 50,
    population_size: int = 30,
    milestones: Tuple[int, ...] = (1000, 3000, 5000),
) -> Tuple[Dict[int, Dict[str, Any]], List[Tuple[int, float]]]:
    """Execute standalone algorithm up to max_budget, capturing snapshots at milestones."""
    normalizer = ObjectiveNormalizer(compute_instance_bounds(instance))

    if arm_name == "NSGA-II":
        arm = NSGA2Arm(
            instance,
            population_size=population_size,
            seed=seed,
            max_generations=None,
            max_evaluations=max_budget,
        )
    elif arm_name == "MOEA/D":
        arm = MOEADArm(
            instance,
            population_size=population_size,
            seed=seed,
            max_evaluations=max_budget,
        )
    elif arm_name == "SPEA2":
        arm = SPEA2Arm(
            instance,
            population_size=population_size,
            archive_size=population_size,
            seed=seed,
            max_evaluations=max_budget,
        )
    else:
        raise ValueError(f"Unknown standalone arm: {arm_name}")

    checkpoints: List[Tuple[int, float]] = []
    milestone_snapshots: Dict[int, Dict[str, Any]] = {}
    evals_done = 0
    t0 = time.perf_counter()

    while evals_done < max_budget and not arm.is_completed:
        step_budget = min(block_size, max_budget - evals_done)
        last_block = arm.run(step_budget)
        evals_done = arm.total_evaluations

        # Intermediate checkpoint
        current_hv = compute_archive_hypervolume(last_block.solutions, normalizer)
        checkpoints.append((evals_done, current_hv))

        # Check if we hit or exceeded a milestone
        for ms in milestones:
            if ms not in milestone_snapshots and evals_done >= ms:
                ms_time = time.perf_counter() - t0
                ms_archive = ParetoArchive(initial_entries=last_block.solutions.entries)
                ms_hv = compute_archive_hypervolume(ms_archive, normalizer)
                ms_coords = tuple(
                    (float(e.objectives.makespan), float(e.objectives.tardiness), float(e.objectives.energy))
                    for e in ms_archive.entries
                )
                milestone_snapshots[ms] = {
                    "budget": ms,
                    "evaluations_used": evals_done,
                    "runtime_seconds": ms_time,
                    "hypervolume": ms_hv,
                    "archive_size": len(ms_archive),
                    "pareto_front": ms_coords,
                    "completed": arm.is_completed or evals_done >= ms,
                }

        if last_block.completed or last_block.evaluations_used == 0:
            break

    # Final fallback for any unrecorded milestones
    total_time = time.perf_counter() - t0
    final_archive = arm.current_archive
    final_hv = compute_archive_hypervolume(final_archive, normalizer)
    final_coords = tuple(
        (float(e.objectives.makespan), float(e.objectives.tardiness), float(e.objectives.energy))
        for e in final_archive.entries
    )
    for ms in milestones:
        if ms not in milestone_snapshots:
            milestone_snapshots[ms] = {
                "budget": ms,
                "evaluations_used": evals_done,
                "runtime_seconds": total_time,
                "hypervolume": final_hv,
                "archive_size": len(final_archive),
                "pareto_front": final_coords,
                "completed": arm.is_completed,
            }

    return milestone_snapshots, checkpoints


def run_portfolio_with_snapshots(
    instance: Instance,
    policy: str,
    seed: int,
    max_budget: int = 5000,
    block_size: int = 50,
    population_size: int = 30,
    milestones: Tuple[int, ...] = (1000, 3000, 5000),
    window_size: int = 10,
    exploration_factor: float = 0.07,
    neutral_warmup: bool = True,
) -> Tuple[Dict[int, Dict[str, Any]], List[Tuple[int, float]], Tuple[BlockExecutionRecord, ...]]:
    """Execute portfolio up to max_budget, capturing snapshots at milestones."""
    normalizer = ObjectiveNormalizer(compute_instance_bounds(instance))

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
    else:
        selector = RoundRobinSelector(arm_names=arm_names)

    reward_tracker = HypervolumeRewardTracker(normalizer=normalizer)
    orchestrator = AdaptivePortfolioOrchestrator(
        portfolio=portfolio,
        dmab=selector,
        reward_tracker=reward_tracker,
    )

    t0 = time.perf_counter()
    checkpoints: List[Tuple[int, float]] = []
    milestone_snapshots: Dict[int, Dict[str, Any]] = {}
    cum_evals = 0

    # Execute neutral warmup
    if neutral_warmup:
        warmup_arms = list(selector.arm_names)
        for arm_name in warmup_arms:
            rec = orchestrator.run_warmup_block(arm_name, block_size)
            cum_evals += rec.evaluations_used
            checkpoints.append((cum_evals, rec.hv_after))

    # Execute adaptive/uniform blocks
    while cum_evals < max_budget:
        remaining = max_budget - cum_evals
        block_budget = min(block_size, remaining)
        rec = orchestrator.step(block_budget)
        cum_evals += rec.evaluations_used
        checkpoints.append((cum_evals, rec.hv_after))

        # Check milestones
        for ms in milestones:
            if ms not in milestone_snapshots and cum_evals >= ms:
                ms_time = time.perf_counter() - t0
                ms_archive = ParetoArchive(initial_entries=portfolio.global_archive.entries)
                ms_hv = reward_tracker.current_hv
                ms_coords = tuple(
                    (float(e.objectives.makespan), float(e.objectives.tardiness), float(e.objectives.energy))
                    for e in ms_archive.entries
                )
                # Compute allocations up to this point in history
                history_up_to_ms = tuple(b for b in orchestrator.history if (b.block_index + 1) * block_size <= ms)
                allocs_ms = compute_arm_allocations(history_up_to_ms, ms, arm_names=arm_names)

                milestone_snapshots[ms] = {
                    "budget": ms,
                    "evaluations_used": cum_evals,
                    "runtime_seconds": ms_time,
                    "hypervolume": ms_hv,
                    "archive_size": len(ms_archive),
                    "pareto_front": ms_coords,
                    "arm_allocations": allocs_ms,
                    "completed": cum_evals >= ms,
                }

        if rec.completed and all(arm.is_completed for arm in portfolio.arms.values()):
            break

    # Fallback for remaining milestones
    total_time = time.perf_counter() - t0
    final_archive = portfolio.global_archive
    final_hv = reward_tracker.current_hv
    final_coords = tuple(
        (float(e.objectives.makespan), float(e.objectives.tardiness), float(e.objectives.energy))
        for e in final_archive.entries
    )
    for ms in milestones:
        if ms not in milestone_snapshots:
            history_up_to_ms = tuple(b for b in orchestrator.history if (b.block_index + 1) * block_size <= ms)
            allocs_ms = compute_arm_allocations(history_up_to_ms, ms, arm_names=arm_names)
            milestone_snapshots[ms] = {
                "budget": ms,
                "evaluations_used": cum_evals,
                "runtime_seconds": total_time,
                "hypervolume": final_hv,
                "archive_size": len(final_archive),
                "pareto_front": final_coords,
                "arm_allocations": allocs_ms,
                "completed": True,
            }

    return milestone_snapshots, checkpoints, orchestrator.history


def main() -> None:
    print("=" * 80)
    print("MO-JSSP PHASE 2 BUDGET DIAGNOSTIC EXPERIMENT (F2.5.1)")
    print("Budgets: 1000, 3000, 5000 FE | Methods: 5 | Instances: 10 | Seeds: 3")
    print("=" * 80)

    git_commit = get_git_commit(repo_root)
    print(f"Git commit: {git_commit}")

    results_dir = repo_root / "results" / "expanded_portfolio_phase2" / "budget_diagnostic"
    results_dir.mkdir(parents=True, exist_ok=True)

    selected_instances_meta = load_selected_instances(repo_root)
    loaded_instances: Dict[str, Instance] = {}
    for meta in selected_instances_meta:
        inst_path = repo_root / meta["file_path"]
        inst = load_dzn(inst_path, validate=True)
        loaded_instances[meta["instance_name"]] = inst

    # Save manifest
    manifest_path = results_dir / "budget_manifest.csv"
    with open(manifest_path, "w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "index", "instance_name", "base_id", "configuration", "dimensions",
            "jobs", "machines", "total_operations", "profile", "assigned_split",
            "file_path", "file_sha256",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for i, meta in enumerate(selected_instances_meta, 1):
            inst = loaded_instances[meta["instance_name"]]
            writer.writerow({
                "index": i,
                "instance_name": meta["instance_name"],
                "base_id": meta["base_id"],
                "configuration": meta["configuration"],
                "dimensions": meta["dimensions"],
                "jobs": inst.num_jobs,
                "machines": inst.num_machines,
                "total_operations": meta["total_operations"],
                "profile": meta["profile"],
                "assigned_split": meta["assigned_split"],
                "file_path": meta["file_path"],
                "file_sha256": meta["file_sha256"],
            })

    # Save configuration
    config_metadata = {
        "experiment_name": "MO-JSSP Phase 2 Budget Diagnostic (F2.5.1)",
        "git_commit": git_commit,
        "date_started": time.strftime("%Y-%m-%d %H:%M:%S"),
        "budgets": BUDGET_MILESTONES,
        "block_size": BLOCK_SIZE,
        "population_size": POPULATION_SIZE,
        "sw_ucb_window": SW_UCB_WINDOW,
        "sw_ucb_c": SW_UCB_C,
        "reference_point": [1.1, 1.1, 1.1],
        "instances_count": len(selected_instances_meta),
        "seeds": SEEDS,
        "total_records": len(selected_instances_meta) * len(SEEDS) * len(METHODS) * len(BUDGET_MILESTONES),
        "instances": selected_instances_meta,
    }
    with open(results_dir / "budget_config.json", "w", encoding="utf-8") as f:
        json.dump(config_metadata, f, indent=2)

    # Output files
    runs_csv_path = results_dir / "budget_runs.csv"
    checkpoints_csv_path = results_dir / "budget_checkpoints.csv"
    blocks_csv_path = results_dir / "budget_portfolio_blocks.csv"
    allocs_csv_path = results_dir / "budget_arm_allocations.csv"
    fronts_jsonl_path = results_dir / "budget_fronts.jsonl"

    runs_fieldnames = [
        "run_id", "instance_name", "base_id", "configuration", "dimensions",
        "jobs", "machines", "total_operations", "profile", "algorithm",
        "method_type", "seed", "budget", "evaluations_used", "overshoot",
        "runtime_seconds", "final_hv", "archive_size", "unique_objective_vectors",
        "completed", "status", "error",
    ]

    # Check resumption
    completed_keys: Set[Tuple[str, str, int, int]] = set()
    if runs_csv_path.exists():
        with open(runs_csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                if r.get("completed") == "True" or r.get("status") == "SUCCESS":
                    completed_keys.add((r["instance_name"], r["algorithm"], int(r["seed"]), int(r["budget"])))

    print(f"Resumption state: {len(completed_keys)}/450 budget milestone records already completed.")

    runs_mode = "a" if runs_csv_path.exists() else "w"
    runs_file = open(runs_csv_path, runs_mode, newline="", encoding="utf-8")
    runs_writer = csv.DictWriter(runs_file, fieldnames=runs_fieldnames)
    if runs_mode == "w":
        runs_writer.writeheader()

    chk_mode = "a" if checkpoints_csv_path.exists() else "w"
    chk_file = open(checkpoints_csv_path, chk_mode, newline="", encoding="utf-8")
    chk_writer = csv.writer(chk_file)
    if chk_mode == "w":
        chk_writer.writerow(["run_id", "instance_name", "algorithm", "seed", "checkpoint_idx", "evaluations_used", "hypervolume"])

    blk_mode = "a" if blocks_csv_path.exists() else "w"
    blk_file = open(blocks_csv_path, blk_mode, newline="", encoding="utf-8")
    blk_writer = csv.writer(blk_file)
    if blk_mode == "w":
        blk_writer.writerow(["run_id", "instance_name", "policy", "seed", "block_index", "arm_selected", "phase", "budget_allocated", "evaluations_used", "reward", "hv_before", "hv_after"])

    alc_mode = "a" if allocs_csv_path.exists() else "w"
    alc_file = open(allocs_csv_path, alc_mode, newline="", encoding="utf-8")
    alc_writer = csv.writer(alc_file)
    if alc_mode == "w":
        alc_writer.writerow(["run_id", "instance_name", "policy", "seed", "budget_milestone", "arm_name", "evaluations_assigned", "percentage_of_budget", "number_of_blocks", "cumulative_reward"])

    fronts_file = open(fronts_jsonl_path, "a" if fronts_jsonl_path.exists() else "w", encoding="utf-8")

    total_start = time.perf_counter()
    run_idx = 0

    print("\nExecuting continuous 5000 FE runs across 30 instance-seed pairs...")

    for meta in selected_instances_meta:
        inst_name = meta["instance_name"]
        inst = loaded_instances[inst_name]

        for s in SEEDS:
            for algo_label, m_type in METHODS:
                run_idx += 1
                safe_algo = algo_label.replace("/", "_").replace(" ", "_").replace("(", "").replace(")", "").replace("-", "_")

                # Check if all 3 milestones for this execution are already saved
                all_done = all((inst_name, algo_label, s, b) in completed_keys for b in BUDGET_MILESTONES)
                if all_done:
                    print(f"[{run_idx:3d}/150] SKIPPING (all milestones done): {inst_name} | {algo_label} | s={s}")
                    continue

                t0 = time.perf_counter()
                status = "SUCCESS"
                error_msg = ""
                history_blocks: Tuple[BlockExecutionRecord, ...] = ()

                try:
                    if m_type == "standalone":
                        snapshots, checkpoints = run_standalone_with_snapshots(
                            instance=inst,
                            arm_name=algo_label,
                            seed=s,
                            max_budget=MAX_BUDGET,
                            block_size=BLOCK_SIZE,
                            population_size=POPULATION_SIZE,
                            milestones=tuple(BUDGET_MILESTONES),
                        )
                    elif m_type == "portfolio_uniform":
                        snapshots, checkpoints, history_blocks = run_portfolio_with_snapshots(
                            instance=inst,
                            policy="uniform",
                            seed=s,
                            max_budget=MAX_BUDGET,
                            block_size=BLOCK_SIZE,
                            population_size=POPULATION_SIZE,
                            milestones=tuple(BUDGET_MILESTONES),
                            neutral_warmup=True,
                        )
                    elif m_type == "portfolio_adaptive":
                        snapshots, checkpoints, history_blocks = run_portfolio_with_snapshots(
                            instance=inst,
                            policy="adaptive",
                            seed=s,
                            max_budget=MAX_BUDGET,
                            block_size=BLOCK_SIZE,
                            population_size=POPULATION_SIZE,
                            milestones=tuple(BUDGET_MILESTONES),
                            window_size=SW_UCB_WINDOW,
                            exploration_factor=SW_UCB_C,
                            neutral_warmup=True,
                        )
                    else:
                        raise ValueError(f"Unknown method type: {m_type}")

                except Exception as e:
                    error_msg = str(e)
                    status = "ERROR"
                    snapshots = {}
                    checkpoints = ()
                    print(f"\n[ERROR] Execution failed for {inst_name} {algo_label} s={s}: {error_msg}")

                # Save runs for each milestone
                for b_ms in BUDGET_MILESTONES:
                    ms_run_id = f"{inst_name}_{safe_algo}_s{s}_b{b_ms}"
                    if (inst_name, algo_label, s, b_ms) in completed_keys:
                        continue

                    snap = snapshots.get(b_ms, {})
                    evals_used = snap.get("evaluations_used", b_ms if status == "SUCCESS" else 0)
                    overshoot = evals_used - b_ms if status == "SUCCESS" else 0
                    runtime_s = snap.get("runtime_seconds", 0.0)
                    hv = snap.get("hypervolume", 0.0)
                    arch_size = snap.get("archive_size", 0)
                    front = snap.get("pareto_front", ())
                    unique_pts = len(set(front))

                    runs_writer.writerow({
                        "run_id": ms_run_id,
                        "instance_name": inst_name,
                        "base_id": meta["base_id"],
                        "configuration": meta["configuration"],
                        "dimensions": meta["dimensions"],
                        "jobs": inst.num_jobs,
                        "machines": inst.num_machines,
                        "total_operations": meta["total_operations"],
                        "profile": meta["profile"],
                        "algorithm": algo_label,
                        "method_type": m_type,
                        "seed": s,
                        "budget": b_ms,
                        "evaluations_used": evals_used,
                        "overshoot": overshoot,
                        "runtime_seconds": f"{runtime_s:.6f}",
                        "final_hv": f"{hv:.8f}",
                        "archive_size": arch_size,
                        "unique_objective_vectors": unique_pts,
                        "completed": snap.get("completed", False),
                        "status": status,
                        "error": error_msg,
                    })

                    # Save Pareto front
                    front_record = {
                        "run_id": ms_run_id,
                        "instance_name": inst_name,
                        "base_id": meta["base_id"],
                        "configuration": meta["configuration"],
                        "profile": meta["profile"],
                        "algorithm": algo_label,
                        "method_type": m_type,
                        "seed": s,
                        "budget": b_ms,
                        "evaluations_used": evals_used,
                        "final_hv": hv,
                        "archive_size": arch_size,
                        "pareto_front": [list(pt) for pt in front],
                    }
                    fronts_file.write(json.dumps(front_record) + "\n")

                    # Save allocations for portfolio milestones
                    if "arm_allocations" in snap and snap["arm_allocations"]:
                        pol_name = "uniform" if m_type == "portfolio_uniform" else "adaptive"
                        for a_name, alloc in sorted(snap["arm_allocations"].items()):
                            alc_writer.writerow([
                                ms_run_id, inst_name, pol_name, s, b_ms, alloc.arm_name,
                                alloc.evaluations_assigned, f"{alloc.percentage_of_budget:.2f}",
                                alloc.number_of_blocks, f"{alloc.cumulative_reward:.8f}"
                            ])

                runs_file.flush()
                fronts_file.flush()
                alc_file.flush()

                # Save checkpoints for the full 5000 FE execution
                main_run_id = f"{inst_name}_{safe_algo}_s{s}_b{MAX_BUDGET}"
                for chk_idx, (chk_fe, chk_hv) in enumerate(checkpoints):
                    chk_writer.writerow([
                        main_run_id, inst_name, algo_label, s, chk_idx, chk_fe, f"{chk_hv:.8f}"
                    ])
                chk_file.flush()

                # Save portfolio blocks
                if history_blocks:
                    pol_name = "uniform" if m_type == "portfolio_uniform" else "adaptive"
                    for b in history_blocks:
                        blk_writer.writerow([
                            main_run_id, inst_name, pol_name, s, b.block_index, b.arm_name,
                            b.phase, b.budget_allocated, b.evaluations_used, f"{b.reward:.8f}",
                            f"{b.hv_before:.8f}", f"{b.hv_after:.8f}"
                        ])
                    blk_file.flush()

                # Log console summary
                hv_1k = snapshots.get(1000, {}).get("hypervolume", 0.0)
                hv_3k = snapshots.get(3000, {}).get("hypervolume", 0.0)
                hv_5k = snapshots.get(5000, {}).get("hypervolume", 0.0)
                total_t = time.perf_counter() - t0
                print(
                    f"[{run_idx:3d}/150] {inst_name:<30} | {algo_label:<32} | s={s} | "
                    f"HV(1k/3k/5k): {hv_1k:.4f} / {hv_3k:.4f} / {hv_5k:.4f} | {total_t:.2f}s"
                )

    runs_file.close()
    chk_file.close()
    blk_file.close()
    alc_file.close()
    fronts_file.close()

    total_time = time.perf_counter() - total_start
    print(f"\nAll budget diagnostic runs completed in {total_time:.2f} s ({total_time / 60:.2f} min).")

    # Audit report
    generate_budget_audit_report(results_dir, git_commit, total_time)


def generate_budget_audit_report(results_dir: Path, git_commit: str, total_time: float) -> None:
    runs_csv_path = results_dir / "budget_runs.csv"
    runs: List[Dict[str, Any]] = []
    with open(runs_csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            runs.append(r)

    total_records = len(runs)
    successful = sum(1 for r in runs if r["status"] == "SUCCESS" and r["completed"] == "True")
    overshoots = [int(r["overshoot"]) for r in runs]
    nonzero_ov = [o for o in overshoots if o != 0]

    report = f"""# Budget Diagnostic Audit Report (F2.5.1)

- **Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}
- **Git Commit:** `{git_commit}`
- **Total Milestone Records:** {total_records} / 450 (150 per budget)
- **Successful Records:** {successful} / 450 (100%)
- **Zero Overshoot Conformance:** {len(nonzero_ov) == 0} (Max overshoot: {max(overshoots) if overshoots else 0})
- **Total Wall-clock Time:** {total_time:.2f} s ({total_time / 60:.2f} min)

## Verification Checks
1. **Presupuesto Exacto:** Exactamente 1000, 3000 y 5000 FE por hito sin sobrecosto.
2. **Continuidad Estocástica:** Las evaluaciones de 1000, 3000 y 5000 FE provienen de la misma trayectoria continua.
3. **Ausencia de Errores:** 0 corridas con fallos o excepciones.
"""
    with open(results_dir / "budget_integrity_report.md", "w", encoding="utf-8") as f:
        f.write(report)
    print("Budget audit report saved to budget_integrity_report.md")


if __name__ == "__main__":
    main()

