"""Calibration batch execution script for Phase 8.3.

Executes:
- Primary calibration: 12 experimental instances x 4 methods x 3 seeds x 500 FE = 144 runs.
- Extended calibration: 3 representative instances x 4 methods x 3 seeds x 1000 FE = 36 runs.
Total: 180 runs.

Exports raw datasets to results/raw/, summaries to results/summaries/,
and Pareto front coordinates to results/fronts/.
"""

import math
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mojssp import (
    BlockExecutionRecord,
    Instance,
    RunResult,
    export_results_to_csv,
    load_dzn,
    run_portfolio_experiment,
    run_standalone_experiment,
)


def run_calibration_f83():
    data_dir = Path("data/experimental")
    results_dir = Path("results")

    # The 12 experimental instances from F8.2.2
    experimental_files = [
        "5_10_2-5_1.dzn",
        "10_10_2-5_1.dzn",
        "15_10_2-5_1.dzn",
        "20_10_2-5_1.dzn",
        "15_15_2-5_1.dzn",
        "20_20_2-5_1.dzn",
        "30_20_2-5_1.dzn",
        "40_20_2-5_1.dzn",
        "30_30_2-5_1.dzn",
        "50_25_2-5_1.dzn",
        "40_40_2-5_1.dzn",
        "50_50_2-5_1.dzn",
    ]

    # 3 representative instances for extended 1000 FE condition
    extended_files = [
        "10_10_2-5_1.dzn",  # Small (N=100)
        "20_20_2-5_1.dzn",  # Medium (N=400)
        "30_30_2-5_1.dzn",  # Large (N=900)
    ]

    seeds = [42, 100, 200]
    standalone_arms = ["NSGA-II", "MOPSO", "NSGA-II+LS"]
    block_size = 50
    pop_size = 30

    all_runs = []
    all_blocks = []

    print("=================================================================")
    print("PHASE 8.3 — CALIBRATION BATCH EXECUTION")
    print("=================================================================")
    print(f"Experimental instances: {len(experimental_files)}")
    print(f"Seeds: {seeds}")
    print(f"Block size: {block_size} FE")
    print(f"Population/Swarm size: {pop_size}")
    print("-----------------------------------------------------------------")

    start_total_time = time.time()

    # 1. Primary Condition: 500 FE across all 12 instances
    print("\n--- 1. Executing Primary Condition (500 FE) ---")
    for inst_idx, fname in enumerate(experimental_files, 1):
        fpath = data_dir / fname
        inst = load_dzn(fpath, validate=True)
        print(f"[{inst_idx:02d}/12] Instance: {inst.name:<18} (N={inst.total_operations:4d} ops, {inst.num_jobs}x{inst.num_machines})")

        for seed in seeds:
            # A. Standalone baselines (NSGA-II, MOPSO, NSGA-II+LS)
            for arm_name in standalone_arms:
                res = run_standalone_experiment(
                    instance=inst,
                    arm_name=arm_name,
                    seed=seed,
                    budget=500,
                    block_size=block_size,
                    population_size=pop_size,
                )
                all_runs.append(res)

            # B. Adaptive Portfolio
            port_res, history = run_portfolio_experiment(
                instance=inst,
                seed=seed,
                total_budget=500,
                block_size=block_size,
                population_size=pop_size,
            )
            all_runs.append(port_res)
            for b in history:
                all_blocks.append((port_res.run_id, b))

    # 2. Extended Condition: 1000 FE on 3 representative instances
    print("\n--- 2. Executing Extended Condition (1000 FE on 3 instances) ---")
    for inst_idx, fname in enumerate(extended_files, 1):
        fpath = data_dir / fname
        inst = load_dzn(fpath, validate=True)
        print(f"[{inst_idx:02d}/03] Extended Instance: {inst.name:<18} (1000 FE)")

        for seed in seeds:
            # Standalone baselines
            for arm_name in standalone_arms:
                res = run_standalone_experiment(
                    instance=inst,
                    arm_name=arm_name,
                    seed=seed,
                    budget=1000,
                    block_size=block_size,
                    population_size=pop_size,
                )
                all_runs.append(res)

            # Portfolio
            port_res, history = run_portfolio_experiment(
                instance=inst,
                seed=seed,
                total_budget=1000,
                block_size=block_size,
                population_size=pop_size,
            )
            all_runs.append(port_res)
            for b in history:
                all_blocks.append((port_res.run_id, b))

    elapsed = time.time() - start_total_time
    print("-----------------------------------------------------------------")
    print(f"Calibration completed in {elapsed:.2f} seconds.")
    print(f"Total runs executed: {len(all_runs)} (Expected: 144 + 36 = 180)")
    print(f"Total portfolio blocks executed: {len(all_blocks)}")

    # 3. Export all results to CSV and JSON
    print("\n--- 3. Exporting Results to CSV and Fronts ---")
    export_results_to_csv(
        runs=all_runs,
        portfolio_blocks=all_blocks,
        results_dir=results_dir,
    )
    print("Results exported successfully:")
    print("  results/raw/runs.csv")
    print("  results/raw/portfolio_blocks.csv")
    print("  results/raw/checkpoints.csv")
    print("  results/summaries/arm_allocations.csv")
    print(f"  results/fronts/ ({len(all_runs)} JSON files)")

if __name__ == "__main__":
    run_calibration_f83()
