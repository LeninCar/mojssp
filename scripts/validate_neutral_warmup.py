"""Validation experiment for neutral warm-up in algorithm portfolio (Phase 8.3.2).

Tests whether neutral warm-up eliminates the deterministic 40/30/30 initialization artifact
observed in Phase 8.3 and Phase 8.3.1.

Experimental Conditions on instance 10_10_2-5_1 (N=100) under seeds 42 and 100:
- Condition A: Warm-up order [NSGA-II, MOPSO, NSGA-II+LS]
- Condition B: Warm-up order [MOPSO, NSGA-II+LS, NSGA-II]
- Condition C: Warm-up order [NSGA-II+LS, NSGA-II, MOPSO]
"""

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
class ValidationRunResult:
    condition_label: str
    arm_order: List[str]
    seed: int
    warmup_rewards: List[Tuple[str, float]]
    adaptive_rewards: List[Tuple[str, float]]
    full_sequence: List[str]
    adaptive_sequence: List[str]
    total_fe_by_arm: Dict[str, int]
    warmup_fe_by_arm: Dict[str, int]
    adaptive_fe_by_arm: Dict[str, int]
    total_pct_by_arm: Dict[str, float]
    adaptive_pct_by_arm: Dict[str, float]
    final_hv: float
    total_evals: int
    total_blocks: int
    runtime_s: float
    history: Tuple[BlockExecutionRecord, ...]


def run_neutral_validation(
    instance_path: Path,
    condition_label: str,
    arm_order: List[str],
    seed: int,
    total_budget: int = 500,
    block_size: int = 50,
    population_size: int = 30,
    window_size: int = 10,
    exploration_factor: float = math.sqrt(2),
) -> ValidationRunResult:
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

    # Selector initialized with arm_order to dictate warm-up execution order
    dmab = SlidingWindowUCB(
        arm_names=arm_order,
        window_size=window_size,
        exploration_factor=exploration_factor,
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

    warmup_rewards = [(r.arm_name, r.reward) for r in history if r.phase == "warmup"]
    adaptive_rewards = [(r.arm_name, r.reward) for r in history if r.phase == "adaptive"]
    full_sequence = [r.arm_name for r in history]
    adaptive_sequence = [r.arm_name for r in history if r.phase == "adaptive"]

    total_fe = {a: sum(r.evaluations_used for r in history if r.arm_name == a) for a in all_arms}
    warmup_fe = {a: sum(r.evaluations_used for r in history if r.arm_name == a and r.phase == "warmup") for a in all_arms}
    adaptive_fe = {a: sum(r.evaluations_used for r in history if r.arm_name == a and r.phase == "adaptive") for a in all_arms}

    total_pct = {a: (total_fe[a] / total_budget) * 100.0 for a in all_arms}
    adaptive_budget = total_budget - sum(warmup_fe.values())
    adaptive_pct = {a: (adaptive_fe[a] / adaptive_budget) * 100.0 if adaptive_budget > 0 else 0.0 for a in all_arms}

    return ValidationRunResult(
        condition_label=condition_label,
        arm_order=arm_order,
        seed=seed,
        warmup_rewards=warmup_rewards,
        adaptive_rewards=adaptive_rewards,
        full_sequence=full_sequence,
        adaptive_sequence=adaptive_sequence,
        total_fe_by_arm=total_fe,
        warmup_fe_by_arm=warmup_fe,
        adaptive_fe_by_arm=adaptive_fe,
        total_pct_by_arm=total_pct,
        adaptive_pct_by_arm=adaptive_pct,
        final_hv=reward_tracker.current_hv,
        total_evals=exec_res.total_evaluations,
        total_blocks=exec_res.total_blocks,
        runtime_s=runtime_s,
        history=history,
    )


def main():
    instance_path = Path("data/experimental/10_10_2-5_1.dzn")
    seeds = [42, 100]

    conditions = [
        ("A", ["NSGA-II", "MOPSO", "NSGA-II+LS"]),
        ("B", ["MOPSO", "NSGA-II+LS", "NSGA-II"]),
        ("C", ["NSGA-II+LS", "NSGA-II", "MOPSO"]),
    ]

    print("=========================================================================================")
    print("FASE 8.3.2 — EXPERIMENTO DE VALIDACIÓN DEL WARM-UP NEUTRAL")
    print("=========================================================================================")
    print(f"Instancia: {instance_path.name} | Presupuesto: 500 FE | Bloque: 50 FE | W: 10 | c: sqrt(2)")
    print(f"Semillas: {seeds}")
    print("-----------------------------------------------------------------------------------------\n")

    results: List[ValidationRunResult] = []
    for cond_label, arm_order in conditions:
        for seed in seeds:
            res = run_neutral_validation(
                instance_path=instance_path,
                condition_label=cond_label,
                arm_order=arm_order,
                seed=seed,
            )
            results.append(res)

    # 1. Resumen General Comparativo
    print("=" * 110)
    print("1. TABLA RESUMEN COMPARATIVA (ASIGNACIONES TOTALES Y ADAPTATIVAS)")
    print("=" * 110)
    hdr = f"{'Cond':<5} {'Seed':<5} {'First Arm':<12} {'Total FE: NSGA2 / MOPSO / LS':<35} {'Adaptive FE (350 FE)':<25} {'Final HV':<10}"
    print(hdr)
    print("-" * 110)
    for r in results:
        tot_str = f"{r.total_fe_by_arm['NSGA-II']} ({r.total_pct_by_arm['NSGA-II']:.0f}%) / {r.total_fe_by_arm['MOPSO']} ({r.total_pct_by_arm['MOPSO']:.0f}%) / {r.total_fe_by_arm['NSGA-II+LS']} ({r.total_pct_by_arm['NSGA-II+LS']:.0f}%)"
        adapt_str = f"{r.adaptive_fe_by_arm['NSGA-II']} / {r.adaptive_fe_by_arm['MOPSO']} / {r.adaptive_fe_by_arm['NSGA-II+LS']}"
        first_arm = r.arm_order[0]
        print(f"{r.condition_label:<5} {r.seed:<5} {first_arm:<12} {tot_str:<35} {adapt_str:<25} {r.final_hv:<10.6f}")

    # 2. Recompensas del Warm-up vs Fase Adaptativa
    print("\n" + "=" * 110)
    print("2. DESGLOSE DE RECOMPENSAS: WARM-UP vs FASE ADAPTATIVA")
    print("=" * 110)
    for r in results:
        print(f"\n[{r.condition_label} / Seed {r.seed}] Orden warm-up: {' -> '.join(r.arm_order)}")
        print("  Recompensas Warm-up (NO enviadas a DMAB):")
        for arm, rew in r.warmup_rewards:
            print(f"    {arm:12s} -> reward = {rew:.6f}")
        print("  Secuencia Adaptativa (7 bloques, 350 FE):")
        adapt_seq_str = " -> ".join([f"{arm} (r={rew:.4f})" for arm, rew in r.adaptive_rewards])
        print(f"    {adapt_seq_str}")

    # 3. Secuencia Completa Bloque a Bloque
    print("\n" + "=" * 110)
    print("3. DETALLE BLOQUE A BLOQUE COMPLETO")
    print("=" * 110)
    for r in results:
        print(f"\n--- Condición {r.condition_label} | Semilla {r.seed} | Primer Arm: {r.arm_order[0]} ---")
        b_hdr = f"{'Block':<6} {'Phase':<10} {'Arm':<12} {'HV Before':<12} {'HV After':<12} {'Reward':<12}"
        print(b_hdr)
        print("-" * len(b_hdr))
        for b in r.history:
            print(f"{b.block_index:<6} {b.phase:<10} {b.arm_name:<12} {b.hv_before:<12.6f} {b.hv_after:<12.6f} {b.reward:<12.6f}")


if __name__ == "__main__":
    main()
