"""Audit and validation script for instance diversity across the 37 MO-JSSP instances (Phase F8.6.4).

Consolidates:
- 12 original instances in data/experimental/
- 25 new instances in data/generated/f86_3/

Computes:
1. Unified structural and operational characteristics across all 37 instances.
2. Standardized Euclidean distance matrix across all pairs.
3. Factor coverage matrix comparing original vs generated datasets.
4. Summary diagnostics (redundancies, extreme cases, distance distributions).

Outputs:
- results/diagnostics/f864_instance_characteristics.csv
- results/diagnostics/f864_instance_distances.csv
- results/diagnostics/f864_factor_coverage.csv
- results/diagnostics/f864_summary.json
"""

import csv
import json
import math
import os
from pathlib import Path
import statistics
import sys
from typing import Any, Dict, List, Tuple

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from mojssp import (
    Instance,
    compute_instance_bounds,
    load_dzn,
)


def compute_unified_characteristics(inst_path: Path, source: str) -> Dict[str, Any]:
    """Compute exact, uniform characteristics for any MO-JSSP instance."""
    inst: Instance = load_dzn(inst_path, validate=True)
    bounds = compute_instance_bounds(inst)

    n = inst.num_jobs
    m = inst.num_machines
    total_ops = inst.total_operations

    ops_per_job = total_ops / n if n > 0 else 0.0
    jobs_per_machine = n / m if m > 0 else 0.0
    ops_per_machine = total_ops / m if m > 0 else 0.0

    # 1. Durations and energies
    all_durations: List[int] = []
    all_energies: List[float] = []
    op_energy_ratios: List[float] = []
    machine_nominal_load: Dict[int, float] = {mach_id: 0.0 for mach_id in range(1, m + 1)}

    for op in inst.all_operations:
        for mode in op.modes:
            all_durations.append(mode.duration)
            all_energies.append(mode.energy)

        # Mode energy conflict ratio for this operation (fastest mode / slowest mode)
        e_slowest = op.modes[0].energy
        e_fastest = op.modes[-1].energy
        ratio = (e_fastest / e_slowest) if e_slowest > 0 else 1.0
        op_energy_ratios.append(ratio)

        # Average duration for this op
        avg_dur = sum(mode.duration for mode in op.modes) / len(op.modes)
        machine_nominal_load[op.machine_id] = machine_nominal_load.get(op.machine_id, 0.0) + avg_dur

    dur_mean = statistics.mean(all_durations)
    dur_std = statistics.stdev(all_durations) if len(all_durations) > 1 else 0.0
    dur_cv = dur_std / dur_mean if dur_mean > 0 else 0.0

    nrg_mean = statistics.mean(all_energies)
    nrg_std = statistics.stdev(all_energies) if len(all_energies) > 1 else 0.0
    nrg_cv = nrg_std / nrg_mean if nrg_mean > 0 else 0.0

    time_energy_conflict = statistics.mean(op_energy_ratios) if op_energy_ratios else 1.0

    # 2. Release dates
    all_releases = [op.release_date for op in inst.all_operations]
    rel_mean = statistics.mean(all_releases)
    rel_std = statistics.stdev(all_releases) if len(all_releases) > 1 else 0.0
    rel_cv = rel_std / rel_mean if rel_mean > 0 else 0.0

    # 3. Due dates and Tardiness Pressure
    all_dues = [job.due_date for job in inst.jobs]
    due_mean = statistics.mean(all_dues)
    due_std = statistics.stdev(all_dues) if len(all_dues) > 1 else 0.0
    due_cv = due_std / due_mean if due_mean > 0 else 0.0

    jobs_tight_count = 0
    tightness_ratios: List[float] = []

    for job in inst.jobs:
        first_op_release = job.operations[0].release_date if job.operations else 0
        min_proc_sum = sum(min(mode.duration for mode in op.modes) for op in job.operations)
        p_min = first_op_release + min_proc_sum
        tightness = p_min / job.due_date if job.due_date > 0 else 1.0
        tightness_ratios.append(tightness)
        if job.due_date < p_min:
            jobs_tight_count += 1

    tardiness_pressure = jobs_tight_count / n if n > 0 else 0.0
    tardiness_tightness_mean = statistics.mean(tightness_ratios) if tightness_ratios else 1.0

    # 4. Machine Workload and Bottleneck
    workloads = list(machine_nominal_load.values())
    m_load_mean = statistics.mean(workloads)
    m_load_std = statistics.stdev(workloads) if len(workloads) > 1 else 0.0
    m_load_cv = m_load_std / m_load_mean if m_load_mean > 0 else 0.0

    max_load = max(workloads)
    bottleneck_concentration = max_load / m_load_mean if m_load_mean > 0 else 1.0

    return {
        "instance": inst_path.stem,
        "source": source,
        "jobs": n,
        "machines": m,
        "operations": total_ops,
        "operations_per_job": round(ops_per_job, 2),
        "operations_per_machine": round(ops_per_machine, 2),
        "jobs_per_machine": round(jobs_per_machine, 2),
        "duration_mean": round(dur_mean, 2),
        "duration_std": round(dur_std, 2),
        "duration_cv": round(dur_cv, 4),
        "duration_min": min(all_durations),
        "duration_max": max(all_durations),
        "energy_mean": round(nrg_mean, 2),
        "energy_std": round(nrg_std, 2),
        "energy_cv": round(nrg_cv, 4),
        "energy_min": min(all_energies),
        "energy_max": max(all_energies),
        "time_energy_conflict": round(time_energy_conflict, 4),
        "release_mean": round(rel_mean, 2),
        "release_std": round(rel_std, 2),
        "release_cv": round(rel_cv, 4),
        "due_mean": round(due_mean, 2),
        "due_std": round(due_std, 2),
        "due_cv": round(due_cv, 4),
        "due_min": min(all_dues),
        "due_max": max(all_dues),
        "machine_load_mean": round(m_load_mean, 2),
        "machine_load_std": round(m_load_std, 2),
        "machine_load_cv": round(m_load_cv, 4),
        "bottleneck_concentration": round(bottleneck_concentration, 4),
        "tardiness_pressure": round(tardiness_pressure, 4),
        "tardiness_tightness_mean": round(tardiness_tightness_mean, 4),
        "bound_cmax_min": bounds.cmax_min,
        "bound_cmax_max": bounds.cmax_max,
        "bound_tard_min": bounds.tardiness_min,
        "bound_tard_max": bounds.tardiness_max,
        "bound_energy_min": bounds.energy_min,
        "bound_energy_max": bounds.energy_max,
    }


def run_f864_audit() -> None:
    diagnostics_dir = PROJECT_ROOT / "results" / "diagnostics"
    diagnostics_dir.mkdir(parents=True, exist_ok=True)

    exp_dir = PROJECT_ROOT / "data" / "experimental"
    gen_dir = PROJECT_ROOT / "data" / "generated" / "f86_3"

    exp_files = sorted(exp_dir.glob("*.dzn"))
    gen_files = sorted(gen_dir.rglob("*.dzn"))

    print(f"Loaded {len(exp_files)} original instances and {len(gen_files)} generated instances.")
    assert len(exp_files) == 12, f"Expected 12 original instances, got {len(exp_files)}"
    assert len(gen_files) == 25, f"Expected 25 generated instances, got {len(gen_files)}"

    all_instances: List[Dict[str, Any]] = []

    # Process original instances
    for p in exp_files:
        all_instances.append(compute_unified_characteristics(p, source="original"))

    # Process generated instances
    for p in gen_files:
        all_instances.append(compute_unified_characteristics(p, source="generated"))

    assert len(all_instances) == 37, f"Expected 37 total instances, got {len(all_instances)}"

    # 1. Save characteristics table
    char_csv = diagnostics_dir / "f864_instance_characteristics.csv"
    fieldnames = list(all_instances[0].keys())
    with open(char_csv, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in all_instances:
            writer.writerow(row)
    print(f"Saved characteristics table to {char_csv}")

    # 2. Compute Distance Matrix (StandardScaler + Euclidean Distance)
    # Features selected for distance: scale, structural, and factor dimensions
    features_for_dist = [
        "operations",
        "jobs_per_machine",
        "duration_mean",
        "duration_cv",
        "energy_mean",
        "energy_cv",
        "time_energy_conflict",
        "release_mean",
        "release_cv",
        "due_mean",
        "due_cv",
        "machine_load_cv",
        "bottleneck_concentration",
        "tardiness_pressure",
    ]

    # Calculate mean and std for each feature across the 37 instances
    means = {}
    stds = {}
    for feat in features_for_dist:
        vals = [inst[feat] for inst in all_instances]
        means[feat] = statistics.mean(vals)
        s = statistics.stdev(vals) if len(vals) > 1 else 1.0
        stds[feat] = s if s > 0 else 1.0

    # Compute z-score normalized vector for each instance
    norm_vectors: Dict[str, List[float]] = {}
    for inst in all_instances:
        name = inst["instance"]
        vec = [(inst[feat] - means[feat]) / stds[feat] for feat in features_for_dist]
        norm_vectors[name] = vec

    # Compute pairwise Euclidean distances
    dist_records: List[Dict[str, Any]] = []
    n_inst = len(all_instances)

    for i in range(n_inst):
        inst_a = all_instances[i]
        name_a = inst_a["instance"]
        vec_a = norm_vectors[name_a]

        for j in range(i + 1, n_inst):
            inst_b = all_instances[j]
            name_b = inst_b["instance"]
            vec_b = norm_vectors[name_b]

            dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(vec_a, vec_b)))

            # Classification
            if dist < 1.0:
                similarity_cat = "muy similares"
            elif dist < 2.5:
                similarity_cat = "similares"
            elif dist < 5.0:
                similarity_cat = "moderadamente diferentes"
            else:
                similarity_cat = "claramente diferentes"

            # Pair type
            if inst_a["source"] == "original" and inst_b["source"] == "original":
                pair_type = "original-original"
            elif inst_a["source"] == "generated" and inst_b["source"] == "generated":
                pair_type = "generated-generated"
            else:
                pair_type = "original-generated"

            dist_records.append({
                "instance_a": name_a,
                "source_a": inst_a["source"],
                "instance_b": name_b,
                "source_b": inst_b["source"],
                "pair_type": pair_type,
                "distance": round(dist, 4),
                "similarity_category": similarity_cat,
            })

    # Save distances CSV
    dist_csv = diagnostics_dir / "f864_instance_distances.csv"
    with open(dist_csv, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(dist_records[0].keys()))
        writer.writeheader()
        for r in dist_records:
            writer.writerow(r)
    print(f"Saved distance matrix ({len(dist_records)} pairs) to {dist_csv}")

    # 3. Factor Coverage Matrix
    coverage_rows = [
        {
            "factor": "Escala (N ops)",
            "original_range": f"{min(i['operations'] for i in all_instances if i['source'] == 'original')} - {max(i['operations'] for i in all_instances if i['source'] == 'original')}",
            "generated_range": f"{min(i['operations'] for i in all_instances if i['source'] == 'generated')} - {max(i['operations'] for i in all_instances if i['source'] == 'generated')}",
            "original_distinct_sizes": len(set(i['operations'] for i in all_instances if i['source'] == 'original')),
            "generated_distinct_sizes": len(set(i['operations'] for i in all_instances if i['source'] == 'generated')),
            "dimension_notes": "Originales cubren hasta 2500 ops (50x50); Generadas se enfocan en escala tractable (50-400 ops)."
        },
        {
            "factor": "Jobs/Machines Ratio",
            "original_range": f"{min(i['jobs_per_machine'] for i in all_instances if i['source'] == 'original'):.2f} - {max(i['jobs_per_machine'] for i in all_instances if i['source'] == 'original'):.2f}",
            "generated_range": f"{min(i['jobs_per_machine'] for i in all_instances if i['source'] == 'generated'):.2f} - {max(i['jobs_per_machine'] for i in all_instances if i['source'] == 'generated'):.2f}",
            "original_distinct_sizes": len(set(i['jobs_per_machine'] for i in all_instances if i['source'] == 'original')),
            "generated_distinct_sizes": len(set(i['jobs_per_machine'] for i in all_instances if i['source'] == 'generated')),
            "dimension_notes": "Originales: ratio entre 0.5 y 2.0; Generadas agregan instancias explícitas con ratio bajo (0.5) y alto (2.0) a escala constante (200 ops)."
        },
        {
            "factor": "Bottleneck Concentration",
            "original_range": f"{min(i['bottleneck_concentration'] for i in all_instances if i['source'] == 'original'):.4f} - {max(i['bottleneck_concentration'] for i in all_instances if i['source'] == 'original'):.4f}",
            "generated_range": f"{min(i['bottleneck_concentration'] for i in all_instances if i['source'] == 'generated'):.4f} - {max(i['bottleneck_concentration'] for i in all_instances if i['source'] == 'generated'):.4f}",
            "original_distinct_sizes": 12,
            "generated_distinct_sizes": 25,
            "dimension_notes": "Originales están todas balanceadas (~1.06 - 1.15); Generadas introducen cuellos de botella severos (~2.84 - 2.94)."
        },
        {
            "factor": "Heterogeneidad Duración (CV)",
            "original_range": f"{min(i['duration_cv'] for i in all_instances if i['source'] == 'original'):.4f} - {max(i['duration_cv'] for i in all_instances if i['source'] == 'original'):.4f}",
            "generated_range": f"{min(i['duration_cv'] for i in all_instances if i['source'] == 'generated'):.4f} - {max(i['duration_cv'] for i in all_instances if i['source'] == 'generated'):.4f}",
            "original_distinct_sizes": 12,
            "generated_distinct_sizes": 25,
            "dimension_notes": "Originales homogéneas en CV (~0.52 - 0.54); Generadas cubren desde CV bajo (0.30) hasta CV muy alto (1.05)."
        },
        {
            "factor": "Conflicto Tiempo-Energía (Ratio E5/E1)",
            "original_range": f"{min(i['time_energy_conflict'] for i in all_instances if i['source'] == 'original'):.4f} - {max(i['time_energy_conflict'] for i in all_instances if i['source'] == 'original'):.4f}",
            "generated_range": f"{min(i['time_energy_conflict'] for i in all_instances if i['source'] == 'generated'):.4f} - {max(i['time_energy_conflict'] for i in all_instances if i['source'] == 'generated'):.4f}",
            "original_distinct_sizes": 12,
            "generated_distinct_sizes": 25,
            "dimension_notes": "Originales tienen conflicto moderado constante (~2.36 - 2.97); Generadas cubren débil (1.29), moderado (3.00) y fuerte (37.52)."
        },
        {
            "factor": "Presión de Tardanza (Fracción d_j < P_min)",
            "original_range": f"{min(i['tardiness_pressure'] for i in all_instances if i['source'] == 'original'):.4f} - {max(i['tardiness_pressure'] for i in all_instances if i['source'] == 'original'):.4f}",
            "generated_range": f"{min(i['tardiness_pressure'] for i in all_instances if i['source'] == 'generated'):.4f} - {max(i['tardiness_pressure'] for i in all_instances if i['source'] == 'generated'):.4f}",
            "original_distinct_sizes": 12,
            "generated_distinct_sizes": 25,
            "dimension_notes": "Originales tienen presión baja (~0.0 - 0.10); Generadas cubren desde presión nula (0.0) hasta presión garantizada al 100% (1.0)."
        },
        {
            "factor": "Dispersión de Releases (Mean)",
            "original_range": f"{min(i['release_mean'] for i in all_instances if i['source'] == 'original'):.2f} - {max(i['release_mean'] for i in all_instances if i['source'] == 'original'):.2f}",
            "generated_range": f"{min(i['release_mean'] for i in all_instances if i['source'] == 'generated'):.2f} - {max(i['release_mean'] for i in all_instances if i['source'] == 'generated'):.2f}",
            "original_distinct_sizes": 12,
            "generated_distinct_sizes": 25,
            "dimension_notes": "Originales tienen releases escalonados correlacionados con tamaño; Generadas añaden condición estática pura (0.0) y dispersión alta (>260.0)."
        },
        {
            "factor": "Interacciones Controladas",
            "original_range": "Ninguna (instancias generadas con un único proceso base)",
            "generated_range": "8 combinaciones explícitas de 2 factores (Tardiness+Btnk, Dur+Btnk, Tard+Nrg, etc.)",
            "original_distinct_sizes": 0,
            "generated_distinct_sizes": 8,
            "dimension_notes": "Aporte exclusivo de las nuevas instancias para estudiar efectos acoplados."
        },
    ]

    coverage_csv = diagnostics_dir / "f864_factor_coverage.csv"
    with open(coverage_csv, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(coverage_rows[0].keys()))
        writer.writeheader()
        for r in coverage_rows:
            writer.writerow(r)
    print(f"Saved factor coverage matrix to {coverage_csv}")

    # 4. Summary JSON
    # Analyze distance distribution
    distances_orig_orig = [r["distance"] for r in dist_records if r["pair_type"] == "original-original"]
    distances_gen_gen = [r["distance"] for r in dist_records if r["pair_type"] == "generated-generated"]
    distances_orig_gen = [r["distance"] for r in dist_records if r["pair_type"] == "original-generated"]

    # Redundancies (distance < 1.0)
    redundant_pairs = [r for r in dist_records if r["distance"] < 1.0]

    # Extreme cases
    extreme_cases = [
        {
            "instance": "nrg_strong_10x10",
            "classification": "condición de estrés / conflicto extremo tiempo-energía",
            "key_metrics": {"time_energy_conflict": 37.52, "energy_cv": 1.04},
            "experimental_role": "Evalúa el comportamiento de los algoritmos ante un frente Pareto empinado donde la aceleración penaliza masivamente el consumo energético."
        },
        {
            "instance": "tard_high_10x10",
            "classification": "condición de estrés / presión de tardanza garantizada",
            "key_metrics": {"tardiness_pressure": 1.0, "due_mean": 229.6},
            "experimental_role": "Fuerza tardanza positiva en el 100% de los trabajos independientemente de la velocidad, creando tensión permanente en el objetivo T."
        },
        {
            "instance": "btnk_high_10x10",
            "classification": "condición de estrés / cuello de botella severo",
            "key_metrics": {"bottleneck_concentration": 2.84, "duration_cv": 1.00},
            "experimental_role": "Evalúa congestión asimétrica extrema donde 2 máquinas concentran casi el triple de la carga media."
        },
        {
            "instance": "rel_high_10x10",
            "classification": "condición de estrés / alta dispersión temporal de releases",
            "key_metrics": {"release_mean": 265.01, "release_cv": 0.41},
            "experimental_role": "Impone ventanas de llegada dilatadas que limitan la compactación semi-activa de los primeros bloques de tiempo."
        },
        {
            "instance": "rel_zero_10x10",
            "classification": "condición de referencia / JSSP estático clásico",
            "key_metrics": {"release_mean": 0.0, "release_cv": 0.0},
            "experimental_role": "Permite comparar contra la formulación tradicional de taller estático donde todos los trabajos están disponibles en t=0."
        },
        {
            "instance": "load_high_20x10",
            "classification": "condición de alta congestión de recursos (ratio jobs/machines = 2.0)",
            "key_metrics": {"jobs_per_machine": 2.0, "operations": 200},
            "experimental_role": "Evalúa alta competencia entre trabajos manteniendo escala de 200 operaciones."
        },
        {
            "instance": "load_low_10x20",
            "classification": "condición de baja congestión de recursos (ratio jobs/machines = 0.5)",
            "key_metrics": {"jobs_per_machine": 0.5, "operations": 200},
            "experimental_role": "Evalúa precedencia dominante con recursos holgados manteniendo escala de 200 operaciones."
        },
    ]

    summary_data = {
        "audit_phase": "F8.6.4",
        "total_instances": 37,
        "counts": {
            "original_instances": len(exp_files),
            "generated_instances": len(gen_files),
        },
        "distances_statistics": {
            "all_pairs_count": len(dist_records),
            "original_original": {
                "count": len(distances_orig_orig),
                "mean_distance": round(statistics.mean(distances_orig_orig), 4),
                "min_distance": round(min(distances_orig_orig), 4),
                "max_distance": round(max(distances_orig_orig), 4),
            },
            "generated_generated": {
                "count": len(distances_gen_gen),
                "mean_distance": round(statistics.mean(distances_gen_gen), 4),
                "min_distance": round(min(distances_gen_gen), 4),
                "max_distance": round(max(distances_gen_gen), 4),
            },
            "original_generated": {
                "count": len(distances_orig_gen),
                "mean_distance": round(statistics.mean(distances_orig_gen), 4),
                "min_distance": round(min(distances_orig_gen), 4),
                "max_distance": round(max(distances_orig_gen), 4),
            },
        },
        "redundancy_analysis": {
            "redundant_pairs_count": len(redundant_pairs),
            "redundant_pairs": redundant_pairs,
        },
        "extreme_cases": extreme_cases,
    }

    summary_json = diagnostics_dir / "f864_summary.json"
    summary_json.write_text(json.dumps(summary_data, indent=2), encoding="utf-8")
    print(f"Saved summary JSON to {summary_json}")


if __name__ == "__main__":
    run_f864_audit()
