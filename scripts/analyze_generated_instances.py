"""Characterization and diagnostic script for newly generated MO-JSSP instances (Phase F8.6.3).

Loads all 25 instances from data/generated/f86_3, validates them,
computes structural and operational diversity metrics, and saves
results to results/diagnostics/generated_instance_characteristics.csv.
"""

import csv
import math
import os
import statistics
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.mojssp.decoder import Decoder
from src.mojssp.evaluator import Evaluator
from src.mojssp.instance import Instance
from src.mojssp.io import load_dzn
from src.mojssp.solution import Solution
from src.mojssp.validator import validate_instance


def calculate_instance_characteristics(instance: Instance) -> Dict[str, float]:
    """Calculates comprehensive metrics for an instance."""
    n = instance.num_jobs
    m = instance.num_machines
    total_ops = instance.total_operations

    ops_per_job = total_ops / n if n > 0 else 0.0
    jobs_per_machine = n / m if m > 0 else 0.0
    ops_per_machine = total_ops / m if m > 0 else 0.0

    # 1. Durations and Energies across all modes of all operations
    all_durations: List[int] = []
    all_energies: List[float] = []
    op_energy_ratios: List[float] = []

    # Nominal workload per machine (using mode-averaged duration)
    machine_nominal_load: Dict[int, float] = {mach_id: 0.0 for mach_id in range(1, m + 1)}

    for op in instance.all_operations:
        for mode in op.modes:
            all_durations.append(mode.duration)
            all_energies.append(mode.energy)

        # Mode energy conflict ratio for this operation (fastest energy / slowest energy)
        # In our configuration: mode 5 is fastest/hungriest, mode 1 is slowest/cheapest
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

    # 2. Release dates across all operations
    all_releases = [op.release_date for op in instance.all_operations]
    rel_mean = statistics.mean(all_releases)
    rel_std = statistics.stdev(all_releases) if len(all_releases) > 1 else 0.0
    rel_cv = rel_std / rel_mean if rel_mean > 0 else 0.0

    # 3. Due dates and Tardiness Pressure
    all_dues = [job.due_date for job in instance.jobs]
    due_mean = statistics.mean(all_dues)
    due_std = statistics.stdev(all_dues) if len(all_dues) > 1 else 0.0
    due_cv = due_std / due_mean if due_mean > 0 else 0.0

    # Tardiness pressure: fraction of jobs where due_date < P_min(j)
    # where P_min(j) = r_{j,1} + sum_{k} min_v p_{j,k,v}
    jobs_tight_count = 0
    tightness_ratios: List[float] = []

    for job in instance.jobs:
        first_op_release = job.operations[0].release_date if job.operations else 0
        min_proc_sum = sum(min(mode.duration for mode in op.modes) for op in job.operations)
        p_min = first_op_release + min_proc_sum
        tightness = p_min / job.due_date if job.due_date > 0 else 1.0
        tightness_ratios.append(tightness)
        if job.due_date < p_min:
            jobs_tight_count += 1

    tardiness_pressure = jobs_tight_count / n if n > 0 else 0.0
    tardiness_tightness_mean = statistics.mean(tightness_ratios) if tightness_ratios else 1.0

    # 4. Machine Workload and Bottleneck Concentration
    workloads = list(machine_nominal_load.values())
    m_load_mean = statistics.mean(workloads)
    m_load_std = statistics.stdev(workloads) if len(workloads) > 1 else 0.0
    m_load_cv = m_load_std / m_load_mean if m_load_mean > 0 else 0.0

    max_load = max(workloads)
    bottleneck_concentration = max_load / m_load_mean if m_load_mean > 0 else 1.0

    return {
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
        "time_energy_conflict": round(time_energy_conflict, 4),
    }


def analyze_all_generated_instances(
    input_base_dir: str = "data/generated/f86_3",
    output_csv_path: str = "results/diagnostics/generated_instance_characteristics.csv",
) -> List[Dict]:
    """Analyzes all generated instances and writes characteristics to CSV."""
    base_dir = Path(input_base_dir)
    dzn_files = sorted(base_dir.rglob("*.dzn"))

    if not dzn_files:
        raise FileNotFoundError(f"No .dzn files found in {base_dir}")

    records: List[Dict] = []
    decoder = Decoder()
    evaluator = Evaluator()

    for file_path in dzn_files:
        instance_name = file_path.stem
        group_name = file_path.parent.name

        # 1. Load and validate
        instance = load_dzn(file_path, validate=True)
        errors = validate_instance(instance, raise_on_error=False)
        if errors:
            raise ValueError(f"Instance {instance_name} failed validation: {errors}")

        # 2. Decode and evaluate smoke check
        sol = Solution.random(instance)
        schedule = decoder.decode(instance, sol)
        obj_vals = evaluator.evaluate(instance, schedule)

        # 3. Compute characteristics
        chars = calculate_instance_characteristics(instance)
        record = {
            "instance_name": instance_name,
            "group": group_name,
            **chars,
            "smoke_cmax": obj_vals.makespan,
            "smoke_tardiness": obj_vals.tardiness,
            "smoke_energy": round(obj_vals.energy, 2),
        }
        records.append(record)

    # Save to CSV
    out_file = Path(output_csv_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = list(records[0].keys())
    with open(out_file, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in records:
            writer.writerow(r)

    print(f"Analyzed {len(records)} instances.")
    print(f"Characteristics saved to {out_file}")
    return records


if __name__ == "__main__":
    analyze_all_generated_instances()

