"""Comprehensive Analysis and Visualization Script for Phase 2 Budget Diagnostic (F2.5.1).

Analyzes performance, scaling, and dynamics across 3 budget milestones:
- 1,000 FE
- 3,000 FE
- 5,000 FE

Across 5 optimization methods, answering questions A through E:
- A: Gap between Portfolio and Standalone algorithms across budgets.
- B: Evolution of DMAB vs Uniform across budgets.
- C: Arm differentiation in evaluation budget allocation.
- D: Proportion of zero-reward blocks across execution phases.
- E: Variations across dimensional configurations and problem profiles.

Generates CSV summaries and interpretive figures saved in
`results/expanded_portfolio_phase2/budget_diagnostic/plots/`.
"""

import csv
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root / "src"))

from mojssp.project_paths import HISTORICAL_ROOT, campaign_path
budget_dir = campaign_path("phase2") / "budget_diagnostic"
output_dir = None
plots_dir = None



def load_datasets() -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, List[Dict[str, Any]]]:
    runs_df = pd.read_csv(budget_dir / "budget_runs.csv")
    checkpoints_df = pd.read_csv(budget_dir / "budget_checkpoints.csv")
    blocks_df = pd.read_csv(budget_dir / "budget_portfolio_blocks.csv")
    allocs_df = pd.read_csv(budget_dir / "budget_arm_allocations.csv")

    fronts = []
    with open(budget_dir / "budget_fronts.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                fronts.append(json.loads(line))

    return runs_df, checkpoints_df, blocks_df, allocs_df, fronts


def analyze_performance_by_budget(runs_df: pd.DataFrame) -> pd.DataFrame:
    print("\n" + "=" * 80)
    print("1. AGGREGATE PERFORMANCE ACROSS BUDGET MILESTONES (1000, 3000, 5000 FE)")
    print("=" * 80)

    summary = runs_df.groupby(["budget", "algorithm"])["final_hv"].agg([
        ("mean", "mean"),
        ("std", "std"),
        ("median", "median"),
        ("min", "min"),
        ("max", "max"),
        ("count", "count"),
    ]).reset_index()

    summary["range"] = summary["max"] - summary["min"]
    print(summary.to_string(index=False))
    summary.to_csv(output_dir / "analysis_performance_by_budget.csv", index=False)
    return summary


def analyze_paired_differences_by_budget(runs_df: pd.DataFrame) -> pd.DataFrame:
    print("\n" + "=" * 80)
    print("2. PAIRED DIFFERENCES AND GAP TO VBS ACROSS BUDGETS")
    print("=" * 80)

    paired_records = []

    for b in [1000, 3000, 5000]:
        sub_df = runs_df[runs_df["budget"] == b]
        pivot = sub_df.pivot(index=["base_id", "instance_name", "seed"], columns="algorithm", values="final_hv")
        
        standalone_cols = ["MOEA/D", "NSGA-II", "SPEA2"]
        pivot["VBS"] = pivot[standalone_cols].max(axis=1)

        diff_adapt_unif = pivot["Adaptive Portfolio (DMAB)"] - pivot["Uniform Portfolio (Round-Robin)"]
        diff_adapt_vbs = pivot["Adaptive Portfolio (DMAB)"] - pivot["VBS"]
        diff_unif_vbs = pivot["Uniform Portfolio (Round-Robin)"] - pivot["VBS"]
        diff_adapt_moead = pivot["Adaptive Portfolio (DMAB)"] - pivot["MOEA/D"]
        diff_adapt_nsga2 = pivot["Adaptive Portfolio (DMAB)"] - pivot["NSGA-II"]
        diff_adapt_spea2 = pivot["Adaptive Portfolio (DMAB)"] - pivot["SPEA2"]

        contrasts = [
            ("Adaptive vs Uniform", diff_adapt_unif),
            ("Adaptive vs VBS", diff_adapt_vbs),
            ("Uniform vs VBS", diff_unif_vbs),
            ("Adaptive vs MOEA/D", diff_adapt_moead),
            ("Adaptive vs NSGA-II", diff_adapt_nsga2),
            ("Adaptive vs SPEA2", diff_adapt_spea2),
        ]

        for label, diffs in contrasts:
            wins = (diffs > 1e-6).sum()
            ties = (diffs.abs() <= 1e-6).sum()
            losses = (diffs < -1e-6).sum()
            m_diff = diffs.mean()
            s_diff = diffs.std()
            med_diff = diffs.median()
            cohen_d = m_diff / s_diff if s_diff > 0 else 0.0

            try:
                nonzero = diffs[diffs.abs() > 1e-6]
                if len(nonzero) > 0:
                    _, p_val = stats.wilcoxon(diffs)
                else:
                    p_val = 1.0
            except Exception:
                p_val = np.nan

            paired_records.append({
                "Budget": b,
                "Comparison": label,
                "Mean_Diff": m_diff,
                "Std_Diff": s_diff,
                "Median_Diff": med_diff,
                "Wins": wins,
                "Ties": ties,
                "Losses": losses,
                "Cohen_d": cohen_d,
                "Wilcoxon_p": p_val,
            })

    paired_df = pd.DataFrame(paired_records)
    print(paired_df.to_string(index=False))
    paired_df.to_csv(output_dir / "analysis_paired_differences_by_budget.csv", index=False)
    return paired_df


def analyze_allocations_and_differentiation(allocs_df: pd.DataFrame) -> pd.DataFrame:
    print("\n" + "=" * 80)
    print("3. ARM ALLOCATIONS AND DIFFERENTIATION ACROSS BUDGETS")
    print("=" * 80)

    adapt_allocs = allocs_df[allocs_df["policy"] == "adaptive"]
    summary = adapt_allocs.groupby(["budget_milestone", "arm_name"])["evaluations_assigned"].agg([
        ("mean_evals", "mean"),
        ("std_evals", "std"),
        ("min_evals", "min"),
        ("max_evals", "max"),
    ]).reset_index()

    summary["pct_of_budget"] = summary["mean_evals"] / summary["budget_milestone"] * 100
    print(summary.to_string(index=False))
    summary.to_csv(output_dir / "analysis_arm_allocations_by_budget.csv", index=False)
    return summary


def analyze_reward_dynamics_and_zeros(blocks_df: pd.DataFrame) -> pd.DataFrame:
    print("\n" + "=" * 80)
    print("4. REWARD DYNAMICS AND ZERO-REWARD FREQUENCY ACROSS PHASES")
    print("=" * 80)

    adapt_blocks = blocks_df[blocks_df["policy"] == "adaptive"].copy()

    # Define execution intervals:
    # Warmup + Probe (0-5: 300 FE)
    # Early Adaptive (6-19: 300 - 1000 FE)
    # Mid Adaptive (20-59: 1000 - 3000 FE)
    # Late Adaptive (60-99: 3000 - 5000 FE)
    def assign_phase(block_idx: int) -> str:
        if block_idx < 3:
            return "1_warmup (0-150 FE)"
        elif block_idx < 6:
            return "2_probe (150-300 FE)"
        elif block_idx < 20:
            return "3_early (300-1000 FE)"
        elif block_idx < 60:
            return "4_mid (1000-3000 FE)"
        else:
            return "5_late (3000-5000 FE)"

    adapt_blocks["interval"] = adapt_blocks["block_index"].apply(assign_phase)
    adapt_blocks["is_zero"] = adapt_blocks["reward"] <= 1e-8

    zero_summary = adapt_blocks.groupby("interval").agg(
        total_blocks=("reward", "count"),
        zero_blocks=("is_zero", "sum"),
        mean_reward=("reward", "mean"),
        median_reward=("reward", "median"),
        std_reward=("reward", "std"),
    ).reset_index()

    zero_summary["zero_pct"] = zero_summary["zero_blocks"] / zero_summary["total_blocks"] * 100
    print(zero_summary.to_string(index=False))
    zero_summary.to_csv(output_dir / "analysis_zero_reward_dynamics.csv", index=False)
    return zero_summary


def analyze_by_configuration_and_profile(runs_df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    print("\n" + "=" * 80)
    print("5. PERFORMANCE BY CONFIGURATION AND PROFILE ACROSS BUDGETS")
    print("=" * 80)

    cfg_df = runs_df.groupby(["budget", "configuration", "algorithm"])["final_hv"].mean().unstack(level="algorithm")
    print("Mean HV by Configuration and Budget:")
    print(cfg_df.to_string())
    cfg_df.to_csv(output_dir / "analysis_by_configuration_and_budget.csv")

    prof_df = runs_df.groupby(["budget", "profile", "algorithm"])["final_hv"].mean().unstack(level="algorithm")
    print("\nMean HV by Profile and Budget:")
    print(prof_df.to_string())
    prof_df.to_csv(output_dir / "analysis_by_profile_and_budget.csv")

    return cfg_df, prof_df


def generate_plots(runs_df: pd.DataFrame, checkpoints_df: pd.DataFrame, allocs_df: pd.DataFrame, blocks_df: pd.DataFrame) -> None:
    print("\n" + "=" * 80)
    print("6. GENERATING INTERPRETIVE FIGURES FOR BUDGET DIAGNOSTIC")
    print("=" * 80)

    methods_order = [
        "MOEA/D",
        "NSGA-II",
        "SPEA2",
        "Uniform Portfolio (Round-Robin)",
        "Adaptive Portfolio (DMAB)",
    ]
    colors = {
        "MOEA/D": "#4C72B0",
        "NSGA-II": "#55A868",
        "SPEA2": "#C44E52",
        "Uniform Portfolio (Round-Robin)": "#8172B3",
        "Adaptive Portfolio (DMAB)": "#D95F02",
    }

    # Plot 1: Mean HV Progression across Budgets (1000, 3000, 5000 FE)
    fig, ax = plt.subplots(figsize=(10, 6))
    perf = runs_df.groupby(["budget", "algorithm"])["final_hv"].mean().unstack()
    for m in methods_order:
        ax.plot([1000, 3000, 5000], perf[m], marker="o", linewidth=2.2, label=m, color=colors[m])

    ax.set_xticks([1000, 3000, 5000])
    ax.set_xlabel("Evaluation Budget (FE)", fontsize=11, fontweight="bold")
    ax.set_ylabel("Mean Hypervolume (HV)", fontsize=11, fontweight="bold")
    ax.set_title("Scaling of Hypervolume across Budgets (1000, 3000, 5000 FE)", fontsize=12, fontweight="bold")
    ax.legend(loc="lower right")
    ax.grid(True, linestyle="--", alpha=0.5)
    plt.tight_layout()
    p1 = plots_dir / "01_budget_hv_progression_by_method.png"
    plt.savefig(p1, dpi=300)
    plt.close()
    print(f"Saved: {p1.name}")

    # Plot 2: Paired Difference (Adaptive - Uniform) across Budgets
    fig, ax = plt.subplots(figsize=(10, 6))
    diff_records = []
    for b in [1000, 3000, 5000]:
        sub = runs_df[runs_df["budget"] == b].pivot(index=["instance_name", "seed"], columns="algorithm", values="final_hv")
        d = sub["Adaptive Portfolio (DMAB)"] - sub["Uniform Portfolio (Round-Robin)"]
        for val in d:
            diff_records.append({"budget": str(b), "diff": val})
    
    diff_df = pd.DataFrame(diff_records)
    box_data = [diff_df[diff_df["budget"] == str(b)]["diff"].values for b in [1000, 3000, 5000]]
    bp = ax.boxplot(box_data, tick_labels=["1,000 FE", "3,000 FE", "5,000 FE"], patch_artist=True)
    for patch in bp['boxes']:
        patch.set_facecolor("#8da0cb")
        patch.set_alpha(0.7)

    ax.axhline(0, color="black", linestyle="--", linewidth=1.2)
    ax.set_xlabel("Evaluation Budget", fontsize=11, fontweight="bold")
    ax.set_ylabel("Paired Difference ΔHV (Adaptive - Uniform)", fontsize=11, fontweight="bold")
    ax.set_title("Evolution of Paired Advantage: Adaptive DMAB vs Uniform Portfolio", fontsize=12, fontweight="bold")
    ax.grid(True, linestyle="--", alpha=0.5)
    plt.tight_layout()
    p2 = plots_dir / "02_budget_paired_diff_evolution.png"
    plt.savefig(p2, dpi=300)
    plt.close()
    print(f"Saved: {p2.name}")

    # Plot 3: Performance Gap to Virtual Best Solver (VBS)
    fig, ax = plt.subplots(figsize=(10, 6))
    gap_records = []
    for b in [1000, 3000, 5000]:
        sub = runs_df[runs_df["budget"] == b].pivot(index=["instance_name", "seed"], columns="algorithm", values="final_hv")
        vbs = sub[["MOEA/D", "NSGA-II", "SPEA2"]].max(axis=1)
        for m in methods_order:
            gap = sub[m] - vbs
            gap_records.append({"budget": b, "method": m, "gap": gap.mean()})

    gap_df = pd.DataFrame(gap_records)
    gap_pivot = gap_df.pivot(index="budget", columns="method", values="gap")
    for m in methods_order:
        ax.plot([1000, 3000, 5000], gap_pivot[m], marker="s", linewidth=2.0, label=m, color=colors[m])

    ax.axhline(0, color="red", linestyle=":", label="VBS (Oracle Benchmark)")
    ax.set_xticks([1000, 3000, 5000])
    ax.set_xlabel("Evaluation Budget (FE)", fontsize=11, fontweight="bold")
    ax.set_ylabel("Mean Gap to VBS (HV - HV_VBS)", fontsize=11, fontweight="bold")
    ax.set_title("Evolution of Gap to Virtual Best Solver (Oracle) across Budgets", fontsize=12, fontweight="bold")
    ax.legend(loc="lower right")
    ax.grid(True, linestyle="--", alpha=0.5)
    plt.tight_layout()
    p3 = plots_dir / "03_budget_gap_to_vbs_evolution.png"
    plt.savefig(p3, dpi=300)
    plt.close()
    print(f"Saved: {p3.name}")

    # Plot 4: Arm Allocation Differentiation in DMAB across Budgets
    fig, ax = plt.subplots(figsize=(10, 6))
    adapt_allocs = allocs_df[allocs_df["policy"] == "adaptive"]
    alloc_means = adapt_allocs.groupby(["budget_milestone", "arm_name"])["evaluations_assigned"].mean().unstack()

    x = np.arange(len(alloc_means.index))
    width = 0.25
    arms = ["MOEA/D", "NSGA-II", "SPEA2"]
    arm_colors = ["#4C72B0", "#55A868", "#C44E52"]
    for i, (arm, color) in enumerate(zip(arms, arm_colors)):
        ax.bar(x + (i - 1) * width, alloc_means[arm], width=width, label=arm, color=color, alpha=0.85, edgecolor="black")

    ax.set_xticks(x)
    ax.set_xticklabels([f"{b:,} FE" for b in alloc_means.index], fontsize=11)
    ax.set_xlabel("Evaluation Budget Milestone", fontsize=11, fontweight="bold")
    ax.set_ylabel("Mean Evaluations Allocated (FE)", fontsize=11, fontweight="bold")
    ax.set_title("Arm Allocation Specialization in Adaptive DMAB across Budgets", fontsize=12, fontweight="bold")
    ax.legend(title="Algorithm Arm", loc="upper left")
    ax.grid(True, linestyle="--", alpha=0.5)
    plt.tight_layout()
    p4 = plots_dir / "04_budget_arm_allocation_evolution.png"
    plt.savefig(p4, dpi=300)
    plt.close()
    print(f"Saved: {p4.name}")

    # Plot 5: Zero-Reward Frequency Progression
    fig, ax = plt.subplots(figsize=(10, 6))
    adapt_blocks = blocks_df[blocks_df["policy"] == "adaptive"].copy()
    
    # Compute zero reward rate in rolling bins of 10 blocks
    adapt_blocks["block_bin"] = adapt_blocks["block_index"] // 10
    zero_rates = adapt_blocks.groupby("block_bin").apply(lambda g: (g["reward"] <= 1e-8).mean() * 100)

    bin_centers = [bin_idx * 10 * 50 + 250 for bin_idx in zero_rates.index]
    ax.plot(bin_centers, zero_rates.values, marker="o", color="#e41a1c", linewidth=2.2)
    ax.set_xlabel("Evaluations Elapsed (FE)", fontsize=11, fontweight="bold")
    ax.set_ylabel("Zero-Reward Block Percentage (%)", fontsize=11, fontweight="bold")
    ax.set_title("Progression of Zero-Reward Frequency during Search (Blocks of 50 FE)", fontsize=12, fontweight="bold")
    ax.axvline(300, color="gray", linestyle=":", label="Startup End (300 FE)")
    ax.legend(loc="lower right")
    ax.grid(True, linestyle="--", alpha=0.5)
    plt.tight_layout()
    p5 = plots_dir / "05_budget_zero_reward_fraction.png"
    plt.savefig(p5, dpi=300)
    plt.close()
    print(f"Saved: {p5.name}")


def main() -> None:
    global output_dir, plots_dir
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    if output_dir.exists():
        parser.error('output directory already exists; choose a new directory')
    if output_dir.is_relative_to(HISTORICAL_ROOT):
        parser.error('output must be outside results/historical')
    plots_dir = output_dir / 'plots'
    plots_dir.mkdir(parents=True, exist_ok=True)
    runs_df, checkpoints_df, blocks_df, allocs_df, fronts = load_datasets()
    analyze_performance_by_budget(runs_df)
    analyze_paired_differences_by_budget(runs_df)
    analyze_allocations_and_differentiation(allocs_df)
    analyze_reward_dynamics_and_zeros(blocks_df)
    analyze_by_configuration_and_profile(runs_df)
    generate_plots(runs_df, checkpoints_df, allocs_df, blocks_df)
    print("\n" + "=" * 80)
    print("BUDGET DIAGNOSTIC ANALYSIS AND FIGURES COMPLETED SUCCESSFULLY.")
    print("=" * 80)


if __name__ == "__main__":
    main()

