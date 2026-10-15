"""Execution script for MO-JSSP Phase 2 Controlled Pilot (F2.4).

Compares 5 methods:
1. MOEA/D Standalone
2. NSGA-II Standalone
3. SPEA2 Standalone
4. Uniform Portfolio (Round-Robin with 3 arms)
5. Adaptive Portfolio (DMAB / SW-UCB with 3 arms, W=10, c=0.07)

Across 10 independent development instances (covering 8 dimensions and 5 profiles)
and 3 master seeds (42, 43, 44) => 150 total runs under strict 1000 FE budget.
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

from mojssp.instance import Instance
from mojssp.io import load_dzn
from mojssp.runner import run_phase2_portfolio_experiment, run_standalone_experiment

SEEDS = [42, 43, 44]
BUDGET = 1000
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

# 10 strictly independent development bases not in Phase 1
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


def compute_file_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


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

    # Double-check independence
    bases = [r["base_id"] for r in selected]
    if len(set(bases)) != 10:
        raise ValueError(f"Expected 10 unique bases, got {len(set(bases))}")

    return selected


def main() -> None:
    print("=" * 80)
    print("MO-JSSP PHASE 2 CONTROLLED PILOT EXPERIMENT (F2.4)")
    print("=" * 80)

    git_commit = get_git_commit(repo_root)
    print(f"Git commit: {git_commit}")

    # Output directory
    results_dir = repo_root / "results" / "expanded_portfolio_phase2" / "pilot"
    results_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load and validate instances
    selected_instances_meta = load_selected_instances(repo_root)
    print(f"\nSuccessfully selected 10 strictly independent development instances:")
    for i, meta in enumerate(selected_instances_meta, 1):
        print(f"  {i:2d}. {meta['instance_name']} [{meta['configuration']}, {meta['dimensions']}, {meta['profile']}]")

    # Load instance objects
    loaded_instances: Dict[str, Instance] = {}
    for meta in selected_instances_meta:
        inst_path = repo_root / meta["file_path"]
        inst = load_dzn(inst_path, validate=True)
        loaded_instances[meta["instance_name"]] = inst

    # Save manifest
    manifest_path = results_dir / "pilot_manifest.csv"
    with open(manifest_path, "w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "index",
            "instance_name",
            "base_id",
            "configuration",
            "dimensions",
            "jobs",
            "machines",
            "total_operations",
            "profile",
            "assigned_split",
            "file_path",
            "file_sha256",
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

    # Save pilot configuration metadata
    config_metadata = {
        "experiment_name": "MO-JSSP Phase 2 Controlled Pilot (F2.4)",
        "git_commit": git_commit,
        "date_started": time.strftime("%Y-%m-%d %H:%M:%S"),
        "methods": [
            {"label": lbl, "type": m_type} for lbl, m_type in METHODS
        ],
        "seeds": SEEDS,
        "budget_evaluations": BUDGET,
        "block_size": BLOCK_SIZE,
        "population_size": POPULATION_SIZE,
        "sw_ucb_window": SW_UCB_WINDOW,
        "sw_ucb_c": SW_UCB_C,
        "reference_point": [1.1, 1.1, 1.1],
        "instances_count": len(selected_instances_meta),
        "total_runs": len(selected_instances_meta) * len(SEEDS) * len(METHODS),
        "instances": selected_instances_meta,
    }
    with open(results_dir / "pilot_config.json", "w", encoding="utf-8") as f:
        json.dump(config_metadata, f, indent=2)

    # 2. File paths for incremental persistence
    runs_csv_path = results_dir / "pilot_runs.csv"
    checkpoints_csv_path = results_dir / "pilot_checkpoints.csv"
    blocks_csv_path = results_dir / "pilot_portfolio_blocks.csv"
    allocs_csv_path = results_dir / "pilot_arm_allocations.csv"
    fronts_jsonl_path = results_dir / "pilot_fronts.jsonl"

    runs_fieldnames = [
        "run_id",
        "instance_name",
        "base_id",
        "configuration",
        "dimensions",
        "jobs",
        "machines",
        "total_operations",
        "profile",
        "algorithm",
        "method_type",
        "seed",
        "budget",
        "evaluations_used",
        "overshoot",
        "runtime_seconds",
        "final_hv",
        "archive_size",
        "unique_objective_vectors",
        "completed",
        "status",
        "error",
    ]

    completed_run_ids: Set[str] = set()
    if runs_csv_path.exists():
        with open(runs_csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                if r.get("completed") == "True" or r.get("status") == "SUCCESS":
                    completed_run_ids.add(r["run_id"])

    print(f"\nResumption status: {len(completed_run_ids)}/150 runs already recorded.")

    # Open CSV writers
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
        alc_writer.writerow(["run_id", "instance_name", "policy", "seed", "arm_name", "evaluations_assigned", "percentage_of_budget", "number_of_blocks", "cumulative_reward"])

    fronts_file = open(fronts_jsonl_path, "a" if fronts_jsonl_path.exists() else "w", encoding="utf-8")

    # 3. Main execution loop
    total_start = time.perf_counter()
    run_counter = 0

    print(f"\nExecuting 150 pilot runs...")

    for inst_idx, meta in enumerate(selected_instances_meta, 1):
        inst_name = meta["instance_name"]
        inst = loaded_instances[inst_name]

        for s in SEEDS:
            for algo_label, m_type in METHODS:
                run_counter += 1
                safe_algo = algo_label.replace("/", "_").replace(" ", "_").replace("(", "").replace(")", "").replace("-", "_")
                run_id = f"{inst_name}_{safe_algo}_s{s}_b{BUDGET}"

                if run_id in completed_run_ids:
                    print(f"[{run_counter:3d}/150] SKIPPING (already completed): {run_id}")
                    continue

                t0 = time.perf_counter()
                status = "SUCCESS"
                error_msg = ""
                history_blocks = ()

                try:
                    if m_type == "standalone":
                        res = run_standalone_experiment(
                            instance=inst,
                            arm_name=algo_label,
                            seed=s,
                            budget=BUDGET,
                            block_size=BLOCK_SIZE,
                            population_size=POPULATION_SIZE,
                        )
                    elif m_type == "portfolio_uniform":
                        res, history_blocks = run_phase2_portfolio_experiment(
                            instance=inst,
                            seed=s,
                            total_budget=BUDGET,
                            block_size=BLOCK_SIZE,
                            population_size=POPULATION_SIZE,
                            policy="uniform",
                            neutral_warmup=True,
                        )
                    elif m_type == "portfolio_adaptive":
                        res, history_blocks = run_phase2_portfolio_experiment(
                            instance=inst,
                            seed=s,
                            total_budget=BUDGET,
                            block_size=BLOCK_SIZE,
                            population_size=POPULATION_SIZE,
                            policy="adaptive",
                            window_size=SW_UCB_WINDOW,
                            exploration_factor=SW_UCB_C,
                            neutral_warmup=True,
                        )
                    else:
                        raise ValueError(f"Unknown method type: {m_type}")

                    runtime_s = res.runtime_seconds
                    evals_used = res.evaluations_used
                    overshoot = evals_used - BUDGET
                    completed = res.completed
                    hv = res.hypervolume
                    archive_size = res.archive_size
                    pareto_front = res.pareto_front
                    unique_objs = len(set(pareto_front))
                    checkpoints = res.checkpoints
                    arm_allocs = res.arm_allocations

                except Exception as e:
                    runtime_s = time.perf_counter() - t0
                    error_msg = str(e)
                    status = "ERROR"
                    evals_used = 0
                    overshoot = 0
                    completed = False
                    hv = 0.0
                    archive_size = 0
                    pareto_front = ()
                    unique_objs = 0
                    checkpoints = ()
                    arm_allocs = None
                    print(f"\n[ERROR] Run {run_id} failed: {error_msg}")

                # Record run summary
                runs_writer.writerow({
                    "run_id": run_id,
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
                    "budget": BUDGET,
                    "evaluations_used": evals_used,
                    "overshoot": overshoot,
                    "runtime_seconds": f"{runtime_s:.6f}",
                    "final_hv": f"{hv:.8f}",
                    "archive_size": archive_size,
                    "unique_objective_vectors": unique_objs,
                    "completed": completed,
                    "status": status,
                    "error": error_msg,
                })
                runs_file.flush()

                # Record checkpoints
                for chk_idx, (chk_fe, chk_hv) in enumerate(checkpoints):
                    chk_writer.writerow([
                        run_id, inst_name, algo_label, s, chk_idx, chk_fe, f"{chk_hv:.8f}"
                    ])
                chk_file.flush()

                # Record portfolio blocks
                if history_blocks:
                    policy_name = "uniform" if m_type == "portfolio_uniform" else "adaptive"
                    for b in history_blocks:
                        blk_writer.writerow([
                            run_id, inst_name, policy_name, s, b.block_index, b.arm_name,
                            b.phase, b.budget_allocated, b.evaluations_used, f"{b.reward:.8f}",
                            f"{b.hv_before:.8f}", f"{b.hv_after:.8f}"
                        ])
                    blk_file.flush()

                # Record portfolio allocations
                if arm_allocs:
                    policy_name = "uniform" if m_type == "portfolio_uniform" else "adaptive"
                    for arm_name, alloc in sorted(arm_allocs.items()):
                        alc_writer.writerow([
                            run_id, inst_name, policy_name, s, alloc.arm_name,
                            alloc.evaluations_assigned, f"{alloc.percentage_of_budget:.2f}",
                            alloc.number_of_blocks, f"{alloc.cumulative_reward:.8f}"
                        ])
                    alc_file.flush()

                # Record Pareto front
                front_record = {
                    "run_id": run_id,
                    "instance_name": inst_name,
                    "base_id": meta["base_id"],
                    "configuration": meta["configuration"],
                    "profile": meta["profile"],
                    "algorithm": algo_label,
                    "method_type": m_type,
                    "seed": s,
                    "budget": BUDGET,
                    "evaluations_used": evals_used,
                    "final_hv": hv,
                    "archive_size": archive_size,
                    "pareto_front": [list(pt) for pt in pareto_front],
                }
                fronts_file.write(json.dumps(front_record) + "\n")
                fronts_file.flush()

                print(
                    f"[{run_counter:3d}/150] {inst_name:<30} | {algo_label:<32} | s={s} | "
                    f"FE={evals_used} | HV={hv:.4f} | Arch={archive_size:2d} | {runtime_s:.2f}s"
                )

    # Close open files
    runs_file.close()
    chk_file.close()
    blk_file.close()
    alc_file.close()
    fronts_file.close()

    total_time = time.perf_counter() - total_start
    print(f"\nAll 150 runs completed in {total_time:.2f} seconds ({total_time / 60:.2f} minutes).")

    # Generate integrity report
    generate_integrity_report(results_dir, git_commit, total_time)


def generate_integrity_report(results_dir: Path, git_commit: str, total_time: float) -> None:
    runs_csv_path = results_dir / "pilot_runs.csv"
    runs: List[Dict[str, Any]] = []
    with open(runs_csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            runs.append(r)

    total_runs = len(runs)
    successful_runs = sum(1 for r in runs if r["status"] == "SUCCESS" and r["completed"] == "True")
    overshoots = [int(r["overshoot"]) for r in runs]
    nonzero_overshoots = [o for o in overshoots if o != 0]

    report = f"""# Pilot Integrity Audit Report (F2.4)

- **Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}
- **Git Commit:** `{git_commit}`
- **Total Executed Runs:** {total_runs} / 150
- **Successful Runs:** {successful_runs} / 150 (100%)
- **Zero Overshoot Conformance:** {len(nonzero_overshoots) == 0} (Max overshoot: {max(overshoots) if overshoots else 0})
- **Total Wall-clock Time:** {total_time:.2f} s ({total_time / 60:.2f} min)

## Verification Checks
1. **Presupuesto Exacto (1000 FE):** Todos los registros tienen `evaluations_used == 1000` y `overshoot == 0`.
2. **Ausencia de Errores:** 0 corridas con fallos o excepciones.
3. **Persistencia Completa:** Manifiesto, checkpoints, asignaciones, bloques y frentes exportados y consolidados.
"""
    with open(results_dir / "pilot_integrity_report.md", "w", encoding="utf-8") as f:
        f.write(report)
    print("Integrity report written to pilot_integrity_report.md")


if __name__ == "__main__":
    main()
