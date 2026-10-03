"""Horizon extension diagnostic for DMAB window size W (Phase 8.3.4).

Evaluates the sliding window dynamics of W in {5, 10} under an extended budget
of 1000 FE (150 FE neutral warm-up + 850 FE adaptive phase = 17 adaptive decisions),
with fixed exploration factor c = sqrt(2).

Protocol:
- Instance: data/experimental/10_10_2-5_1.dzn (N=100)
- Seeds: 42, 100
- Total budget: 1000 FE
- Block size: 50 FE (20 blocks total: 3 warm-up + 17 adaptive)
- Warm-up neutral: active (150 FE across [NSGA-II, MOPSO, NSGA-II+LS])
- Adaptive phase: 850 FE (17 blocks)
- Exploration factor c: math.sqrt(2)
- Window sizes: W=5, W=10
- Total runs: 4
"""

from collections import Counter
from dataclasses import dataclass
import math
from pathlib import Path
import sys
import time
from typing import Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mojssp import (
    AdaptivePortfolioOrchestrator,
    BlockExecutionRecord,
    HypervolumeRewardTracker,
    MOPSOArm,
    NSGA2Arm,
    NSGA2LSArm,
    ObjectiveNormalizer,
    Portfolio,
    SlidingWindowUCB,
    compute_instance_bounds,
    load_dzn,
)


@dataclass
class WindowHorizonRunResult:
    w: int
    c: float
    seed: int
    total_evals: int
    total_blocks: int
    warmup_evals: int
    adaptive_evals: int
    final_hv: float
    final_archive_size: int
    runtime_s: float
    total_fe_by_arm: Dict[str, int]
    adaptive_fe_by_arm: Dict[str, int]
    total_pct_by_arm: Dict[str, float]
    adaptive_pct_by_arm: Dict[str, float]
    pulls_adaptive_by_arm: Dict[str, int]
    cum_reward_adaptive: Dict[str, float]
    mean_reward_adaptive: Dict[str, float]
    adaptive_sequence: List[str]
    history: Tuple[BlockExecutionRecord, ...]


def run_single_window_horizon_trial(
    instance_path: Path,
    w: int,
    c: float,
    seed: int,
    total_budget: int = 1000,
    block_size: int = 50,
    population_size: int = 30,
) -> WindowHorizonRunResult:
    inst = load_dzn(instance_path, validate=True)
    normalizer = ObjectiveNormalizer(compute_instance_bounds(inst))

    # Exact deterministic seed derivation from Phase 8.3 / runner.py
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

    arms = {
        "NSGA-II": arm_nsga2,
        "MOPSO": arm_mopso,
        "NSGA-II+LS": arm_ls,
    }
    portfolio = Portfolio(arms)

    # Fixed canonical registration order for warm-up
    arm_names = ["NSGA-II", "MOPSO", "NSGA-II+LS"]
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
    exec_res = orchestrator.run(
        total_budget=total_budget,
        block_size=block_size,
        neutral_warmup=True,
    )
    runtime_s = time.perf_counter() - t0

    history = exec_res.history
    all_arms = ["NSGA-II", "MOPSO", "NSGA-II+LS"]

    warmup_recs = [r for r in history if r.phase == "warmup"]
    adaptive_recs = [r for r in history if r.phase == "adaptive"]

    warmup_fe = sum(r.evaluations_used for r in warmup_recs)
    adaptive_fe_tot = sum(r.evaluations_used for r in adaptive_recs)

    total_fe = {a: sum(r.evaluations_used for r in history if r.arm_name == a) for a in all_arms}
    adaptive_fe = {a: sum(r.evaluations_used for r in adaptive_recs if r.arm_name == a) for a in all_arms}

    total_pct = {a: (total_fe[a] / total_budget) * 100.0 for a in all_arms}
    adaptive_pct = {a: (adaptive_fe[a] / adaptive_fe_tot) * 100.0 if adaptive_fe_tot > 0 else 0.0 for a in all_arms}

    pulls_adapt = {a: sum(1 for r in adaptive_recs if r.arm_name == a) for a in all_arms}
    cum_rew_adapt = {a: sum(r.reward for r in adaptive_recs if r.arm_name == a) for a in all_arms}
    mean_rew_adapt = {
        a: (cum_rew_adapt[a] / pulls_adapt[a]) if pulls_adapt[a] > 0 else 0.0
        for a in all_arms
    }
    adaptive_seq = [r.arm_name for r in adaptive_recs]

    return WindowHorizonRunResult(
        w=w,
        c=c,
        seed=seed,
        total_evals=exec_res.total_evaluations,
        total_blocks=len(history),
        warmup_evals=warmup_fe,
        adaptive_evals=adaptive_fe_tot,
        final_hv=reward_tracker.current_hv,
        final_archive_size=len(exec_res.global_archive),
        runtime_s=runtime_s,
        total_fe_by_arm=total_fe,
        adaptive_fe_by_arm=adaptive_fe,
        total_pct_by_arm=total_pct,
        adaptive_pct_by_arm=adaptive_pct,
        pulls_adaptive_by_arm=pulls_adapt,
        cum_reward_adaptive=cum_rew_adapt,
        mean_reward_adaptive=mean_rew_adapt,
        adaptive_sequence=adaptive_seq,
        history=history,
    )


def run_all_window_horizon_experiments() -> List[WindowHorizonRunResult]:
    instance_path = Path("data/experimental/10_10_2-5_1.dzn")
    w_values = [5, 10]
    c = math.sqrt(2)
    seeds = [42, 100]

    print("==========================================================================================================")
    print("FASE 8.3.4 — SENSIBILIDAD DE W EN HORIZONTE EXTENDIDO (1000 FE)")
    print("==========================================================================================================")
    print(f"Instancia: {instance_path.name} | Total Budget: 1000 FE | Block Size: 50 FE (20 bloques)")
    print(f"Warm-up neutral: Activo (150 FE = 3 bloques) | Fase Adaptativa: 850 FE (17 bloques)")
    print(f"Valores W: {w_values} | Factor c: sqrt(2) | Semillas: {seeds}")
    print("----------------------------------------------------------------------------------------------------------\n")

    results: List[WindowHorizonRunResult] = []

    for w in w_values:
        for seed in seeds:
            res = run_single_window_horizon_trial(
                instance_path=instance_path,
                w=w,
                c=c,
                seed=seed,
                total_budget=1000,
                block_size=50,
            )
            results.append(res)

    # 1. Tabla de las 4 Ejecuciones
    print("=" * 130)
    print("1. TABLA COMPLETA DE LAS 4 EJECUCIONES (W in {5, 10} x Seed in {42, 100})")
    print("=" * 130)
    hdr1 = (
        f"{'W':<4} {'Seed':<5} {'Warm-up':<9} {'Adapt':<7} "
        f"{'Total FE (N / M / L)':<25} {'Adapt FE (N / M / L)':<25} "
        f"{'Final HV':<11} {'Archive':<8} {'Runtime (s)':<11}"
    )
    print(hdr1)
    print("-" * 130)
    for r in results:
        tot_str = f"{r.total_fe_by_arm['NSGA-II']} / {r.total_fe_by_arm['MOPSO']} / {r.total_fe_by_arm['NSGA-II+LS']}"
        adapt_str = f"{r.adaptive_fe_by_arm['NSGA-II']} / {r.adaptive_fe_by_arm['MOPSO']} / {r.adaptive_fe_by_arm['NSGA-II+LS']}"
        print(
            f"{r.w:<4} {r.seed:<5} {r.warmup_evals:<9} {r.adaptive_evals:<7} "
            f"{tot_str:<25} {adapt_str:<25} "
            f"{r.final_hv:<11.6f} {r.final_archive_size:<8} {r.runtime_s:<11.2f}"
        )

    # 2. Secuencia adaptativa detallada
    print("\n" + "=" * 130)
    print("2. SECUENCIA COMPLETA DE SELECCIÓN ADAPTATIVA (17 BLOQUES)")
    print("=" * 130)
    for r in results:
        seq_short = " -> ".join([arm[0] if arm != "NSGA-II+LS" else "L" for arm in r.adaptive_sequence])
        counts = Counter(r.adaptive_sequence)
        print(f"W={r.w:<2} | Seed={r.seed:<3} | Pulls (N={counts['NSGA-II']}, M={counts['MOPSO']}, L={counts['NSGA-II+LS']}):")
        print(f"  Secuencia: {seq_short}")

    # 3. Detalle de bloques individuales
    print("\n" + "=" * 130)
    print("3. HISTORIAL DETALLADO DE BLOQUES POR EJECUCIÓN")
    print("=" * 130)
    for r in results:
        print(f"\n--- W={r.w}, Seed={r.seed} ---")
        hdr_b = f"{'Block':<6} {'Phase':<9} {'Arm':<12} {'Budget':<8} {'Used':<6} {'HV Before':<11} {'HV After':<11} {'Reward':<10}"
        print(hdr_b)
        print("-" * 80)
        for rec in r.history:
            print(
                f"{rec.block_index:<6} {rec.phase:<9} {rec.arm_name:<12} "
                f"{rec.budget_allocated:<8} {rec.evaluations_used:<6} "
                f"{rec.hv_before:<11.6f} {rec.hv_after:<11.6f} {rec.reward:<10.6f}"
            )

    return results


if __name__ == "__main__":
    run_all_window_horizon_experiments()
