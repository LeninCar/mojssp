"""Pilot experiment runner for 5 instances x 5 seeds x 5 algorithms = 125 runs.

Benchmark comparison of:
- NSGA-II
- NSGA-II+LS
- MOPSO
- MOEA/D
- SPEA2
under a strict evaluation budget of exactly 1000 FE with zero overshoot.

Generates:
- results/experiments/pilot_runs.csv (125 individual run records)
- results/experiments/pilot_checkpoints.csv (trajectory checkpoints per run)
- results/experiments/pilot_complementarity.csv (union and exclusive contributions per instance-seed)
- results/experiments/pilot_summary_by_instance.csv (mean and std metrics by instance-algorithm)

Protects existing F8.5 and F8.6 artifacts.
"""

from collections import defaultdict
import csv
from dataclasses import dataclass
import math
from pathlib import Path
import statistics
import sys
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mojssp import (
    Decoder,
    Evaluator,
    Instance,
    MOEADArm,
    MOPSOArm,
    NSGA2Arm,
    NSGA2LSArm,
    ObjectiveNormalizer,
    ParetoArchive,
    SPEA2Arm,
    compute_archive_hypervolume,
    compute_instance_bounds,
    load_dzn,
)
from mojssp.runner import RunResult, run_standalone_experiment


@dataclass
class PilotRunRecord:
    run_id: str
    instance: str
    algorithm: str
    seed: int
    budget: int
    evaluations_used: int
    overshoot: int
    runtime_seconds: float
    final_hv: float
    archive_size: int
    unique_solutions_count: int
    completed: bool
    error: str
    pareto_front: Tuple[Tuple[float, float, float], ...]
    archive_snapshot: ParetoArchive


@dataclass
class CheckpointRecord:
    run_id: str
    instance: str
    algorithm: str
    seed: int
    evaluations: int
    hypervolume: float


@dataclass
class ComplementarityRecord:
    instance: str
    seed: int
    algorithm: str
    individual_hv: float
    individual_archive_size: int
    union_hv: float
    union_archive_size: int
    solutions_in_union: int
    exclusive_solutions_count: int
    marginal_hv_delta: float
    relative_marginal_hv_pct: float


def run_single_pilot_execution(
    instance_path: Path,
    algorithm: str,
    seed: int,
    budget: int = 1000,
    block_size: int = 50,
    population_size: int = 30,
) -> Tuple[PilotRunRecord, List[CheckpointRecord]]:
    """Execute a single run under strict budget, tracking checkpoints and archive."""
    inst = load_dzn(instance_path, validate=True)
    normalizer = ObjectiveNormalizer(compute_instance_bounds(inst))

    if algorithm == "NSGA-II":
        arm = NSGA2Arm(inst, population_size=population_size, seed=seed, max_evaluations=budget)
    elif algorithm == "NSGA-II+LS":
        arm = NSGA2LSArm(
            inst,
            population_size=population_size,
            seed=seed,
            max_evaluations=budget,
            max_ls_iterations=10,
            max_ls_neighbors=10,
        )
    elif algorithm == "MOPSO":
        arm = MOPSOArm(inst, population_size=population_size, seed=seed, max_evaluations=budget)
    elif algorithm == "MOEA/D":
        arm = MOEADArm(inst, population_size=population_size, seed=seed, max_evaluations=budget)
    elif algorithm == "SPEA2":
        arm = SPEA2Arm(
            inst,
            population_size=population_size,
            archive_size=population_size,
            seed=seed,
            max_evaluations=budget,
        )
    else:
        raise ValueError(f"Unknown algorithm: {algorithm}")

    checkpoints: List[CheckpointRecord] = []
    evals_done = 0
    t0 = time.perf_counter()
    error_msg = ""

    last_block_res = None
    try:
        while evals_done < budget and not arm.is_completed:
            step_budget = min(block_size, budget - evals_done)
            last_block_res = arm.run(step_budget)
            evals_done = arm.total_evaluations

            current_hv = compute_archive_hypervolume(last_block_res.solutions, normalizer)
            checkpoints.append(
                CheckpointRecord(
                    run_id=f"{inst.name}_{algorithm}_{seed}",
                    instance=inst.name,
                    algorithm=algorithm,
                    seed=seed,
                    evaluations=evals_done,
                    hypervolume=current_hv,
                )
            )

            if last_block_res.completed or last_block_res.evaluations_used == 0:
                break
    except Exception as e:
        error_msg = str(e)

    runtime_s = time.perf_counter() - t0
    final_archive = (
        last_block_res.solutions if last_block_res is not None else ParetoArchive()
    )
    final_hv = compute_archive_hypervolume(final_archive, normalizer) if not error_msg else 0.0

    unique_seqs = len(set(e.solution.sequence for e in final_archive.entries))
    front_coords = tuple(
        (float(e.objectives.makespan), float(e.objectives.tardiness), float(e.objectives.energy))
        for e in final_archive.entries
    )
    overshoot = max(0, arm.total_evaluations - budget)

    rec = PilotRunRecord(
        run_id=f"{inst.name}_{algorithm}_{seed}",
        instance=inst.name,
        algorithm=algorithm,
        seed=seed,
        budget=budget,
        evaluations_used=arm.total_evaluations,
        overshoot=overshoot,
        runtime_seconds=runtime_s,
        final_hv=final_hv,
        archive_size=len(final_archive),
        unique_solutions_count=unique_seqs,
        completed=arm.is_completed,
        error=error_msg,
        pareto_front=front_coords,
        archive_snapshot=final_archive,
    )

    return rec, checkpoints


def compute_complementarity_analysis(
    instance_path: Path,
    runs_by_instance_seed: Dict[Tuple[str, int], Dict[str, PilotRunRecord]],
) -> List[ComplementarityRecord]:
    """Build the non-dominated union for each (instance, seed) and compute contributions."""
    inst = load_dzn(instance_path, validate=True)
    normalizer = ObjectiveNormalizer(compute_instance_bounds(inst))
    results: List[ComplementarityRecord] = []

    for (inst_name, seed), alg_runs in runs_by_instance_seed.items():
        if inst_name != inst.name:
            continue

        # 1. Build combined union archive
        union_archive = ParetoArchive()
        for alg_name, r in alg_runs.items():
            for entry in r.archive_snapshot.entries:
                union_archive.add(entry.solution, entry.schedule, entry.objectives)

        union_hv = compute_archive_hypervolume(union_archive, normalizer)
        union_entries = list(union_archive.entries)

        # 2. For each algorithm, determine contribution
        for alg_name, r in alg_runs.items():
            alg_archive = r.archive_snapshot

            # Set of genotypes in alg_archive
            alg_sol_keys = set((e.solution.sequence, e.solution.modes) for e in alg_archive.entries)

            # Check which entries in union_archive were contributed by this algorithm
            in_union_entries = [
                e for e in union_entries
                if (e.solution.sequence, e.solution.modes) in alg_sol_keys
            ]
            solutions_in_union = len(in_union_entries)

            # Check exclusive solutions: solutions in union that appear in NO other algorithm's archive
            other_sol_keys = set()
            for other_name, other_r in alg_runs.items():
                if other_name != alg_name:
                    for e in other_r.archive_snapshot.entries:
                        other_sol_keys.add((e.solution.sequence, e.solution.modes))

            exclusive_entries = [
                e for e in in_union_entries
                if (e.solution.sequence, e.solution.modes) not in other_sol_keys
            ]
            exclusive_count = len(exclusive_entries)

            # Marginal HV contribution: HV(Union) - HV(Union without this algorithm)
            archive_without = ParetoArchive()
            for other_name, other_r in alg_runs.items():
                if other_name != alg_name:
                    for e in other_r.archive_snapshot.entries:
                        archive_without.add(e.solution, e.schedule, e.objectives)

            hv_without = compute_archive_hypervolume(archive_without, normalizer)
            delta_hv = max(0.0, union_hv - hv_without)
            rel_pct = (delta_hv / union_hv * 100.0) if union_hv > 0.0 else 0.0

            results.append(
                ComplementarityRecord(
                    instance=inst_name,
                    seed=seed,
                    algorithm=alg_name,
                    individual_hv=r.final_hv,
                    individual_archive_size=r.archive_size,
                    union_hv=union_hv,
                    union_archive_size=len(union_archive),
                    solutions_in_union=solutions_in_union,
                    exclusive_solutions_count=exclusive_count,
                    marginal_hv_delta=delta_hv,
                    relative_marginal_hv_pct=rel_pct,
                )
            )

    return results


def run_full_pilot(
    instances: List[Path],
    algorithms: List[str],
    seeds: List[int],
    budget: int = 1000,
    block_size: int = 50,
    output_dir: Path = Path("results/experiments"),
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    all_runs: List[PilotRunRecord] = []
    all_checkpoints: List[CheckpointRecord] = []
    runs_by_key: Dict[Tuple[str, int], Dict[str, PilotRunRecord]] = defaultdict(dict)

    total_runs = len(instances) * len(algorithms) * len(seeds)
    print(f"\n================================================================================")
    print(f"PILOTO EXPERIMENTAL: {len(instances)} INSTANCIAS x {len(algorithms)} ALGORITMOS x {len(seeds)} SEMILLAS = {total_runs} CORRIDAS")
    print(f"Presupuesto: {budget} FE exactas por corrida (0 overshoot)")
    print(f"================================================================================\n")

    t_global_start = time.perf_counter()
    run_count = 0

    for inst_p in instances:
        print(f"\n>>> Procesando Instancia: {inst_p.name} ...")
        for seed in seeds:
            for alg in algorithms:
                run_count += 1
                rec, chks = run_single_pilot_execution(
                    instance_path=inst_p,
                    algorithm=alg,
                    seed=seed,
                    budget=budget,
                    block_size=block_size,
                )
                assert rec.evaluations_used == budget, f"Violation: {rec.evaluations_used} != {budget}"
                assert rec.overshoot == 0, f"Overshoot violation: {rec.overshoot}"

                all_runs.append(rec)
                all_checkpoints.extend(chks)
                runs_by_key[(rec.instance, seed)][alg] = rec

                print(
                    f"  [{run_count:>3}/{total_runs}] {rec.instance:<16} | {alg:<11} | Seed {seed} | "
                    f"HV: {rec.final_hv:.6f} | Arch: {rec.archive_size:>2} | {rec.runtime_seconds:.2f} s"
                )

    t_total_elapsed = time.perf_counter() - t_global_start
    print(f"\n125 Corridas completadas exitosamente en {t_total_elapsed:.2f} s ({t_total_elapsed/total_runs:.2f} s/corrida).")

    # Compute complementarity
    print("\nCalculando analisis de complementariedad y frentes de union...")
    all_comp: List[ComplementarityRecord] = []
    for inst_p in instances:
        comp_records = compute_complementarity_analysis(inst_p, runs_by_key)
        all_comp.extend(comp_records)

    # Export CSVs
    runs_csv = output_dir / "pilot_runs.csv"
    checkpoints_csv = output_dir / "pilot_checkpoints.csv"
    comp_csv = output_dir / "pilot_complementarity.csv"
    summary_csv = output_dir / "pilot_summary_by_instance.csv"

    print(f"Exportando resultados a CSV:")
    # 1. Runs CSV
    with open(runs_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "run_id", "instance", "algorithm", "seed",
            "budget", "evaluations_used", "overshoot",
            "runtime_seconds", "final_hv", "archive_size",
            "unique_solutions_count", "completed", "error"
        ])
        for r in all_runs:
            writer.writerow([
                r.run_id, r.instance, r.algorithm, r.seed,
                r.budget, r.evaluations_used, r.overshoot,
                f"{r.runtime_seconds:.3f}", f"{r.final_hv:.8f}",
                r.archive_size, r.unique_solutions_count,
                r.completed, r.error
            ])
    print(f"  1. {runs_csv} ({len(all_runs)} registros)")

    # 2. Checkpoints CSV
    with open(checkpoints_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["run_id", "instance", "algorithm", "seed", "evaluations", "hypervolume"])
        for c in all_checkpoints:
            writer.writerow([
                c.run_id, c.instance, c.algorithm, c.seed, c.evaluations, f"{c.hypervolume:.8f}"
            ])
    print(f"  2. {checkpoints_csv} ({len(all_checkpoints)} registros)")

    # 3. Complementarity CSV
    with open(comp_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "instance", "seed", "algorithm", "individual_hv",
            "individual_archive_size", "union_hv", "union_archive_size",
            "solutions_in_union", "exclusive_solutions_count",
            "marginal_hv_delta", "relative_marginal_hv_pct"
        ])
        for cp in all_comp:
            writer.writerow([
                cp.instance, cp.seed, cp.algorithm,
                f"{cp.individual_hv:.8f}", cp.individual_archive_size,
                f"{cp.union_hv:.8f}", cp.union_archive_size,
                cp.solutions_in_union, cp.exclusive_solutions_count,
                f"{cp.marginal_hv_delta:.8f}", f"{cp.relative_marginal_hv_pct:.4f}"
            ])
    print(f"  3. {comp_csv} ({len(all_comp)} registros)")

    # 4. Summary CSV
    with open(summary_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "instance", "algorithm",
            "hv_mean", "hv_std", "hv_min", "hv_max",
            "archive_size_mean", "archive_size_std",
            "runtime_mean", "runtime_std",
            "exclusive_sols_mean", "marginal_hv_mean"
        ])
        for inst_p in instances:
            for alg in algorithms:
                matching_runs = [r for r in all_runs if r.instance in (inst_p.name, inst_p.stem) and r.algorithm == alg]
                matching_comp = [c for c in all_comp if c.instance in (inst_p.name, inst_p.stem) and c.algorithm == alg]

                hvs = [r.final_hv for r in matching_runs]
                archs = [r.archive_size for r in matching_runs]
                times = [r.runtime_seconds for r in matching_runs]
                excls = [c.exclusive_solutions_count for c in matching_comp]
                deltas = [c.marginal_hv_delta for c in matching_comp]

                writer.writerow([
                    inst_p.name, alg,
                    f"{statistics.mean(hvs):.6f}", f"{statistics.stdev(hvs) if len(hvs)>1 else 0.0:.6f}",
                    f"{min(hvs):.6f}", f"{max(hvs):.6f}",
                    f"{statistics.mean(archs):.1f}", f"{statistics.stdev(archs) if len(archs)>1 else 0.0:.1f}",
                    f"{statistics.mean(times):.3f}", f"{statistics.stdev(times) if len(times)>1 else 0.0:.3f}",
                    f"{statistics.mean(excls):.2f}", f"{statistics.mean(deltas):.6f}"
                ])
    print(f"  4. {summary_csv} (25 resúmenes instancia-algoritmo)")


if __name__ == "__main__":
    inst_paths = [
        Path("data/experimental/5_10_2-5_1.dzn"),
        Path("data/experimental/10_10_2-5_1.dzn"),
        Path("data/experimental/20_10_2-5_1.dzn"),
        Path("data/experimental/20_20_2-5_1.dzn"),
        Path("data/experimental/30_30_2-5_1.dzn"),
    ]
    algs = ["NSGA-II", "NSGA-II+LS", "MOPSO", "MOEA/D", "SPEA2"]
    seed_list = [0, 1, 2, 3, 4]

    run_full_pilot(inst_paths, algs, seed_list, budget=1000, block_size=50)

