"""Comprehensive Analysis and Visualization Script for Phase 2 Pilot (F2.4).

Processes pilot datasets from `results/expanded_portfolio_phase2/pilot/`:
- Computes aggregate metrics (mean, median, std, min, max, range) by method, configuration, and profile.
- Computes paired differences (Adaptive vs Uniform, Adaptive vs Standalone, Adaptive vs VBS).
- Analyzes DMAB dynamic selection, FE allocations, rewards, and arm contributions.
- Analyzes Pareto front complementarity and provenance of solutions in the Global Archive.
- Generates high-quality interpretive figures saved in `results/expanded_portfolio_phase2/pilot/plots/`.
- Exports summary CSV tables for thesis and paper documentation.
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

from mojssp.pareto_archive import ParetoArchive
from mojssp.dominance import dominates

from mojssp.project_paths import HISTORICAL_ROOT, campaign_path
pilot_dir = campaign_path("phase2") / "pilot"
output_dir = None
plots_dir = None



def load_datasets() -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, List[Dict[str, Any]]]:
    runs_df = pd.read_csv(pilot_dir / "pilot_runs.csv")
    checkpoints_df = pd.read_csv(pilot_dir / "pilot_checkpoints.csv")
    blocks_df = pd.read_csv(pilot_dir / "pilot_portfolio_blocks.csv")
    allocs_df = pd.read_csv(pilot_dir / "pilot_arm_allocations.csv")

    fronts = []
    with open(pilot_dir / "pilot_fronts.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                fronts.append(json.loads(line))

    return runs_df, checkpoints_df, blocks_df, allocs_df, fronts


def analyze_performance(runs_df: pd.DataFrame) -> Dict[str, Any]:
    print("\n" + "=" * 80)
    print("1. AGGREGATE PERFORMANCE BY METHOD")
    print("=" * 80)

    summary_by_method = runs_df.groupby("algorithm")["final_hv"].agg([
        ("mean", "mean"),
        ("std", "std"),
        ("median", "median"),
        ("min", "min"),
        ("max", "max"),
        ("count", "count"),
    ])
    summary_by_method["range"] = summary_by_method["max"] - summary_by_method["min"]
    summary_by_method = summary_by_method.sort_values(by="mean", ascending=False)
    print(summary_by_method.to_string())

    summary_by_method.to_csv(output_dir / "analysis_method_summary.csv")

    print("\n" + "=" * 80)
    print("2. PERFORMANCE BY CONFIGURATION AND PROFILE")
    print("=" * 80)
    cfg_summary = runs_df.groupby(["configuration", "algorithm"])["final_hv"].agg(["mean", "std", "median"])
    print(cfg_summary.to_string())
    cfg_summary.to_csv(output_dir / "analysis_configuration_summary.csv")

    prof_summary = runs_df.groupby(["profile", "algorithm"])["final_hv"].agg(["mean", "std", "median"])
    print("\nBy Profile:")
    print(prof_summary.to_string())
    prof_summary.to_csv(output_dir / "analysis_profile_summary.csv")

    return {"by_method": summary_by_method, "by_cfg": cfg_summary, "by_prof": prof_summary}


def analyze_paired_comparisons(runs_df: pd.DataFrame) -> pd.DataFrame:
    print("\n" + "=" * 80)
    print("3. PAIRED COMPARISONS (ACROSS 30 INSTANCE-SEED PAIRS)")
    print("=" * 80)

    # Pivot table: rows = (instance_name, seed), cols = algorithm, value = final_hv
    pivot_hv = runs_df.pivot(index=["instance_name", "seed"], columns="algorithm", values="final_hv")
    
    # Calculate Virtual Best Solver (VBS) of standalone algorithms
    standalone_cols = ["MOEA/D", "NSGA-II", "SPEA2"]
    pivot_hv["VBS_Standalone"] = pivot_hv[standalone_cols].max(axis=1)

    diff_adaptive_uniform = pivot_hv["Adaptive Portfolio (DMAB)"] - pivot_hv["Uniform Portfolio (Round-Robin)"]
    diff_adaptive_vbs = pivot_hv["Adaptive Portfolio (DMAB)"] - pivot_hv["VBS_Standalone"]
    diff_uniform_vbs = pivot_hv["Uniform Portfolio (Round-Robin)"] - pivot_hv["VBS_Standalone"]

    diff_adaptive_moead = pivot_hv["Adaptive Portfolio (DMAB)"] - pivot_hv["MOEA/D"]
    diff_adaptive_nsga2 = pivot_hv["Adaptive Portfolio (DMAB)"] - pivot_hv["NSGA-II"]
    diff_adaptive_spea2 = pivot_hv["Adaptive Portfolio (DMAB)"] - pivot_hv["SPEA2"]

    paired_stats = []

    pairs = [
        ("Adaptive vs Uniform", diff_adaptive_uniform),
        ("Adaptive vs VBS", diff_adaptive_vbs),
        ("Uniform vs VBS", diff_uniform_vbs),
        ("Adaptive vs MOEA/D", diff_adaptive_moead),
        ("Adaptive vs NSGA-II", diff_adaptive_nsga2),
        ("Adaptive vs SPEA2", diff_adaptive_spea2),
    ]

    for label, diffs in pairs:
        wins = (diffs > 1e-6).sum()
        ties = (diffs.abs() <= 1e-6).sum()
        losses = (diffs < -1e-6).sum()
        mean_d = diffs.mean()
        std_d = diffs.std()
        med_d = diffs.median()
        # Wilcoxon signed rank test if not all differences are zero
        nonzero_diffs = diffs[diffs.abs() > 1e-6]
        if len(nonzero_diffs) > 0:
            try:
                w_stat, p_val = stats.wilcoxon(diffs)
            except Exception:
                w_stat, p_val = np.nan, np.nan
        else:
            w_stat, p_val = np.nan, 1.0

        # Cohen's d
        cohen_d = mean_d / std_d if std_d > 0 else 0.0

        paired_stats.append({
            "Comparison": label,
            "Mean_Diff": mean_d,
            "Std_Diff": std_d,
            "Median_Diff": med_d,
            "Wins": wins,
            "Ties": ties,
            "Losses": losses,
            "Cohen_d": cohen_d,
            "Wilcoxon_p": p_val,
        })

    paired_df = pd.DataFrame(paired_stats)
    print(paired_df.to_string(index=False))
    paired_df.to_csv(output_dir / "analysis_paired_comparisons.csv", index=False)

    # Detailed per-instance differences
    pivot_hv["Diff_Adaptive_minus_Uniform"] = diff_adaptive_uniform
    pivot_hv["Diff_Adaptive_minus_VBS"] = diff_adaptive_vbs
    pivot_hv.to_csv(output_dir / "analysis_paired_instances_detail.csv")

    return paired_df


def analyze_adaptive_behavior(allocs_df: pd.DataFrame, blocks_df: pd.DataFrame) -> None:
    print("\n" + "=" * 80)
    print("4. ADAPTIVE ALLOCATION AND DMAB BEHAVIOR")
    print("=" * 80)

    # Filter adaptive portfolio
    adaptive_allocs = allocs_df[allocs_df["policy"] == "adaptive"]
    uniform_allocs = allocs_df[allocs_df["policy"] == "uniform"]

    print("Average Evaluations Assigned by Policy:")
    print("ADAPTIVE:")
    mean_adapt = adaptive_allocs.groupby("arm_name")["evaluations_assigned"].agg(["mean", "std", "min", "max"])
    print(mean_adapt.to_string())

    print("\nUNIFORM:")
    mean_unif = uniform_allocs.groupby("arm_name")["evaluations_assigned"].agg(["mean", "std", "min", "max"])
    print(mean_unif.to_string())

    mean_adapt.to_csv(output_dir / "analysis_adaptive_arm_allocations.csv")

    # Analyze blocks after 300 FE (block_index >= 6)
    post_startup_blocks = blocks_df[(blocks_df["policy"] == "adaptive") & (blocks_df["block_index"] >= 6)]
    arm_counts_post_startup = post_startup_blocks.groupby("arm_selected").size()
    total_post_startup = len(post_startup_blocks)
    print(f"\nPost-startup blocks (Blocks 6-19, total {total_post_startup}):")
    for arm, count in arm_counts_post_startup.items():
        print(f"  {arm}: {count} blocks ({count / total_post_startup * 100:.2f}%)")

    # Rewards by arm
    print("\nMean Rewards by Arm in Adaptive Policy:")
    rew_summary = blocks_df[blocks_df["policy"] == "adaptive"].groupby(["arm_selected", "phase"])["reward"].agg(["mean", "std", "count"])
    print(rew_summary.to_string())
    rew_summary.to_csv(output_dir / "analysis_arm_rewards_by_phase.csv")


def analyze_complementarity(fronts: List[Dict[str, Any]]) -> pd.DataFrame:
    print("\n" + "=" * 80)
    print("5. PARETO FRONT COMPLEMENTARITY ANALYSIS")
    print("=" * 80)

    # Group fronts by (instance_name, seed)
    fronts_by_pair: Dict[Tuple[str, int], Dict[str, List[Tuple[float, float, float]]]] = {}
    for f in fronts:
        k = (f["instance_name"], f["seed"])
        if k not in fronts_by_pair:
            fronts_by_pair[k] = {}
        # Convert list of lists to list of tuples
        pts = [tuple(p) for p in f["pareto_front"]]
        fronts_by_pair[k][f["algorithm"]] = pts

    comp_records = []

    for (inst_name, s), f_dict in fronts_by_pair.items():
        # Get standalone fronts
        m_pts = set(f_dict.get("MOEA/D", []))
        n_pts = set(f_dict.get("NSGA-II", []))
        s_pts = set(f_dict.get("SPEA2", []))

        # Union of standalone solutions
        union_all = m_pts | n_pts | s_pts

        # Filter strictly non-dominated in the union
        union_nd = []
        for p in union_all:
            if not any(dominates(q, p) for q in union_all if q != p):
                union_nd.append(p)
        union_nd_set = set(union_nd)

        # Standalone contributions to union
        m_contrib = len(union_nd_set & m_pts)
        n_contrib = len(union_nd_set & n_pts)
        s_contrib = len(union_nd_set & s_pts)

        # Portfolio fronts
        unif_pts = set(f_dict.get("Uniform Portfolio (Round-Robin)", []))
        adapt_pts = set(f_dict.get("Adaptive Portfolio (DMAB)", []))

        # Check how many solutions in Adaptive Portfolio came from the standalone sets
        adapt_in_union = len(adapt_pts & union_nd_set)

        comp_records.append({
            "instance_name": inst_name,
            "seed": s,
            "union_nd_size": len(union_nd_set),
            "moead_in_union": m_contrib,
            "nsga2_in_union": n_contrib,
            "spea2_in_union": s_contrib,
            "adaptive_front_size": len(adapt_pts),
            "uniform_front_size": len(unif_pts),
            "adaptive_overlap_with_union": adapt_in_union,
        })

    comp_df = pd.DataFrame(comp_records)
    mean_comp = comp_df.mean(numeric_only=True)
    print("Average Complementarity Metrics across 30 pairs:")
    print(mean_comp.to_string())
    comp_df.to_csv(output_dir / "analysis_complementarity_summary.csv", index=False)
    return comp_df


def generate_plots(runs_df: pd.DataFrame, checkpoints_df: pd.DataFrame, allocs_df: pd.DataFrame) -> None:
    print("\n" + "=" * 80)
    print("6. GENERATING INTERPRETIVE VISUALIZATIONS")
    print("=" * 80)

    # Plot 1: Boxplot of HV by Method
    fig, ax = plt.subplots(figsize=(10, 6))
    methods_order = [
        "MOEA/D",
        "NSGA-II",
        "SPEA2",
        "Uniform Portfolio (Round-Robin)",
        "Adaptive Portfolio (DMAB)",
    ]
    data_by_method = [runs_df[runs_df["algorithm"] == m]["final_hv"].values for m in methods_order]
    
    bp = ax.boxplot(data_by_method, labels=[m.replace(" Portfolio", "").replace(" (Round-Robin)", "").replace(" (DMAB)", "") for m in methods_order], patch_artist=True)
    colors = ["#4C72B0", "#55A868", "#C44E52", "#8172B3", "#CCB974"]
    for patch, color in zip(bp['boxes'], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)

    ax.set_ylabel("Hypervolume (HV)", fontsize=12)
    ax.set_title("Distribution of Final Hypervolume by Optimization Method (1000 FE, N=30)", fontsize=13, fontweight="bold")
    ax.grid(True, linestyle="--", alpha=0.5)
    plt.tight_layout()
    plot1_path = plots_dir / "01_pilot_hv_by_method.png"
    plt.savefig(plot1_path, dpi=300)
    plt.close()
    print(f"Saved: {plot1_path.name}")

    # Plot 2: Paired Differences (Adaptive vs Uniform) by Instance
    pivot_hv = runs_df.pivot(index=["instance_name", "seed"], columns="algorithm", values="final_hv")
    diff_series = pivot_hv["Adaptive Portfolio (DMAB)"] - pivot_hv["Uniform Portfolio (Round-Robin)"]
    diff_df = diff_series.reset_index(name="HV_Diff")

    fig, ax = plt.subplots(figsize=(12, 6))
    instances_order = sorted(diff_df["instance_name"].unique())
    inst_means = [diff_df[diff_df["instance_name"] == inst]["HV_Diff"].mean() for inst in instances_order]
    inst_stds = [diff_df[diff_df["instance_name"] == inst]["HV_Diff"].std() for inst in instances_order]

    x = np.arange(len(instances_order))
    bar_colors = ["#2ca02c" if m >= 0 else "#d62728" for m in inst_means]
    ax.bar(x, inst_means, yerr=inst_stds, capsize=4, color=bar_colors, alpha=0.8, edgecolor="black")
    ax.axhline(0, color="black", linestyle="-", linewidth=1)
    ax.set_xticks(x)
    ax.set_xticklabels([inst.replace("base_", "") for inst in instances_order], rotation=35, ha="right", fontsize=9)
    ax.set_ylabel("Paired Difference ΔHV (Adaptive - Uniform)", fontsize=11)
    ax.set_title("Paired Difference in Hypervolume: Adaptive DMAB vs Uniform Portfolio (Mean ± Std)", fontsize=12, fontweight="bold")
    ax.grid(True, linestyle="--", alpha=0.5)
    plt.tight_layout()
    plot2_path = plots_dir / "02_pilot_paired_diff_adaptive_vs_uniform.png"
    plt.savefig(plot2_path, dpi=300)
    plt.close()
    print(f"Saved: {plot2_path.name}")

    # Plot 3: Arm Allocations in Adaptive Portfolio
    adapt_allocs = allocs_df[allocs_df["policy"] == "adaptive"]
    alloc_summary = adapt_allocs.groupby(["instance_name", "arm_name"])["evaluations_assigned"].mean().unstack()

    fig, ax = plt.subplots(figsize=(12, 6))
    inst_labels = [idx.replace("base_", "") for idx in alloc_summary.index]
    alloc_summary.plot(kind="bar", stacked=True, ax=ax, colormap="viridis", edgecolor="black", alpha=0.85)
    ax.set_ylabel("Allocated Evaluations (FE out of 1000)", fontsize=11)
    ax.set_xlabel("Problem Instance", fontsize=11)
    ax.set_xticklabels(inst_labels, rotation=35, ha="right", fontsize=9)
    ax.set_title("Evaluation Budget Distribution by Arm in Adaptive DMAB Portfolio (Mean across seeds)", fontsize=12, fontweight="bold")
    ax.axhline(300, color="red", linestyle="--", label="Startup Budget (300 FE: 100/arm)")
    ax.legend(title="Algorithm Arm", loc="upper right")
    ax.grid(True, linestyle="--", alpha=0.5)
    plt.tight_layout()
    plot3_path = plots_dir / "03_pilot_dmab_arm_allocation.png"
    plt.savefig(plot3_path, dpi=300)
    plt.close()
    print(f"Saved: {plot3_path.name}")

    # Plot 4: Convergence Trajectories (Checkpoints)
    fig, ax = plt.subplots(figsize=(10, 6))
    chk_summary = checkpoints_df.groupby(["algorithm", "evaluations_used"])["hypervolume"].mean().unstack(level=0)
    for col in methods_order:
        if col in chk_summary.columns:
            ax.plot(chk_summary.index, chk_summary[col], marker="o", markersize=3, label=col, linewidth=1.8)

    ax.set_xlabel("Evaluations (FE)", fontsize=11)
    ax.set_ylabel("Mean Hypervolume (HV)", fontsize=11)
    ax.set_title("Convergence Curves: Mean Hypervolume Progression over 1000 FE", fontsize=12, fontweight="bold")
    ax.axvline(300, color="gray", linestyle=":", label="Startup Transition (300 FE)")
    ax.legend(loc="lower right")
    ax.grid(True, linestyle="--", alpha=0.5)
    plt.tight_layout()
    plot4_path = plots_dir / "04_pilot_convergence_curves.png"
    plt.savefig(plot4_path, dpi=300)
    plt.close()
    print(f"Saved: {plot4_path.name}")


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
    analyze_performance(runs_df)
    analyze_paired_comparisons(runs_df)
    analyze_adaptive_behavior(allocs_df, blocks_df)
    analyze_complementarity(fronts)
    generate_plots(runs_df, checkpoints_df, allocs_df)
    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE. ALL ARTIFACTS AND PLOTS GENERATED SUCCESSFULLY.")
    print("=" * 80)


if __name__ == "__main__":
    main()

