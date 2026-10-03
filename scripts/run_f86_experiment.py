"""Main experiment runner for Phase 8.6: Multi-Instance & Multi-Seed Experiment.

Compares:
- NSGA-II standalone (1000 FE)
- MOPSO standalone (1000 FE)
- NSGA-II+LS standalone (1000 FE)
- Portfolio + DMAB (1000 FE: 150 FE neutral warm-up + 850 FE adaptive, W=10, c=0.07)
across 5 benchmark instances and 10 seeds (0..9) for a total of 200 runs.

Generates:
- results/experiments/f86_runs.csv (200 runs)
- results/experiments/f86_dmab_blocks.csv (850 adaptive blocks)
- results/experiments/f86_pairwise.csv (150 pairwise comparisons)
- results/experiments/f86_summary_by_instance.csv (20 instance-configuration summaries)

DO NOT modify any production code in src/mojssp/*.
"""

import argparse
from collections import Counter
import csv
from dataclasses import dataclass
import math
from pathlib import Path
import statistics
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mojssp import (
    AdaptivePortfolioOrchestrator,
    BlockExecutionRecord,
    HypervolumeRewardTracker,
    MOPSOArm,
    NSGA2Arm,
    NSGA2LSArm,
    ObjectiveNormalizer,
    ParetoArchive,
    Portfolio,
    SlidingWindowUCB,
    compute_archive_hypervolume,
    compute_instance_bounds,
    load_dzn,
)


@dataclass
class StandaloneExecutionResult:
    instance: str
    seed: int
    configuration: str
    budget: int
    evaluations_used: int
    overshoot: int
    final_hv: float
    archive_size: int
    runtime_seconds: float


@dataclass
class PortfolioExecutionResult:
    instance: str
    seed: int
    configuration: str
    budget: int
    evaluations_used: int
    overshoot: int
    final_hv: float
    archive_size: int
    runtime_seconds: float
    warmup_fe: int
    adaptive_fe: int
    nsga2_fe: int
    mopso_fe: int
    nsga2_ls_fe: int
    nsga2_blocks: int
    mopso_blocks: int
    nsga2_ls_blocks: int
    nsga2_budget_share: float
    mopso_budget_share: float
    nsga2_ls_budget_share: float
    selection_sequence: str


@dataclass
class DMABBlockRecord:
    instance: str
    seed: int
    block: int
    phase: str
    selected_arm: str
    budget_allocated: int
    evaluations_used: int
    cumulative_evaluations: int
    hv_before: float
    hv_after: float
    reward: float
    nsga2_pulls: int
    mopso_pulls: int
    nsga2_ls_pulls: int
    nsga2_mean: float
    mopso_mean: float
    nsga2_ls_mean: float
    nsga2_ucb: float
    mopso_ucb: float
    nsga2_ls_ucb: float
    window_size: int
    exploration_factor: float


def run_standalone_execution(
    instance_path: Path,
    seed: int,
    configuration: str,
    budget: int = 1000,
    population_size: int = 30,
) -> StandaloneExecutionResult:
    inst = load_dzn(instance_path, validate=True)
    normalizer = ObjectiveNormalizer(compute_instance_bounds(inst))

    seed_nsga2 = (seed * 10007 + 11) % (2**31 - 1)
    seed_mopso = (seed * 10007 + 23) % (2**31 - 1)
    seed_ls = (seed * 10007 + 37) % (2**31 - 1)

    arm: Any
    if configuration == "NSGA-II":
        arm = NSGA2Arm(inst, population_size=population_size, seed=seed_nsga2)
    elif configuration == "MOPSO":
        arm = MOPSOArm(inst, population_size=population_size, seed=seed_mopso)
    elif configuration == "NSGA-II+LS":
        arm = NSGA2LSArm(
            inst,
            population_size=population_size,
            seed=seed_ls,
            max_ls_iterations=10,
            max_ls_neighbors=10,
        )
    else:
        raise ValueError(f"Unknown configuration: {configuration}")

    t0 = time.perf_counter()
    block_res = arm.run(budget=budget)
    runtime_s = time.perf_counter() - t0

    archive = block_res.solutions
    hv = compute_archive_hypervolume(archive, normalizer)
    overshoot = max(0, block_res.evaluations_used - budget)

    return StandaloneExecutionResult(
        instance=instance_path.name,
        seed=seed,
        configuration=configuration,
        budget=budget,
        evaluations_used=block_res.evaluations_used,
        overshoot=overshoot,
        final_hv=hv,
        archive_size=len(archive),
        runtime_seconds=runtime_s,
    )


def run_portfolio_execution(
    instance_path: Path,
    seed: int,
    total_budget: int = 1000,
    block_size: int = 50,
    w: int = 10,
    c: float = 0.07,
    population_size: int = 30,
) -> Tuple[PortfolioExecutionResult, List[DMABBlockRecord]]:
    inst = load_dzn(instance_path, validate=True)
    normalizer = ObjectiveNormalizer(compute_instance_bounds(inst))

    seed_nsga2 = (seed * 10007 + 11) % (2**31 - 1)
    seed_mopso = (seed * 10007 + 23) % (2**31 - 1)
    seed_ls = (seed * 10007 + 37) % (2**31 - 1)

    arm_nsga2 = NSGA2Arm(inst, population_size=population_size, seed=seed_nsga2)
    arm_mopso = MOPSOArm(inst, population_size=population_size, seed=seed_mopso)
    arm_ls = NSGA2LSArm(
        inst,
        population_size=population_size,
        seed=seed_ls,
        max_ls_iterations=10,
        max_ls_neighbors=10,
    )

    arm_names = ["NSGA-II", "MOPSO", "NSGA-II+LS"]
    arms = {
        "NSGA-II": arm_nsga2,
        "MOPSO": arm_mopso,
        "NSGA-II+LS": arm_ls,
    }
    portfolio = Portfolio(arms)
    dmab = SlidingWindowUCB(
        arm_names=arm_names,
        window_size=w,
        exploration_factor=c,
        seed=seed,
    )
    reward_tracker = HypervolumeRewardTracker(normalizer=normalizer)
    orchestrator = AdaptivePortfolioOrchestrator(
        portfolio=portfolio,
        dmab=dmab,
        reward_tracker=reward_tracker,
    )

    t0 = time.perf_counter()
    cum_evals = 0

    # 1. Warm-up (3 blocks)
    for arm_name in arm_names:
        if cum_evals >= total_budget:
            break
        remaining = total_budget - cum_evals
        block_budget = min(block_size, remaining)
        rec = orchestrator.run_warmup_block(arm_name, block_budget)
        cum_evals += rec.evaluations_used

    warmup_fe = cum_evals

    # 2. Adaptive Phase (17 blocks)
    traces: List[DMABBlockRecord] = []
    adaptive_seq: List[str] = []

    while cum_evals < total_budget:
        remaining = total_budget - cum_evals
        block_budget = min(block_size, remaining)

        stats_before = dmab.get_stats()
        pulls_before = {name: stats_before[name].window_pulls for name in arm_names}
        means_before = {name: stats_before[name].window_mean for name in arm_names}
        ucbs_before = {name: stats_before[name].ucb for name in arm_names}

        rec = orchestrator.step(block_budget)
        cum_evals += rec.evaluations_used
        adaptive_seq.append(rec.arm_name)

        traces.append(
            DMABBlockRecord(
                instance=instance_path.name,
                seed=seed,
                block=rec.block_index,
                phase="adaptive",
                selected_arm=rec.arm_name,
                budget_allocated=block_budget,
                evaluations_used=rec.evaluations_used,
                cumulative_evaluations=cum_evals,
                hv_before=rec.hv_before,
                hv_after=rec.hv_after,
                reward=rec.reward,
                nsga2_pulls=pulls_before["NSGA-II"],
                mopso_pulls=pulls_before["MOPSO"],
                nsga2_ls_pulls=pulls_before["NSGA-II+LS"],
                nsga2_mean=means_before["NSGA-II"],
                mopso_mean=means_before["MOPSO"],
                nsga2_ls_mean=means_before["NSGA-II+LS"],
                nsga2_ucb=ucbs_before["NSGA-II"],
                mopso_ucb=ucbs_before["MOPSO"],
                nsga2_ls_ucb=ucbs_before["NSGA-II+LS"],
                window_size=w,
                exploration_factor=c,
            )
        )

    runtime_s = time.perf_counter() - t0
    adaptive_fe = cum_evals - warmup_fe

    history_adaptive = [r for r in orchestrator.history if r.phase == "adaptive"]
    adaptive_fe_by_arm = {
        a: sum(r.evaluations_used for r in history_adaptive if r.arm_name == a)
        for a in arm_names
    }
    adaptive_blocks_by_arm = {
        a: sum(1 for r in history_adaptive if r.arm_name == a)
        for a in arm_names
    }

    total_fe_by_arm = {
        a: sum(r.evaluations_used for r in orchestrator.history if r.arm_name == a)
        for a in arm_names
    }

    seq_str = " -> ".join([a[0] if a != "NSGA-II+LS" else "L" for a in adaptive_seq])
    overshoot = max(0, cum_evals - total_budget)

    port_res = PortfolioExecutionResult(
        instance=instance_path.name,
        seed=seed,
        configuration="Portfolio+DMAB",
        budget=total_budget,
        evaluations_used=cum_evals,
        overshoot=overshoot,
        final_hv=reward_tracker.current_hv,
        archive_size=len(portfolio.global_archive),
        runtime_seconds=runtime_s,
        warmup_fe=warmup_fe,
        adaptive_fe=adaptive_fe,
        nsga2_fe=adaptive_fe_by_arm["NSGA-II"],
        mopso_fe=adaptive_fe_by_arm["MOPSO"],
        nsga2_ls_fe=adaptive_fe_by_arm["NSGA-II+LS"],
        nsga2_blocks=adaptive_blocks_by_arm["NSGA-II"],
        mopso_blocks=adaptive_blocks_by_arm["MOPSO"],
        nsga2_ls_blocks=adaptive_blocks_by_arm["NSGA-II+LS"],
        nsga2_budget_share=(total_fe_by_arm["NSGA-II"] / cum_evals) * 100.0,
        mopso_budget_share=(total_fe_by_arm["MOPSO"] / cum_evals) * 100.0,
        nsga2_ls_budget_share=(total_fe_by_arm["NSGA-II+LS"] / cum_evals) * 100.0,
        selection_sequence=seq_str,
    )

    return port_res, traces


def run_batch_experiments(
    instances: List[Path],
    seeds: List[int],
    total_budget: int = 1000,
    block_size: int = 50,
    w: int = 10,
    c: float = 0.07,
) -> Tuple[List[Any], List[DMABBlockRecord]]:
    all_runs: List[Any] = []
    all_traces: List[DMABBlockRecord] = []
    configs = ["NSGA-II", "MOPSO", "NSGA-II+LS"]
    total_runs_to_do = len(instances) * len(seeds) * 4

    print(f"Iniciando lote: {len(instances)} instancias x {len(seeds)} semillas x 4 configs = {total_runs_to_do} corridas.")
    t_start = time.perf_counter()

    for inst_p in instances:
        print(f"\n--- Instancia: {inst_p.name} ---")
        for seed in seeds:
            for cfg in configs:
                res_st = run_standalone_execution(
                    instance_path=inst_p,
                    seed=seed,
                    configuration=cfg,
                    budget=total_budget,
                )
                assert res_st.evaluations_used == total_budget
                assert res_st.overshoot == 0
                all_runs.append(res_st)

            res_pt, traces = run_portfolio_execution(
                instance_path=inst_p,
                seed=seed,
                total_budget=total_budget,
                block_size=block_size,
                w=w,
                c=c,
            )
            assert res_pt.evaluations_used == total_budget
            assert res_pt.overshoot == 0
            assert res_pt.warmup_fe == 150
            assert res_pt.adaptive_fe == 850
            assert res_pt.nsga2_fe + res_pt.mopso_fe + res_pt.nsga2_ls_fe == 850
            assert len(traces) == 17

            all_runs.append(res_pt)
            all_traces.extend(traces)
            print(f"  [Seed {seed:>2}] Port HV: {res_pt.final_hv:.6f} | Secuencia: {res_pt.selection_sequence} | Asig: {res_pt.nsga2_blocks}N/{res_pt.mopso_blocks}M/{res_pt.nsga2_ls_blocks}L")

    elapsed = time.perf_counter() - t_start
    print(f"\nLote completado en {elapsed:.2f} s ({elapsed/total_runs_to_do:.2f} s/corrida).")
    return all_runs, all_traces


def export_all_csvs(
    all_runs: List[Any],
    all_traces: List[DMABBlockRecord],
    output_dir: Path,
) -> Tuple[Path, Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    runs_csv_path = output_dir / "f86_runs.csv"
    blocks_csv_path = output_dir / "f86_dmab_blocks.csv"
    pairwise_csv_path = output_dir / "f86_pairwise.csv"
    summary_csv_path = output_dir / "f86_summary_by_instance.csv"

    with open(runs_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "instance", "seed", "configuration",
            "budget", "evaluations_used", "overshoot",
            "final_hv", "archive_size", "runtime_seconds",
            "warmup_fe", "adaptive_fe",
            "nsga2_fe", "mopso_fe", "nsga2_ls_fe",
            "nsga2_blocks", "mopso_blocks", "nsga2_ls_blocks",
            "nsga2_budget_share", "mopso_budget_share", "nsga2_ls_budget_share",
        ])
        for r in all_runs:
            if isinstance(r, StandaloneExecutionResult):
                writer.writerow([
                    r.instance, r.seed, r.configuration,
                    r.budget, r.evaluations_used, r.overshoot,
                    f"{r.final_hv:.8f}", r.archive_size, f"{r.runtime_seconds:.2f}",
                    "", "",
                    r.evaluations_used if r.configuration == "NSGA-II" else 0,
                    r.evaluations_used if r.configuration == "MOPSO" else 0,
                    r.evaluations_used if r.configuration == "NSGA-II+LS" else 0,
                    "", "", "",
                    100.0 if r.configuration == "NSGA-II" else 0.0,
                    100.0 if r.configuration == "MOPSO" else 0.0,
                    100.0 if r.configuration == "NSGA-II+LS" else 0.0,
                ])
            else:
                writer.writerow([
                    r.instance, r.seed, r.configuration,
                    r.budget, r.evaluations_used, r.overshoot,
                    f"{r.final_hv:.8f}", r.archive_size, f"{r.runtime_seconds:.2f}",
                    r.warmup_fe, r.adaptive_fe,
                    r.nsga2_fe, r.mopso_fe, r.nsga2_ls_fe,
                    r.nsga2_blocks, r.mopso_blocks, r.nsga2_ls_blocks,
                    f"{r.nsga2_budget_share:.2f}", f"{r.mopso_budget_share:.2f}", f"{r.nsga2_ls_budget_share:.2f}",
                ])

    with open(blocks_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "instance", "seed", "block", "phase", "selected_arm",
            "budget_allocated", "evaluations_used", "cumulative_evaluations",
            "hv_before", "hv_after", "reward",
            "nsga2_pulls", "mopso_pulls", "nsga2_ls_pulls",
            "nsga2_mean", "mopso_mean", "nsga2_ls_mean",
            "nsga2_ucb", "mopso_ucb", "nsga2_ls_ucb",
            "window_size", "exploration_factor",
        ])
        for tr in all_traces:
            writer.writerow([
                tr.instance, tr.seed, tr.block, tr.phase, tr.selected_arm,
                tr.budget_allocated, tr.evaluations_used, tr.cumulative_evaluations,
                f"{tr.hv_before:.8f}", f"{tr.hv_after:.8f}", f"{tr.reward:.8f}",
                tr.nsga2_pulls, tr.mopso_pulls, tr.nsga2_ls_pulls,
                f"{tr.nsga2_mean:.8f}", f"{tr.mopso_mean:.8f}", f"{tr.nsga2_ls_mean:.8f}",
                f"{tr.nsga2_ucb:.8f}" if not math.isinf(tr.nsga2_ucb) else "inf",
                f"{tr.mopso_ucb:.8f}" if not math.isinf(tr.mopso_ucb) else "inf",
                f"{tr.nsga2_ls_ucb:.8f}" if not math.isinf(tr.nsga2_ls_ucb) else "inf",
                tr.window_size, tr.exploration_factor,
            ])

    run_map: Dict[Tuple[str, int, str], Any] = {
        (r.instance, r.seed, r.configuration): r for r in all_runs
    }
    instances = sorted(list(set(r.instance for r in all_runs)))
    seeds = sorted(list(set(r.seed for r in all_runs)))

    with open(pairwise_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "instance", "seed", "comparison",
            "portfolio_hv", "standalone_hv",
            "absolute_difference", "relative_difference_percent",
        ])
        for inst in instances:
            for s in seeds:
                port = run_map[(inst, s, "Portfolio+DMAB")]
                for std_cfg in ["NSGA-II", "MOPSO", "NSGA-II+LS"]:
                    std = run_map[(inst, s, std_cfg)]
                    diff = port.final_hv - std.final_hv
                    rel_diff = (diff / std.final_hv * 100.0) if std.final_hv > 0 else 0.0
                    writer.writerow([
                        inst, s, f"Portfolio vs {std_cfg}",
                        f"{port.final_hv:.8f}", f"{std.final_hv:.8f}",
                        f"{diff:.8f}", f"{rel_diff:.4f}",
                    ])

    all_configs = ["NSGA-II", "MOPSO", "NSGA-II+LS", "Portfolio+DMAB"]
    with open(summary_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "instance", "configuration", "n",
            "mean_hv", "median_hv", "std_hv", "min_hv", "max_hv",
            "mean_archive_size", "mean_runtime",
        ])
        for inst in instances:
            for cfg in all_configs:
                matching = [r for r in all_runs if r.instance == inst and r.configuration == cfg]
                n = len(matching)
                hvs = [r.final_hv for r in matching]
                archives = [r.archive_size for r in matching]
                runtimes = [r.runtime_seconds for r in matching]

                mean_hv = statistics.mean(hvs)
                median_hv = statistics.median(hvs)
                std_hv = statistics.stdev(hvs) if n > 1 else 0.0
                min_hv = min(hvs)
                max_hv = max(hvs)
                mean_archive = statistics.mean(archives)
                mean_run = statistics.mean(runtimes)

                writer.writerow([
                    inst, cfg, n,
                    f"{mean_hv:.8f}", f"{median_hv:.8f}", f"{std_hv:.8f}",
                    f"{min_hv:.8f}", f"{max_hv:.8f}",
                    f"{mean_archive:.2f}", f"{mean_run:.2f}",
                ])

    return runs_csv_path, blocks_csv_path, pairwise_csv_path, summary_csv_path


def load_and_print_report_from_csv(exp_dir: Path) -> None:
    """Read exported CSVs and print clean ASCII tables."""
    runs_csv = exp_dir / "f86_runs.csv"
    blocks_csv = exp_dir / "f86_dmab_blocks.csv"
    pairwise_csv = exp_dir / "f86_pairwise.csv"
    summary_csv = exp_dir / "f86_summary_by_instance.csv"

    with open(runs_csv, "r", encoding="utf-8") as f:
        runs = list(csv.DictReader(f))
    with open(blocks_csv, "r", encoding="utf-8") as f:
        blocks = list(csv.DictReader(f))
    with open(pairwise_csv, "r", encoding="utf-8") as f:
        pairwise = list(csv.DictReader(f))
    with open(summary_csv, "r", encoding="utf-8") as f:
        summaries = list(csv.DictReader(f))

    instances = sorted(list(set(r["instance"] for r in runs)))
    all_configs = ["NSGA-II", "MOPSO", "NSGA-II+LS", "Portfolio+DMAB"]

    print("\n" + "=" * 130)
    print("REPORTE COMPLETO: FASE 8.6 EXPERIMENTO MULTINSTANCIA + MULTISEMILLA")
    print("=" * 130)

    # TABLA A
    print("\nTABLA A: RESUMEN DE DESEMPENO POR INSTANCIA Y CONFIGURACION (1000 FE)")
    print("-" * 130)
    hdr_a = f"{'Instancia':<18} {'Configuracion':<18} {'N':<3} {'Mean HV':<11} {'Median HV':<11} {'Std HV':<10} {'Min HV':<11} {'Max HV':<11} {'Archive':<8} {'Runtime':<8}"
    print(hdr_a)
    print("-" * 130)

    for s in summaries:
        inst = s["instance"]
        cfg = s["configuration"]
        n = s["n"]
        m_hv = float(s["mean_hv"])
        med_hv = float(s["median_hv"])
        std_hv = float(s["std_hv"])
        min_hv = float(s["min_hv"])
        max_hv = float(s["max_hv"])
        arc = float(s["mean_archive_size"])
        run = float(s["mean_runtime"])
        print(f"{inst:<18} {cfg:<18} {n:<3} {m_hv:<11.6f} {med_hv:<11.6f} {std_hv:<10.6f} {min_hv:<11.6f} {max_hv:<11.6f} {arc:<8.1f} {run:<8.2f}s")
    print("-" * 130)

    # TABLA B
    print("\nTABLA B: DIFERENCIAS EMPAREJADAS (PORTFOLIO - STANDALONE) POR INSTANCIA")
    print("-" * 130)
    hdr_b = f"{'Instancia':<18} {'Comparacion':<26} {'Media dHV':<12} {'Mediana dHV':<13} {'Std dHV':<11} {'Min dHV':<12} {'Max dHV':<12} {'% Relativo Medio':<18}"
    print(hdr_b)
    print("-" * 130)

    for inst in instances:
        for std_cfg in ["NSGA-II", "MOPSO", "NSGA-II+LS"]:
            comp_name = f"Portfolio vs {std_cfg}"
            matching = [p for p in pairwise if p["instance"] == inst and p["comparison"] == comp_name]
            diffs = [float(p["absolute_difference"]) for p in matching]
            rel_diffs = [float(p["relative_difference_percent"]) for p in matching]
            m_d = statistics.mean(diffs)
            med_d = statistics.median(diffs)
            s_d = statistics.stdev(diffs) if len(diffs) > 1 else 0.0
            min_d = min(diffs)
            max_d = max(diffs)
            m_rel = statistics.mean(rel_diffs)
            print(f"{inst:<18} {comp_name:<26} {m_d:<+12.6f} {med_d:<+13.6f} {s_d:<11.6f} {min_d:<+12.6f} {max_d:<+12.6f} {m_rel:<+18.2f}%")
        print("-" * 130)

    # TABLA C
    print("\nTABLA C: ASIGNACION ADAPTATIVA DEL PRESUPUESTO POR INSTANCIA (10 Semillas, 850 FE Adaptativo = 17 Bloques)")
    print("-" * 130)
    hdr_c = f"{'Instancia':<18} {'Arm':<12} {'Media FE':<10} {'Std FE':<9} {'Min FE':<8} {'Max FE':<8} {'Media Bloques':<15} {'% Presupuesto Total':<22}"
    print(hdr_c)
    print("-" * 130)

    arm_names = ["NSGA-II", "MOPSO", "NSGA-II+LS"]
    for inst in instances:
        port_runs = [r for r in runs if r["instance"] == inst and r["configuration"] == "Portfolio+DMAB"]
        for arm in arm_names:
            if arm == "NSGA-II":
                fes = [int(r["nsga2_fe"]) for r in port_runs]
                blks = [int(r["nsga2_blocks"]) for r in port_runs]
                shares = [float(r["nsga2_budget_share"]) for r in port_runs]
            elif arm == "MOPSO":
                fes = [int(r["mopso_fe"]) for r in port_runs]
                blks = [int(r["mopso_blocks"]) for r in port_runs]
                shares = [float(r["mopso_budget_share"]) for r in port_runs]
            else:
                fes = [int(r["nsga2_ls_fe"]) for r in port_runs]
                blks = [int(r["nsga2_ls_blocks"]) for r in port_runs]
                shares = [float(r["nsga2_ls_budget_share"]) for r in port_runs]

            m_fe = statistics.mean(fes)
            s_fe = statistics.stdev(fes) if len(fes) > 1 else 0.0
            min_fe = min(fes)
            max_fe = max(fes)
            m_blk = statistics.mean(blks)
            m_share = statistics.mean(shares)
            print(f"{inst:<18} {arm:<12} {m_fe:<10.1f} {s_fe:<9.1f} {min_fe:<8} {max_fe:<8} {m_blk:<15.2f} {m_share:<22.1f}%")
        print("-" * 130)

    # TABLA D
    print("\nTABLA D: PATRONES DE ASIGNACION TOTAL (NSGA-II / MOPSO / NSGA-II+LS en FE)")
    print("-" * 130)
    for inst in instances:
        port_runs = [r for r in runs if r["instance"] == inst and r["configuration"] == "Portfolio+DMAB"]
        patterns = [
            f"{int(r['nsga2_fe']) + 50}/{int(r['mopso_fe']) + 50}/{int(r['nsga2_ls_fe']) + 50}"
            for r in port_runs
        ]
        cnt = Counter(patterns)
        pat_str = ", ".join([f"{p}: {c} semillas ({c/len(port_runs)*100:.0f}%)" for p, c in cnt.most_common()])
        print(f"{inst:<18} -> {pat_str}")

    # TABLA E
    print("\nTABLA E: REWARD TOTAL ACUMULADO VS BLOQUES SELECCIONADOS POR ARM")
    print("-" * 130)
    hdr_e = f"{'Instancia':<18} {'Arm':<12} {'Reward Acumulado':<18} {'Bloques Totales':<18} {'Reward / Bloque':<18}"
    print(hdr_e)
    print("-" * 130)

    for inst in instances:
        inst_traces = [tr for tr in blocks if tr["instance"] == inst]
        for arm in arm_names:
            arm_traces = [tr for tr in inst_traces if tr["selected_arm"] == arm]
            tot_rew = sum(float(tr["reward"]) for tr in arm_traces)
            tot_blks = len(arm_traces)
            rew_per_blk = (tot_rew / tot_blks) if tot_blks > 0 else 0.0
            print(f"{inst:<18} {arm:<12} {tot_rew:<18.6f} {tot_blks:<18} {rew_per_blk:<18.6f}")
        print("-" * 130)


def run_f86_pilot() -> bool:
    print("================================================================================")
    print("F8.6 PILOTO DE PRUEBA: 1 INSTANCIA x 2 SEMILLAS x 4 CONFIGS = 8 RUNS")
    print("================================================================================")
    inst_path = Path("data/experimental/5_10_2-5_1.dzn")
    seeds = [0, 1]

    runs, traces = run_batch_experiments([inst_path], seeds, total_budget=1000)
    assert len(runs) == 8
    assert len(traces) == 34

    for r in runs:
        assert r.evaluations_used == 1000
        assert r.overshoot == 0

    p0_1, tr0_1 = run_portfolio_execution(inst_path, seed=0, total_budget=1000)
    p0_2, tr0_2 = run_portfolio_execution(inst_path, seed=0, total_budget=1000)
    assert p0_1.final_hv == p0_2.final_hv
    assert p0_1.selection_sequence == p0_2.selection_sequence

    print("\n>>> PILOTO SUPERADO EXITOSAMENTE: Cero overshoot, 1000 FE exactas, reproducibilidad bit a bit.")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Phase 8.6 experiments.")
    parser.add_argument("--pilot-only", action="store_true", help="Run only the 8-run pilot.")
    parser.add_argument("--report-only", action="store_true", help="Only load and print report from CSVs.")
    args = parser.parse_args()

    out_dir = Path("results/experiments")

    if args.report_only:
        load_and_print_report_from_csv(out_dir)
        return

    pilot_passed = run_f86_pilot()
    if not pilot_passed:
        print("El piloto fallo. Abortando corrida completa.")
        sys.exit(1)

    if args.pilot_only:
        print("Modo --pilot-only finalizado.")
        return

    instances = [
        Path("data/experimental/5_10_2-5_1.dzn"),
        Path("data/experimental/10_10_2-5_1.dzn"),
        Path("data/experimental/15_10_2-5_1.dzn"),
        Path("data/experimental/20_10_2-5_1.dzn"),
        Path("data/experimental/20_20_2-5_1.dzn"),
    ]
    seeds = list(range(10))

    print("\n================================================================================")
    print("F8.6 EXPERIMENTO COMPLETO: 5 INSTANCIAS x 10 SEMILLAS x 4 CONFIGS = 200 RUNS")
    print("================================================================================")

    all_runs, all_traces = run_batch_experiments(instances, seeds, total_budget=1000)
    runs_csv, blocks_csv, pairwise_csv, summary_csv = export_all_csvs(all_runs, all_traces, out_dir)

    print("\nArchivos exportados exitosamente:")
    print(f"  1. {runs_csv}")
    print(f"  2. {blocks_csv}")
    print(f"  3. {pairwise_csv}")
    print(f"  4. {summary_csv}")

    load_and_print_report_from_csv(out_dir)


if __name__ == "__main__":
    main()
