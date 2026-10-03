"""Sensitivity analysis of DMAB hyperparameters W and c (Phase 8.3.3).

Evaluates the influence of sliding window size W in {3, 5, 10} and exploration factor
c in {0.5, 1.0, sqrt(2)} on adaptive budget allocation under neutral warm-up.

Fixed Protocol:
- Instance: data/experimental/10_10_2-5_1.dzn (N=100)
- Seeds: 42, 100
- Total budget: 500 FE
- Block size: 50 FE
- Warm-up neutral: active (150 FE across [NSGA-II, MOPSO, NSGA-II+LS])
- Adaptive phase: 350 FE (7 blocks)
- Configurations: 3 window sizes x 3 exploration factors x 2 seeds = 18 runs
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
class SensitivityRunResult:
    w: int
    c: float
    c_label: str
    seed: int
    total_evals: int
    total_blocks: int
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


def run_single_sensitivity_trial(
    instance_path: Path,
    w: int,
    c: float,
    c_label: str,
    seed: int,
    total_budget: int = 500,
    block_size: int = 50,
    population_size: int = 30,
) -> SensitivityRunResult:
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

    total_fe = {a: sum(r.evaluations_used for r in history if r.arm_name == a) for a in all_arms}
    adaptive_fe = {a: sum(r.evaluations_used for r in history if r.arm_name == a and r.phase == "adaptive") for a in all_arms}

    total_pct = {a: (total_fe[a] / total_budget) * 100.0 for a in all_arms}
    adapt_budget = total_budget - 150  # 3 arms x 50 FE warm-up
    adaptive_pct = {a: (adaptive_fe[a] / adapt_budget) * 100.0 for a in all_arms}

    adaptive_recs = [r for r in history if r.phase == "adaptive"]
    pulls_adapt = {a: sum(1 for r in adaptive_recs if r.arm_name == a) for a in all_arms}
    cum_rew_adapt = {a: sum(r.reward for r in adaptive_recs if r.arm_name == a) for a in all_arms}
    mean_rew_adapt = {
        a: (cum_rew_adapt[a] / pulls_adapt[a]) if pulls_adapt[a] > 0 else 0.0
        for a in all_arms
    }
    adaptive_seq = [r.arm_name for r in adaptive_recs]

    return SensitivityRunResult(
        w=w,
        c=c,
        c_label=c_label,
        seed=seed,
        total_evals=exec_res.total_evaluations,
        total_blocks=exec_res.total_blocks,
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


def run_all_sensitivity_experiments():
    instance_path = Path("data/experimental/10_10_2-5_1.dzn")
    w_values = [3, 5, 10]
    c_configs = [
        (0.5, "0.5"),
        (1.0, "1.0"),
        (math.sqrt(2), "sqrt(2)"),
    ]
    seeds = [42, 100]

    print("==========================================================================================================")
    print("FASE 8.3.3 — ANÁLISIS DE SENSIBILIDAD DE HIPERPARÁMETROS W Y c DE DMAB")
    print("==========================================================================================================")
    print(f"Instancia: {instance_path.name} | Total Budget: 500 FE | Block Size: 50 FE")
    print(f"Warm-up neutral: Activo (150 FE = 3 bloques) | Fase Adaptativa: 350 FE (7 bloques)")
    print(f"Valores W: {w_values} | Valores c: {[cfg[1] for cfg in c_configs]} | Semillas: {seeds}")
    print("----------------------------------------------------------------------------------------------------------\n")

    all_results: List[SensitivityRunResult] = []

    for w in w_values:
        for c, c_label in c_configs:
            for seed in seeds:
                res = run_single_sensitivity_trial(
                    instance_path=instance_path,
                    w=w,
                    c=c,
                    c_label=c_label,
                    seed=seed,
                )
                all_results.append(res)

    # 1. Tabla Completa de las 18 Ejecuciones
    print("=" * 120)
    print("1. TABLA COMPLETA POR EJECUCIÓN (18 RUNS: W x c x seed)")
    print("=" * 120)
    hdr1 = f"{'W':<4} {'c':<8} {'Seed':<5} {'Total FE (N / M / L)':<28} {'Adapt FE (350 FE)':<22} {'Final HV':<11} {'Archive':<8} {'Secuencia Adaptativa (7 bloques)'}"
    print(hdr1)
    print("-" * 120)
    for r in all_results:
        tot_str = f"{r.total_fe_by_arm['NSGA-II']} / {r.total_fe_by_arm['MOPSO']} / {r.total_fe_by_arm['NSGA-II+LS']}"
        adapt_str = f"{r.adaptive_fe_by_arm['NSGA-II']} / {r.adaptive_fe_by_arm['MOPSO']} / {r.adaptive_fe_by_arm['NSGA-II+LS']}"
        seq_short = " -> ".join([arm[0] if arm != "NSGA-II+LS" else "L" for arm in r.adaptive_sequence])
        print(f"{r.w:<4} {r.c_label:<8} {r.seed:<5} {tot_str:<28} {adapt_str:<22} {r.final_hv:<11.6f} {r.final_archive_size:<8} {seq_short}")

    # 2. Tabla Agregada por Configuración (Media sobre las 2 semillas)
    print("\n" + "=" * 120)
    print("2. TABLA AGREGADA POR CONFIGURACIÓN (Media sobre 2 semillas)")
    print("=" * 120)
    hdr2 = f"{'W':<4} {'c':<8} {'NSGA2 FE (tot)':<16} {'MOPSO FE (tot)':<16} {'LS FE (tot)':<16} {'NSGA2 FE (adapt)':<18} {'MOPSO (adapt)':<15} {'LS (adapt)':<15} {'HV medio':<10}"
    print(hdr2)
    print("-" * 120)

    # Group by (w, c_label)
    from collections import defaultdict
    grouped = defaultdict(list)
    for r in all_results:
        grouped[(r.w, r.c_label)].append(r)

    for (w, c_label), runs in grouped.items():
        mean_tot_nsga = sum(r.total_fe_by_arm["NSGA-II"] for r in runs) / len(runs)
        mean_tot_mopso = sum(r.total_fe_by_arm["MOPSO"] for r in runs) / len(runs)
        mean_tot_ls = sum(r.total_fe_by_arm["NSGA-II+LS"] for r in runs) / len(runs)

        mean_adapt_nsga = sum(r.adaptive_fe_by_arm["NSGA-II"] for r in runs) / len(runs)
        mean_adapt_mopso = sum(r.adaptive_fe_by_arm["MOPSO"] for r in runs) / len(runs)
        mean_adapt_ls = sum(r.adaptive_fe_by_arm["NSGA-II+LS"] for r in runs) / len(runs)

        mean_hv = sum(r.final_hv for r in runs) / len(runs)

        print(f"{w:<4} {c_label:<8} {mean_tot_nsga:<16.1f} {mean_tot_mopso:<16.1f} {mean_tot_ls:<16.1f} {mean_adapt_nsga:<18.1f} {mean_adapt_mopso:<15.1f} {mean_adapt_ls:<15.1f} {mean_hv:<10.6f}")

    # 3. Prueba de Reproducibilidad
    print("\n" + "=" * 120)
    print("3. VERIFICACIÓN PUNTUAL DE REPRODUCIBILIDAD (Configuración W=3, c=0.5, Seed=42)")
    print("=" * 120)
    rep1 = run_single_sensitivity_trial(instance_path, w=3, c=0.5, c_label="0.5", seed=42)
    rep2 = run_single_sensitivity_trial(instance_path, w=3, c=0.5, c_label="0.5", seed=42)
    identical_evals = rep1.total_evals == rep2.total_evals
    identical_blocks = rep1.total_blocks == rep2.total_blocks
    identical_hv = abs(rep1.final_hv - rep2.final_hv) < 1e-12
    identical_seq = rep1.adaptive_sequence == rep2.adaptive_sequence
    identical_alloc = rep1.total_fe_by_arm == rep2.total_fe_by_arm
    print(f"Total evals idénticos: {identical_evals} ({rep1.total_evals})")
    print(f"Total blocks idénticos: {identical_blocks} ({rep1.total_blocks})")
    print(f"Final HV idéntico: {identical_hv} ({rep1.final_hv:.8f})")
    print(f"Secuencia adaptativa idéntica: {identical_seq} ({rep1.adaptive_sequence})")
    print(f"Asignación idéntica: {identical_alloc} ({rep1.total_fe_by_arm})")


if __name__ == "__main__":
    run_all_sensitivity_experiments()
