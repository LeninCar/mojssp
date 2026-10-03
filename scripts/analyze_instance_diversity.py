"""Structural Diversity Analysis for the 5 MO-JSSP Instances of Phase 8.6.

Analyzes instances:
- 5_10_2-5_1.dzn   (50 operations)
- 10_10_2-5_1.dzn  (100 operations)
- 15_10_2-5_1.dzn  (150 operations)
- 20_10_2-5_1.dzn  (200 operations)
- 20_20_2-5_1.dzn  (400 operations)

Computes:
- Grupo A: Tamaño (Scale)
- Grupo B: Duraciones
- Grupo C: Energía
- Grupo D: Release dates
- Grupo E: Due dates y presión de tardanza (Slack/Tightness)
- Grupo F: Flexibilidad de máquinas y modos
- Grupo G: Carga y congestión de máquinas
- Grupo H: Cotas de normalización existentes
- Grupo I: Características adimensionales y estructurales
- Matriz de distancia euclídea estandarizada entre instancias
- Visualizaciones (heatmaps y scatter plots)
- Cruce descriptivo con los resultados de F8.6

DO NOT modify any production code in src/mojssp/*.
"""

import csv
import json
import math
from pathlib import Path
import statistics
import sys
from typing import Any, Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mojssp import (
    Instance,
    Job,
    Operation,
    ProcessingMode,
    compute_instance_bounds,
    load_dzn,
)


def compute_instance_characterization(instance_path: Path) -> Dict[str, Any]:
    """Compute comprehensive structural features for a MO-JSSP instance."""
    inst: Instance = load_dzn(instance_path, validate=True)
    bounds = compute_instance_bounds(inst)

    n_jobs = inst.num_jobs
    n_mach = inst.num_machines
    n_ops = inst.total_operations
    all_ops = inst.all_operations
    all_jobs = inst.jobs

    # --- Grupo A: Tamaño ---
    ops_per_job = n_ops / n_jobs
    ops_per_mach = n_ops / n_mach
    jobs_per_mach = n_jobs / n_mach

    # --- Grupo B: Duraciones ---
    all_durations = [m.duration for op in all_ops for m in op.modes]
    dur_min = min(all_durations)
    dur_max = max(all_durations)
    dur_mean = statistics.mean(all_durations)
    dur_median = statistics.median(all_durations)
    dur_std = statistics.stdev(all_durations) if len(all_durations) > 1 else 0.0
    dur_range = dur_max - dur_min
    dur_cv = dur_std / dur_mean if dur_mean > 0 else 0.0

    # Per-operation duration properties
    op_dur_ranges = [max(m.duration for m in op.modes) - min(m.duration for m in op.modes) for op in all_ops]
    op_dur_ratios = [max(m.duration for m in op.modes) / min(m.duration for m in op.modes) for op in all_ops]
    op_dur_range_mean = statistics.mean(op_dur_ranges)
    op_dur_ratio_mean = statistics.mean(op_dur_ratios)

    # --- Grupo C: Energía ---
    all_energies = [m.energy for op in all_ops for m in op.modes]
    nrg_min = min(all_energies)
    nrg_max = max(all_energies)
    nrg_mean = statistics.mean(all_energies)
    nrg_median = statistics.median(all_energies)
    nrg_std = statistics.stdev(all_energies) if len(all_energies) > 1 else 0.0
    nrg_range = nrg_max - nrg_min
    nrg_cv = nrg_std / nrg_mean if nrg_mean > 0 else 0.0

    # Per-operation energy properties
    op_nrg_ranges = [max(m.energy for m in op.modes) - min(m.energy for m in op.modes) for op in all_ops]
    op_nrg_ratios = [
        max(m.energy for m in op.modes) / min(m.energy for m in op.modes)
        if min(m.energy for m in op.modes) > 0 else 0.0
        for op in all_ops
    ]
    op_nrg_range_mean = statistics.mean(op_nrg_ranges)
    op_nrg_ratio_mean = statistics.mean(op_nrg_ratios)

    # --- Grupo D: Release dates ---
    all_releases = [op.release_date for op in all_ops]
    rel_min = min(all_releases)
    rel_max = max(all_releases)
    rel_mean = statistics.mean(all_releases)
    rel_median = statistics.median(all_releases)
    rel_std = statistics.stdev(all_releases) if len(all_releases) > 1 else 0.0
    rel_range = rel_max - rel_min
    rel_cv = rel_std / rel_mean if rel_mean > 0 else 0.0
    prop_ops_rel_gt_0 = sum(1 for r in all_releases if r > 0) / len(all_releases)
    rel_dispersion_normalized = rel_range / bounds.cmax_max if bounds.cmax_max > 0 else 0.0

    # --- Grupo E: Due dates y presión de tardanza ---
    all_due_dates = [j.due_date for j in all_jobs]
    due_min = min(all_due_dates)
    due_max = max(all_due_dates)
    due_mean = statistics.mean(all_due_dates)
    due_median = statistics.median(all_due_dates)
    due_std = statistics.stdev(all_due_dates) if len(all_due_dates) > 1 else 0.0
    due_range = due_max - due_min
    due_cv = due_std / due_mean if due_mean > 0 else 0.0

    # Slack and tightness under fastest execution:
    # Minimum processing time required by job j: sum of min mode durations + first op release date
    job_min_durations = [sum(min(m.duration for m in op.modes) for op in j.operations) for j in all_jobs]
    job_min_starts = [j.operations[0].release_date for j in all_jobs]
    job_earliest_completions = [s + d for s, d in zip(job_min_starts, job_min_durations)]
    slacks = [d_j - c_min for d_j, c_min in zip(all_due_dates, job_earliest_completions)]
    tightness_ratios = [d_j / c_min if c_min > 0 else 1.0 for d_j, c_min in zip(all_due_dates, job_earliest_completions)]

    slack_mean = statistics.mean(slacks)
    slack_min = min(slacks)
    slack_max = max(slacks)
    tightness_ratio_mean = statistics.mean(tightness_ratios)
    prop_jobs_tight_fastest = sum(1 for s in slacks if s < 0) / len(slacks)

    # --- Grupo F: Flexibilidad de máquinas y modos ---
    mode_counts = [len(op.modes) for op in all_ops]
    modes_min = min(mode_counts)
    modes_max = max(mode_counts)
    modes_mean = statistics.mean(mode_counts)
    modes_std = statistics.stdev(mode_counts) if len(mode_counts) > 1 else 0.0
    prop_ops_multi_mode = sum(1 for c in mode_counts if c > 1) / len(mode_counts)

    # --- Grupo G: Carga y congestión de máquinas ---
    mach_op_counts = []
    mach_min_workloads = []
    mach_max_workloads = []

    for m_id in range(1, n_mach + 1):
        m_ops = inst.get_operations_for_machine(m_id)
        mach_op_counts.append(len(m_ops))
        w_min = sum(min(m.duration for m in op.modes) for op in m_ops)
        w_max = sum(max(m.duration for m in op.modes) for op in m_ops)
        mach_min_workloads.append(w_min)
        mach_max_workloads.append(w_max)

    mach_ops_min = min(mach_op_counts)
    mach_ops_max = max(mach_op_counts)
    mach_ops_mean = statistics.mean(mach_op_counts)
    mach_ops_std = statistics.stdev(mach_op_counts) if len(mach_op_counts) > 1 else 0.0
    mach_ops_cv = mach_ops_std / mach_ops_mean if mach_ops_mean > 0 else 0.0

    mach_w_min_mean = statistics.mean(mach_min_workloads)
    mach_w_min_std = statistics.stdev(mach_min_workloads) if len(mach_min_workloads) > 1 else 0.0
    mach_w_min_cv = mach_w_min_std / mach_w_min_mean if mach_w_min_mean > 0 else 0.0

    mach_w_max_mean = statistics.mean(mach_max_workloads)
    mach_w_max_std = statistics.stdev(mach_max_workloads) if len(mach_max_workloads) > 1 else 0.0
    mach_w_max_cv = mach_w_max_std / mach_w_max_mean if mach_w_max_mean > 0 else 0.0

    # --- Grupo H: Cotas de normalización existentes ---
    cmax_min = bounds.cmax_min
    cmax_max = bounds.cmax_max
    cmax_range = cmax_max - cmax_min

    tard_min = bounds.tardiness_min
    tard_max = bounds.tardiness_max
    tard_range = tard_max - tard_min

    nrg_b_min = bounds.energy_min
    nrg_b_max = bounds.energy_max
    nrg_b_range = nrg_b_max - nrg_b_min

    return {
        "instance": instance_path.name,
        # Grupo A: Tamaño
        "jobs": n_jobs,
        "machines": n_mach,
        "operations": n_ops,
        "operations_per_job": ops_per_job,
        "operations_per_machine": ops_per_mach,
        "jobs_per_machine": jobs_per_mach,
        # Grupo B: Duraciones
        "duration_min": dur_min,
        "duration_max": dur_max,
        "duration_mean": dur_mean,
        "duration_median": dur_median,
        "duration_std": dur_std,
        "duration_range": dur_range,
        "duration_cv": dur_cv,
        "op_duration_range_mean": op_dur_range_mean,
        "op_duration_ratio_mean": op_dur_ratio_mean,
        # Grupo C: Energía
        "energy_min": nrg_min,
        "energy_max": nrg_max,
        "energy_mean": nrg_mean,
        "energy_median": nrg_median,
        "energy_std": nrg_std,
        "energy_range": nrg_range,
        "energy_cv": nrg_cv,
        "op_energy_range_mean": op_nrg_range_mean,
        "op_energy_ratio_mean": op_nrg_ratio_mean,
        # Grupo D: Release dates
        "release_min": rel_min,
        "release_max": rel_max,
        "release_mean": rel_mean,
        "release_median": rel_median,
        "release_std": rel_std,
        "release_range": rel_range,
        "release_cv": rel_cv,
        "prop_ops_release_gt_0": prop_ops_rel_gt_0,
        "release_dispersion_normalized": rel_dispersion_normalized,
        # Grupo E: Due dates y presión
        "due_date_min": due_min,
        "due_date_max": due_max,
        "due_date_mean": due_mean,
        "due_date_median": due_median,
        "due_date_std": due_std,
        "due_date_range": due_range,
        "due_date_cv": due_cv,
        "slack_mean": slack_mean,
        "slack_min": slack_min,
        "slack_max": slack_max,
        "tightness_ratio_mean": tightness_ratio_mean,
        "prop_jobs_tight_fastest": prop_jobs_tight_fastest,
        # Grupo F: Flexibilidad
        "modes_per_op_min": modes_min,
        "modes_per_op_max": modes_max,
        "modes_per_op_mean": modes_mean,
        "modes_per_op_std": modes_std,
        "prop_ops_multi_mode": prop_ops_multi_mode,
        # Grupo G: Carga y congestión
        "machine_ops_min": mach_ops_min,
        "machine_ops_max": mach_ops_max,
        "machine_ops_mean": mach_ops_mean,
        "machine_ops_std": mach_ops_std,
        "machine_ops_cv": mach_ops_cv,
        "machine_workload_min_mean": mach_w_min_mean,
        "machine_workload_min_std": mach_w_min_std,
        "machine_workload_min_cv": mach_w_min_cv,
        "machine_workload_max_mean": mach_w_max_mean,
        "machine_workload_max_std": mach_w_max_std,
        "machine_workload_max_cv": mach_w_max_cv,
        # Grupo H: Cotas de normalización
        "cmax_min": cmax_min,
        "cmax_max": cmax_max,
        "cmax_range": cmax_range,
        "tardiness_min": tard_min,
        "tardiness_max": tard_max,
        "tardiness_range": tard_range,
        "energy_bound_min": nrg_b_min,
        "energy_bound_max": nrg_b_max,
        "energy_bound_range": nrg_b_range,
    }


def compute_standardized_distances(
    char_list: List[Dict[str, Any]],
    feature_keys: List[str],
) -> Tuple[List[str], List[List[float]], Dict[str, Dict[str, float]]]:
    """Compute pairwise Euclidean distance matrix over z-score standardized features."""
    instances = [c["instance"] for c in char_list]
    n_inst = len(char_list)

    # 1. Compute means and stds for normalization
    stats: Dict[str, Dict[str, float]] = {}
    for k in feature_keys:
        vals = [float(c[k]) for c in char_list]
        m = statistics.mean(vals)
        s = statistics.stdev(vals) if len(vals) > 1 else 0.0
        stats[k] = {"mean": m, "std": s}

    # 2. Standardize
    z_matrix = []
    for c in char_list:
        row = []
        for k in feature_keys:
            val = float(c[k])
            m = stats[k]["mean"]
            s = stats[k]["std"]
            z = (val - m) / s if s > 1e-12 else 0.0
            row.append(z)
        z_matrix.append(row)

    # 3. Compute Euclidean distance matrix
    dist_matrix = [[0.0 for _ in range(n_inst)] for _ in range(n_inst)]
    for i in range(n_inst):
        for j in range(n_inst):
            if i == j:
                dist_matrix[i][j] = 0.0
            else:
                dist_sq = sum((z_matrix[i][f] - z_matrix[j][f]) ** 2 for f in range(len(feature_keys)))
                d = math.sqrt(dist_sq)
                dist_matrix[i][j] = d

    return instances, dist_matrix, stats


def export_diversity_results(
    char_list: List[Dict[str, Any]],
    dist_instances: List[str],
    dist_matrix: List[List[float]],
    output_dir: Path,
) -> Tuple[Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    div_csv = output_dir / "f86_instance_diversity.csv"
    dist_csv = output_dir / "f86_instance_distances.csv"
    summary_json = output_dir / "f86_instance_diversity_summary.json"

    # 1. f86_instance_diversity.csv
    fieldnames = list(char_list[0].keys())
    with open(div_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for c in char_list:
            writer.writerow(c)

    # 2. f86_instance_distances.csv
    with open(dist_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["instance"] + dist_instances)
        for i, name in enumerate(dist_instances):
            row = [name] + [f"{dist_matrix[i][j]:.6f}" for j in range(len(dist_instances))]
            writer.writerow(row)

    # 3. f86_instance_diversity_summary.json
    summary_data = {
        "instances": char_list,
        "distances": {
            dist_instances[i]: {
                dist_instances[j]: dist_matrix[i][j] for j in range(len(dist_instances))
            }
            for i in range(len(dist_instances))
        },
    }
    with open(summary_json, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2)

    return div_csv, dist_csv, summary_json


def generate_diversity_plots(
    char_list: List[Dict[str, Any]],
    structural_keys: List[str],
    dist_instances: List[str],
    dist_matrix: List[List[float]],
    output_dir: Path,
) -> List[Path]:
    import matplotlib.pyplot as plt

    plots_dir = output_dir / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)
    created_plots = []

    inst_labels = [c["instance"].replace(".dzn", "") for c in char_list]

    # Plot 1: Distance Heatmap
    fig, ax = plt.subplots(figsize=(7, 6))
    im = ax.imshow(dist_matrix, cmap="YlGnBu")
    ax.set_xticks(range(len(inst_labels)))
    ax.set_yticks(range(len(inst_labels)))
    ax.set_xticklabels(inst_labels, rotation=45, ha="right", fontsize=10)
    ax.set_yticklabels(inst_labels, fontsize=10)
    for i in range(len(inst_labels)):
        for j in range(len(inst_labels)):
            ax.text(j, i, f"{dist_matrix[i][j]:.2f}", ha="center", va="center", color="black" if dist_matrix[i][j] < 4 else "white", fontsize=9)
    plt.colorbar(im, ax=ax, label="Euclidean Distance (Standardized)")
    ax.set_title("Matriz de Distancia Estructural entre Instancias F8.6", fontsize=12, pad=12)
    plt.tight_layout()
    p1 = plots_dir / "f86_distance_heatmap.png"
    plt.savefig(p1, dpi=300)
    plt.close()
    created_plots.append(p1)

    # Plot 2: Scatter Operations vs CVs (Duration CV & Energy CV)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 5))
    ops = [c["operations"] for c in char_list]
    dur_cvs = [c["duration_cv"] for c in char_list]
    nrg_cvs = [c["energy_cv"] for c in char_list]

    ax1.scatter(ops, dur_cvs, color="#2b5c8f", s=80, edgecolors="black", zorder=3)
    for op, cv, lbl in zip(ops, dur_cvs, inst_labels):
        ax1.annotate(lbl, (op, cv), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=9)
    ax1.set_xlabel("Número Total de Operaciones", fontsize=10)
    ax1.set_ylabel("Duration CV (std / mean)", fontsize=10)
    ax1.set_title("Escala vs Variabilidad de Duración", fontsize=11)
    ax1.grid(True, linestyle="--", alpha=0.5)

    ax2.scatter(ops, nrg_cvs, color="#d95f02", s=80, edgecolors="black", zorder=3)
    for op, cv, lbl in zip(ops, nrg_cvs, inst_labels):
        ax2.annotate(lbl, (op, cv), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=9)
    ax2.set_xlabel("Número Total de Operaciones", fontsize=10)
    ax2.set_ylabel("Energy CV (std / mean)", fontsize=10)
    ax2.set_title("Escala vs Variabilidad de Energía", fontsize=11)
    ax2.grid(True, linestyle="--", alpha=0.5)

    plt.suptitle("Análisis de Invarianza Estructural de Distribuciones", fontsize=13)
    plt.tight_layout()
    p2 = plots_dir / "f86_scatter_ops_vs_cv.png"
    plt.savefig(p2, dpi=300)
    plt.close()
    created_plots.append(p2)

    return created_plots


def main() -> None:
    instance_files = [
        Path("data/experimental/5_10_2-5_1.dzn"),
        Path("data/experimental/10_10_2-5_1.dzn"),
        Path("data/experimental/15_10_2-5_1.dzn"),
        Path("data/experimental/20_10_2-5_1.dzn"),
        Path("data/experimental/20_20_2-5_1.dzn"),
    ]

    print("================================================================================")
    print("FASE 8.6.1: CARACTERIZACIÓN DE DIVERSIDAD ESTRUCTURAL DE LAS 5 INSTANCIAS")
    print("================================================================================")

    char_list = [compute_instance_characterization(p) for p in instance_files]

    # Selected dimensionless structural features for distance metric
    structural_features = [
        "jobs_per_machine",
        "operations_per_job",
        "duration_cv",
        "energy_cv",
        "op_duration_ratio_mean",
        "op_energy_ratio_mean",
        "release_cv",
        "due_date_cv",
        "tightness_ratio_mean",
        "machine_workload_min_cv",
        "release_dispersion_normalized",
    ]

    dist_instances, dist_matrix, stats = compute_standardized_distances(char_list, structural_features)

    out_dir = Path("results/diagnostics")
    div_csv, dist_csv, summary_json = export_diversity_results(
        char_list, dist_instances, dist_matrix, out_dir
    )
    created_plots = generate_diversity_plots(char_list, structural_features, dist_instances, dist_matrix, out_dir)

    print(f"\nArchivos generados exitosamente:")
    print(f"  1. {div_csv}")
    print(f"  2. {dist_csv}")
    print(f"  3. {summary_json}")
    for p in created_plots:
        print(f"  - Gráfico: {p}")

    # Console summary print
    print("\n" + "=" * 120)
    print("TABLA 1: CARACTERIZACIÓN ESTRUCTURAL DE LAS 5 INSTANCIAS")
    print("=" * 120)
    hdr1 = f"{'Instancia':<18} {'Jobs':<5} {'Mach':<5} {'Ops':<5} {'Ops/Job':<8} {'Ops/M':<7} {'Dur Mean':<9} {'Dur CV':<8} {'Nrg Mean':<9} {'Nrg CV':<8} {'Due CV':<8} {'Tightness':<10}"
    print(hdr1)
    print("-" * 120)
    for c in char_list:
        print(
            f"{c['instance']:<18} {c['jobs']:<5} {c['machines']:<5} {c['operations']:<5} "
            f"{c['operations_per_job']:<8.1f} {c['operations_per_machine']:<7.1f} "
            f"{c['duration_mean']:<9.2f} {c['duration_cv']:<8.4f} "
            f"{c['energy_mean']:<9.2f} {c['energy_cv']:<8.4f} "
            f"{c['due_date_cv']:<8.4f} {c['tightness_ratio_mean']:<10.3f}"
        )
    print("-" * 120)

    print("\n" + "=" * 120)
    print("TABLA 2: MATRIZ DE DISTANCIA EUCLÍDEA ESTANDARIZADA (Características Estructurales)")
    print("=" * 120)
    inst_names = [c["instance"].replace(".dzn", "") for c in char_list]
    hdr2 = f"{'Instancia':<18} " + " ".join([f"{name:>12}" for name in inst_names])
    print(hdr2)
    print("-" * 120)
    for i, name in enumerate(inst_names):
        row_str = f"{name:<18} " + " ".join([f"{dist_matrix[i][j]:>12.4f}" for j in range(len(inst_names))])
        print(row_str)
    print("-" * 120)


if __name__ == "__main__":
    main()
