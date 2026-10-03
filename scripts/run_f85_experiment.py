"""Main experiment runner for Phase 8.5: Portfolio vs Standalone + budget adaptation.

Executes:
- NSGA-II standalone (1000 FE)
- MOPSO standalone (1000 FE)
- NSGA-II+LS standalone (1000 FE)
- Portfolio + DMAB (1000 FE: 150 FE neutral warm-up + 850 FE adaptive, W=10, c=0.07)
across seeds 42 and 100 on instance data/experimental/10_10_2-5_1.dzn.

Exports:
- results/experiments/f85_portfolio_vs_standalone.csv (consolidated summary)
- results/experiments/f85_dmab_allocation.csv (block-by-block trace of DMAB decisions)

DO NOT modify any production code in src/mojssp/*.
"""

import csv
from dataclasses import dataclass
import math
from pathlib import Path
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
    experiment_id: str
    instance: str
    seed: int
    configuration: str
    total_budget: int
    evaluations_used: int
    final_hv: float
    archive_size: int
    runtime_s: float
    genetic_evaluations: Optional[int] = None
    ls_evaluations: Optional[int] = None


@dataclass
class PortfolioExecutionResult:
    experiment_id: str
    instance: str
    seed: int
    configuration: str
    total_budget: int
    evaluations_used: int
    final_hv: float
    archive_size: int
    runtime_s: float
    dmab_c: float
    dmab_window: int
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
class DMABBlockTraceRecord:
    instance: str
    seed: int
    block: int
    selected_arm: str
    budget_allocated: int
    cumulative_fe: int
    hv_before: float
    hv_after: float
    reward: float
    nsga2_pulls: int
    mopso_pulls: int
    nsga2_ls_pulls: int
    nsga2_ucb: float
    mopso_ucb: float
    nsga2_ls_ucb: float


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

    gen_evals = None
    ls_evals = None
    if configuration == "NSGA-II+LS":
        ls_evals = arm.ls_evaluations
        gen_evals = arm.total_evaluations - arm.ls_evaluations

    exp_id = f"{instance_path.stem}_{configuration}_s{seed}_{budget}FE"

    return StandaloneExecutionResult(
        experiment_id=exp_id,
        instance=instance_path.name,
        seed=seed,
        configuration=configuration,
        total_budget=budget,
        evaluations_used=block_res.evaluations_used,
        final_hv=hv,
        archive_size=len(archive),
        runtime_s=runtime_s,
        genetic_evaluations=gen_evals,
        ls_evaluations=ls_evals,
    )


def run_portfolio_execution(
    instance_path: Path,
    seed: int,
    total_budget: int = 1000,
    block_size: int = 50,
    w: int = 10,
    c: float = 0.07,
    population_size: int = 30,
) -> Tuple[PortfolioExecutionResult, List[DMABBlockTraceRecord]]:
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
    traces: List[DMABBlockTraceRecord] = []

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
    adaptive_seq = []
    while cum_evals < total_budget:
        remaining = total_budget - cum_evals
        block_budget = min(block_size, remaining)

        stats_before = {name: dmab.get_stats()[name] for name in arm_names}
        pulls_before = {name: stats_before[name].window_pulls for name in arm_names}
        ucbs_before = {name: stats_before[name].ucb for name in arm_names}

        rec = orchestrator.step(block_budget)
        cum_evals += rec.evaluations_used
        adaptive_seq.append(rec.arm_name)

        traces.append(
            DMABBlockTraceRecord(
                instance=instance_path.name,
                seed=seed,
                block=rec.block_index,
                selected_arm=rec.arm_name,
                budget_allocated=block_budget,
                cumulative_fe=cum_evals,
                hv_before=rec.hv_before,
                hv_after=rec.hv_after,
                reward=rec.reward,
                nsga2_pulls=pulls_before["NSGA-II"],
                mopso_pulls=pulls_before["MOPSO"],
                nsga2_ls_pulls=pulls_before["NSGA-II+LS"],
                nsga2_ucb=ucbs_before["NSGA-II"],
                mopso_ucb=ucbs_before["MOPSO"],
                nsga2_ls_ucb=ucbs_before["NSGA-II+LS"],
            )
        )

    runtime_s = time.perf_counter() - t0
    adaptive_fe = cum_evals - warmup_fe

    history = orchestrator.history
    total_fe_by_arm = {
        a: sum(r.evaluations_used for r in history if r.arm_name == a)
        for a in arm_names
    }
    adaptive_blocks_by_arm = {
        a: sum(1 for r in traces if r.selected_arm == a)
        for a in arm_names
    }

    seq_str = " -> ".join([a[0] if a != "NSGA-II+LS" else "L" for a in adaptive_seq])
    exp_id = f"{instance_path.stem}_Portfolio+DMAB_s{seed}_{total_budget}FE"

    port_res = PortfolioExecutionResult(
        experiment_id=exp_id,
        instance=instance_path.name,
        seed=seed,
        configuration="Portfolio+DMAB",
        total_budget=total_budget,
        evaluations_used=cum_evals,
        final_hv=reward_tracker.current_hv,
        archive_size=len(portfolio.global_archive),
        runtime_s=runtime_s,
        dmab_c=c,
        dmab_window=w,
        warmup_fe=warmup_fe,
        adaptive_fe=adaptive_fe,
        nsga2_fe=total_fe_by_arm["NSGA-II"],
        mopso_fe=total_fe_by_arm["MOPSO"],
        nsga2_ls_fe=total_fe_by_arm["NSGA-II+LS"],
        nsga2_blocks=adaptive_blocks_by_arm["NSGA-II"],
        mopso_blocks=adaptive_blocks_by_arm["MOPSO"],
        nsga2_ls_blocks=adaptive_blocks_by_arm["NSGA-II+LS"],
        nsga2_budget_share=(total_fe_by_arm["NSGA-II"] / cum_evals) * 100.0,
        mopso_budget_share=(total_fe_by_arm["MOPSO"] / cum_evals) * 100.0,
        nsga2_ls_budget_share=(total_fe_by_arm["NSGA-II+LS"] / cum_evals) * 100.0,
        selection_sequence=seq_str,
    )

    return port_res, traces


def run_all_f85_experiments() -> Tuple[Path, Path]:
    instance_path = Path("data/experimental/10_10_2-5_1.dzn")
    seeds = [42, 100]
    total_budget = 1000

    print("=" * 130)
    print("FASE 8.5 — EXPERIMENTO PRINCIPAL: PORTFOLIO VS STANDALONE + ADAPTACIÓN DEL PRESUPUESTO")
    print("=" * 130)
    print(f"Instancia: {instance_path.name} | Presupuesto Total: {total_budget} FE | Semillas: {seeds}")
    print("Parámetros Portfolio: Block=50 FE | Warm-up=150 FE (3 bloques) | Adaptativo=850 FE (17 bloques) | W=10 | c=0.07")
    print("-" * 130)

    standalone_results: List[StandaloneExecutionResult] = []
    portfolio_results: List[PortfolioExecutionResult] = []
    all_traces: List[DMABBlockTraceRecord] = []

    for seed in seeds:
        print(f"\nEjecutando corridas para Seed {seed}...")
        for alg in ["NSGA-II", "MOPSO", "NSGA-II+LS"]:
            print(f"  -> Ejecutando {alg} standalone...")
            st_res = run_standalone_execution(instance_path, seed=seed, configuration=alg, budget=total_budget)
            standalone_results.append(st_res)

        print(f"  -> Ejecutando Portfolio + DMAB...")
        pt_res, traces = run_portfolio_execution(
            instance_path,
            seed=seed,
            total_budget=total_budget,
            block_size=50,
            w=10,
            c=0.07,
        )
        portfolio_results.append(pt_res)
        all_traces.extend(traces)

    # Export CSVs
    exp_dir = Path("results/experiments")
    exp_dir.mkdir(parents=True, exist_ok=True)
    main_csv_path = exp_dir / "f85_portfolio_vs_standalone.csv"
    alloc_csv_path = exp_dir / "f85_dmab_allocation.csv"

    # 1. Main CSV
    with open(main_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "experiment_id", "instance", "seed", "configuration",
            "total_budget", "evaluations_used", "final_hv", "archive_size", "runtime_s",
            "dmab_c", "dmab_window", "warmup_fe", "adaptive_fe",
            "nsga2_fe", "mopso_fe", "nsga2_ls_fe",
            "nsga2_blocks", "mopso_blocks", "nsga2_ls_blocks",
            "nsga2_budget_share", "mopso_budget_share", "nsga2_ls_budget_share",
            "selection_sequence",
        ])

        for st in standalone_results:
            writer.writerow([
                st.experiment_id, st.instance, st.seed, st.configuration,
                st.total_budget, st.evaluations_used, f"{st.final_hv:.8f}", st.archive_size, f"{st.runtime_s:.2f}",
                "", "", "", "",
                st.evaluations_used if st.configuration == "NSGA-II" else 0,
                st.evaluations_used if st.configuration == "MOPSO" else 0,
                st.evaluations_used if st.configuration == "NSGA-II+LS" else 0,
                "", "", "",
                100.0 if st.configuration == "NSGA-II" else 0.0,
                100.0 if st.configuration == "MOPSO" else 0.0,
                100.0 if st.configuration == "NSGA-II+LS" else 0.0,
                "",
            ])

        for pt in portfolio_results:
            writer.writerow([
                pt.experiment_id, pt.instance, pt.seed, pt.configuration,
                pt.total_budget, pt.evaluations_used, f"{pt.final_hv:.8f}", pt.archive_size, f"{pt.runtime_s:.2f}",
                pt.dmab_c, pt.dmab_window, pt.warmup_fe, pt.adaptive_fe,
                pt.nsga2_fe, pt.mopso_fe, pt.nsga2_ls_fe,
                pt.nsga2_blocks, pt.mopso_blocks, pt.nsga2_ls_blocks,
                f"{pt.nsga2_budget_share:.2f}", f"{pt.mopso_budget_share:.2f}", f"{pt.nsga2_ls_budget_share:.2f}",
                pt.selection_sequence,
            ])

    # 2. Allocation CSV
    with open(alloc_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "instance", "seed", "block", "selected_arm",
            "budget_allocated", "cumulative_fe",
            "hv_before", "hv_after", "reward",
            "nsga2_pulls", "mopso_pulls", "nsga2_ls_pulls",
            "nsga2_ucb", "mopso_ucb", "nsga2_ls_ucb",
        ])
        for tr in all_traces:
            writer.writerow([
                tr.instance, tr.seed, tr.block, tr.selected_arm,
                tr.budget_allocated, tr.cumulative_fe,
                f"{tr.hv_before:.8f}", f"{tr.hv_after:.8f}", f"{tr.reward:.8f}",
                tr.nsga2_pulls, tr.mopso_pulls, tr.nsga2_ls_pulls,
                f"{tr.nsga2_ucb:.8f}" if not math.isinf(tr.nsga2_ucb) else "inf",
                f"{tr.mopso_ucb:.8f}" if not math.isinf(tr.mopso_ucb) else "inf",
                f"{tr.nsga2_ls_ucb:.8f}" if not math.isinf(tr.nsga2_ls_ucb) else "inf",
            ])

    print("\n" + "=" * 130)
    print("RESUMEN CONSOLIDADO: F8.5 PORTFOLIO VS STANDALONE")
    print("=" * 130)
    hdr = f"{'Configuration':<18} {'Seed':<5} {'Budget':<7} {'FE Used':<8} {'Final HV':<11} {'Archive':<8} {'Runtime (s)':<11} {'FE Allocation (N / M / L)':<28}"
    print(hdr)
    print("-" * 130)

    for seed in seeds:
        for st in [s for s in standalone_results if s.seed == seed]:
            fe_alloc = f"{st.evaluations_used if st.configuration == 'NSGA-II' else 0} / {st.evaluations_used if st.configuration == 'MOPSO' else 0} / {st.evaluations_used if st.configuration == 'NSGA-II+LS' else 0}"
            print(f"{st.configuration:<18} {st.seed:<5} {st.total_budget:<7} {st.evaluations_used:<8} {st.final_hv:<11.6f} {st.archive_size:<8} {st.runtime_s:<11.2f} {fe_alloc:<28}")

        pt = next(p for p in portfolio_results if p.seed == seed)
        fe_alloc_pt = f"{pt.nsga2_fe} / {pt.mopso_fe} / {pt.nsga2_ls_fe} ({pt.nsga2_budget_share:.0f}% / {pt.mopso_budget_share:.0f}% / {pt.nsga2_ls_budget_share:.0f}%)"
        print(f"{pt.configuration:<18} {pt.seed:<5} {pt.total_budget:<7} {pt.evaluations_used:<8} {pt.final_hv:<11.6f} {pt.archive_size:<8} {pt.runtime_s:<11.2f} {fe_alloc_pt:<28}")
        print(f"  -> Secuencia DMAB: {pt.selection_sequence}")
        print("-" * 130)

    print(f"\nArchivos generados exitosamente:")
    print(f"  - {main_csv_path}")
    print(f"  - {alloc_csv_path}")

    return main_csv_path, alloc_csv_path


if __name__ == "__main__":
    run_all_f85_experiments()
