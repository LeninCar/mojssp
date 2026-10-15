"""P7 Active Cooperation Expanded Empirical Validation Runner.

Executes and manages the 350-run experimental campaign across:
- 10 base development instances (profile='base', assigned_split='development')
- 5 master random seeds (42, 101, 202, 303, 404)
- 7 strictly controlled conditions:
    1. MOEA/D Standalone
    2. NSGA-II Standalone
    3. SPEA2 Standalone
    4. Portfolio Round-Robin (Passive)
    5. Portfolio SW-UCB (Passive, c=0.01)
    6. Portfolio SW-UCB (Cooperative, c=0.01, kappa=2, min_block=6)
    7. Portfolio Cooperative Fixed-Sequence Control (paired sequence from Condition 5)

Methodological constraints:
- Exactly 1000 evaluations per run (20 blocks of 50 FE, fe_overshoot == 0).
- Strict resume support: avoids duplicating runs and loads previous checkpoints.
- Pairwise reproduction: Condition 7 reproduces the exact sequence of Condition 5.
- Leave-One-Out marginal HV contribution computation.
- Canonical seed derivation per arm and orchestrator.
- Zero holdout usage.
"""

import argparse
import csv
import json
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

# Ensure src is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mojssp.arms import NSGA2Arm
from mojssp.cooperation import CooperativePortfolio, InjectionResult
from mojssp.dmab import RoundRobinSelector, SlidingWindowUCB
from mojssp.evaluator import Evaluator, ObjectiveValues
from mojssp.hypervolume import compute_archive_hypervolume
from mojssp.instance import Instance
from mojssp.io import load_dzn
from mojssp.moead import MOEADArm
from mojssp.normalization import compute_instance_bounds, ObjectiveNormalizer
from mojssp.pareto_archive import ArchiveEntry, ParetoArchive
from mojssp.provenance import (
    ProvenanceObservingPortfolio,
    ProvenanceTracker,
    compute_genotype_id,
    compute_objective_key,
)
from mojssp.reward import HypervolumeRewardTracker
from mojssp.spea2 import SPEA2Arm

# 10 verified base development instances
BASE_INSTANCES = [
    ("base_c01_5x5_b03", Path("data/generated/expanded_200/base_c01_5x5_b03.dzn")),
    ("base_c01_5x5_b05", Path("data/generated/expanded_200/base_c01_5x5_b05.dzn")),
    ("base_c02_10x10_b03", Path("data/generated/expanded_200/base_c02_10x10_b03.dzn")),
    ("base_c02_10x10_b04", Path("data/generated/expanded_200/base_c02_10x10_b04.dzn")),
    ("base_c03_20x10_b04", Path("data/generated/expanded_200/base_c03_20x10_b04.dzn")),
    ("base_c04_10x20_b04", Path("data/generated/expanded_200/base_c04_10x20_b04.dzn")),
    ("base_c05_20x20_b03", Path("data/generated/expanded_200/base_c05_20x20_b03.dzn")),
    ("base_c06_30x20_b03", Path("data/generated/expanded_200/base_c06_30x20_b03.dzn")),
    ("base_c07_40x20_b03", Path("data/generated/expanded_200/base_c07_40x20_b03.dzn")),
    ("base_c08_50x50_b03", Path("data/generated/expanded_200/base_c08_50x50_b03.dzn")),
]

SEEDS = [42, 101, 202, 303, 404]

CONDITIONS_ORDER = [
    "MOEAD_Standalone",
    "NSGA2_Standalone",
    "SPEA2_Standalone",
    "Portfolio_RoundRobin_Passive",
    "Portfolio_SWUCB_Passive",
    "Portfolio_SWUCB_Cooperative",
    "Portfolio_Coop_FixedSequence",
]

BUDGET = 1000
BLOCK_SIZE = 50
POP_SIZE = 30
WINDOW_SIZE = 10
UCB_C = 0.01
MIN_COOP_BLOCK = 6
MAX_INJECTIONS = 2

trapezoid = getattr(np, "trapezoid", getattr(np, "trapz", None))


def compute_leave_one_out_contributions(
    archive: ParetoArchive,
    tracker: ProvenanceTracker,
    normalizer: ObjectiveNormalizer,
    arm_names: List[str],
) -> Dict[str, float]:
    """Calculate Leave-One-Out (LOO) marginal HV contribution for each arm.
    
    Marginal HV(A) = HV(GPA) - HV(GPA \\ S_A)
    where S_A is the set of solutions whose first_observed_arm is A.
    """
    total_hv = compute_archive_hypervolume(archive, normalizer)
    loo_contributions = {}
    
    # Map each entry in archive to first discovered arm
    arm_sol_keys = {arm: set() for arm in arm_names}
    for entry in archive.entries:
        gid = compute_genotype_id(entry.solution)
        info = tracker.solutions.get(gid)
        discovered_by = info.first_observed_arm if info else "unknown"
        if discovered_by in arm_sol_keys:
            arm_sol_keys[discovered_by].add(gid)

    arm_key_map = {"MOEA/D": "moead", "NSGA-II": "nsga2", "SPEA2": "spea2"}
    for arm in arm_names:
        key_suffix = arm_key_map.get(arm, arm.lower().replace("/", "").replace("-", ""))
        sols_to_exclude = arm_sol_keys[arm]
        if not sols_to_exclude:
            loo_contributions[f"marginal_loo_hv_{key_suffix}"] = 0.0
            continue
        
        # Build reduced archive
        reduced_arch = ParetoArchive()
        for entry in archive.entries:
            gid = compute_genotype_id(entry.solution)
            if gid not in sols_to_exclude:
                reduced_arch.add_entry(entry)
                
        reduced_hv = compute_archive_hypervolume(reduced_arch, normalizer)
        marginal = max(0.0, total_hv - reduced_hv)
        loo_contributions[f"marginal_loo_hv_{key_suffix}"] = round(marginal, 8)
        
    return loo_contributions


def run_standalone_condition(
    instance: Instance,
    inst_name: str,
    normalizer: ObjectiveNormalizer,
    cond_name: str,
    seed: int,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any]]:
    """Execute a standalone algorithm in 20 blocks of 50 FE."""
    seed_offset = {"MOEAD_Standalone": 17, "NSGA2_Standalone": 29, "SPEA2_Standalone": 43}[cond_name]
    arm_type = {"MOEAD_Standalone": "MOEA/D", "NSGA2_Standalone": "NSGA-II", "SPEA2_Standalone": "SPEA2"}[cond_name]
    arm_seed = (seed * 10007 + seed_offset) % (2**31 - 1)

    if arm_type == "MOEA/D":
        arm = MOEADArm(instance, population_size=POP_SIZE, seed=arm_seed)
    elif arm_type == "NSGA-II":
        arm = NSGA2Arm(instance, population_size=POP_SIZE, max_generations=None, seed=arm_seed)
    else:
        arm = SPEA2Arm(instance, population_size=POP_SIZE, archive_size=POP_SIZE, seed=arm_seed)

    rt = HypervolumeRewardTracker(normalizer=normalizer)
    t0 = time.perf_counter()
    fe_consumed = 0
    checkpoints = [(0, 0.0)]
    block_records = []

    for b_idx in range(BUDGET // BLOCK_SIZE):
        hv_before = rt.current_hv
        b_res = arm.run(BLOCK_SIZE)
        fe_consumed += b_res.evaluations_used
        rew = rt.compute_reward(arm.current_archive)
        hv_after = rt.current_hv
        checkpoints.append((fe_consumed, hv_after))

        rec = {
            "instance_name": inst_name,
            "seed": seed,
            "condition": cond_name,
            "cooperation_enabled": False,
            "block_index": b_idx,
            "phase": "standalone",
            "arm_selected": arm_type,
            "budget_allocated": BLOCK_SIZE,
            "evaluations_used": b_res.evaluations_used,
            "cumulative_fe": fe_consumed,
            "reward": rew,
            "hv_before": hv_before,
            "hv_after": hv_after,
            "injections_offered": 0,
            "injections_accepted": 0,
            "injections_rejected_dup": 0,
            "injections_rejected_dom": 0,
            "injections_surviving": 0,
            "injection_time_seconds": 0.0,
        }
        block_records.append(rec)

    runtime = time.perf_counter() - t0
    final_arch = arm.current_archive

    fe_vals = [pt[0] for pt in checkpoints]
    hv_vals = [pt[1] for pt in checkpoints]
    auc_val = trapezoid(hv_vals, fe_vals) / float(BUDGET)

    unique_genotypes = len(set(compute_genotype_id(e.solution) for e in final_arch.entries))
    unique_objs = len(set(compute_objective_key(e.objectives) for e in final_arch.entries))

    summary = {
        "instance_name": inst_name,
        "seed": seed,
        "condition": cond_name,
        "cooperation_enabled": False,
        "runtime_seconds": round(runtime, 4),
        "total_fe": fe_consumed,
        "fe_overshoot": fe_consumed - BUDGET,
        "final_hv": round(rt.current_hv, 8),
        "auc_hv": round(auc_val, 8),
        "archive_size": len(final_arch),
        "unique_genotypes": unique_genotypes,
        "unique_objectives": unique_objs,
        "moead_fe": fe_consumed if arm_type == "MOEA/D" else 0,
        "nsga2_fe": fe_consumed if arm_type == "NSGA-II" else 0,
        "spea2_fe": fe_consumed if arm_type == "SPEA2" else 0,
        "active_sols_moead": len(final_arch) if arm_type == "MOEA/D" else 0,
        "active_sols_nsga2": len(final_arch) if arm_type == "NSGA-II" else 0,
        "active_sols_spea2": len(final_arch) if arm_type == "SPEA2" else 0,
        "marginal_loo_hv_moead": np.nan,
        "marginal_loo_hv_nsga2": np.nan,
        "marginal_loo_hv_spea2": np.nan,
        "total_injections_offered": 0,
        "total_injections_accepted": 0,
        "total_injections_rejected_dup": 0,
        "total_injections_rejected_dom": 0,
        "total_injections_surviving": 0,
        "total_injection_time_seconds": 0.0,
    }

    trace_data = {
        "summary": summary,
        "checkpoints": checkpoints,
        "active_solutions": [
            {
                "genotype_id": compute_genotype_id(e.solution),
                "objective_key": list(compute_objective_key(e.objectives)),
                "discovered_by_arm": arm_type,
            }
            for e in final_arch.entries
        ],
    }

    return summary, block_records, trace_data


def run_portfolio_autonomous(
    instance: Instance,
    inst_name: str,
    normalizer: ObjectiveNormalizer,
    cond_name: str,
    seed: int,
    coop_enabled: bool,
    c_val: Optional[float],
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any], List[str]]:
    """Execute an autonomous portfolio condition (Round-Robin, SW-UCB Passive, or SW-UCB Cooperative)."""
    seed_moead = (seed * 10007 + 17) % (2**31 - 1)
    seed_nsga2 = (seed * 10007 + 29) % (2**31 - 1)
    seed_spea2 = (seed * 10007 + 43) % (2**31 - 1)

    arm_m = MOEADArm(instance, population_size=POP_SIZE, seed=seed_moead)
    arm_n = NSGA2Arm(instance, population_size=POP_SIZE, max_generations=None, seed=seed_nsga2)
    arm_s = SPEA2Arm(instance, population_size=POP_SIZE, archive_size=POP_SIZE, seed=seed_spea2)

    tracker = ProvenanceTracker()
    arms_dict = {"MOEA/D": arm_m, "NSGA-II": arm_n, "SPEA2": arm_s}
    portfolio = CooperativePortfolio(
        arms=arms_dict,
        tracker=tracker,
        cooperation_enabled=coop_enabled,
        observability_enabled=True,
        max_injections_per_block=MAX_INJECTIONS,
        min_cooperation_block=MIN_COOP_BLOCK,
        seed=seed,
    )
    arm_names = ["MOEA/D", "NSGA-II", "SPEA2"]

    if c_val is not None:
        selector = SlidingWindowUCB(
            arm_names=arm_names,
            window_size=WINDOW_SIZE,
            exploration_factor=c_val,
            seed=seed,
        )
    else:
        selector = RoundRobinSelector(arm_names=arm_names)

    rt = HypervolumeRewardTracker(normalizer=normalizer)
    t0 = time.perf_counter()
    fe_consumed = 0
    block_records = []
    checkpoints = [(0, 0.0)]
    executed_sequence = []

    # 1. Warmup (Blocks 0-2, 150 FE)
    for w_arm in arm_names:
        hv_before = rt.current_hv
        b_res = portfolio.run_arm(w_arm, budget=BLOCK_SIZE)
        fe_consumed += b_res.evaluations_used
        rew = rt.compute_reward(portfolio.global_archive)
        hv_after = rt.current_hv
        if hasattr(selector, "initialize_arm"):
            selector.initialize_arm(w_arm)
        checkpoints.append((fe_consumed, hv_after))
        executed_sequence.append(w_arm)

        rec = {
            "instance_name": inst_name,
            "seed": seed,
            "condition": cond_name,
            "cooperation_enabled": coop_enabled,
            "block_index": len(block_records),
            "phase": "warmup",
            "arm_selected": w_arm,
            "budget_allocated": BLOCK_SIZE,
            "evaluations_used": b_res.evaluations_used,
            "cumulative_fe": fe_consumed,
            "reward": rew,
            "hv_before": hv_before,
            "hv_after": hv_after,
            "injections_offered": 0,
            "injections_accepted": 0,
            "injections_rejected_dup": 0,
            "injections_rejected_dom": 0,
            "injections_surviving": 0,
            "injection_time_seconds": 0.0,
        }
        block_records.append(rec)

    # 2. Subsequent blocks (probe and adaptive)
    while fe_consumed < BUDGET:
        b_budget = min(BLOCK_SIZE, BUDGET - fe_consumed)
        current_b_idx = len(block_records)

        chosen_arm = selector.select_arm()
        executed_sequence.append(chosen_arm)
        is_probe = False
        if hasattr(selector, "is_in_initial_probe"):
            is_probe = selector.is_in_initial_probe(chosen_arm)
        elif hasattr(selector, "get_adaptive_pulls"):
            is_probe = (selector.get_adaptive_pulls(chosen_arm) == 0)

        inj_before_len = len(portfolio.injection_history)
        hv_before = rt.current_hv

        b_res = portfolio.run_arm(chosen_arm, budget=b_budget)
        fe_consumed += b_res.evaluations_used
        rew = rt.compute_reward(portfolio.global_archive)
        hv_after = rt.current_hv
        selector.update(chosen_arm, rew)
        checkpoints.append((fe_consumed, hv_after))

        inj_rec = None
        if len(portfolio.injection_history) > inj_before_len:
            inj_rec = portfolio.injection_history[-1]

        rec = {
            "instance_name": inst_name,
            "seed": seed,
            "condition": cond_name,
            "cooperation_enabled": coop_enabled,
            "block_index": current_b_idx,
            "phase": "initial_probe" if is_probe else "adaptive",
            "arm_selected": chosen_arm,
            "budget_allocated": b_budget,
            "evaluations_used": b_res.evaluations_used,
            "cumulative_fe": fe_consumed,
            "reward": rew,
            "hv_before": hv_before,
            "hv_after": hv_after,
            "injections_offered": inj_rec.offered_count if inj_rec else 0,
            "injections_accepted": inj_rec.accepted_count if inj_rec else 0,
            "injections_rejected_dup": inj_rec.rejected_duplicate_count if inj_rec else 0,
            "injections_rejected_dom": inj_rec.rejected_dominated_count if inj_rec else 0,
            "injections_surviving": inj_rec.surviving_in_population if inj_rec else 0,
            "injection_time_seconds": inj_rec.injection_time_seconds if inj_rec else 0.0,
        }
        block_records.append(rec)

    runtime = time.perf_counter() - t0
    final_arch = portfolio.global_archive

    fe_vals = [pt[0] for pt in checkpoints]
    hv_vals = [pt[1] for pt in checkpoints]
    auc_val = trapezoid(hv_vals, fe_vals) / float(BUDGET)

    unique_genotypes = len(set(compute_genotype_id(e.solution) for e in final_arch.entries))
    unique_objs = len(set(compute_objective_key(e.objectives) for e in final_arch.entries))

    prov_summary = tracker.get_arm_contribution_summary()
    active_sols_by_arm = {
        arm: prov_summary.get(arm, {}).get("currently_active_in_archive", 0)
        for arm in arm_names
    }

    fe_by_arm = {
        "MOEA/D": sum(r["evaluations_used"] for r in block_records if r["arm_selected"] == "MOEA/D"),
        "NSGA-II": sum(r["evaluations_used"] for r in block_records if r["arm_selected"] == "NSGA-II"),
        "SPEA2": sum(r["evaluations_used"] for r in block_records if r["arm_selected"] == "SPEA2"),
    }

    loo_contribs = compute_leave_one_out_contributions(final_arch, tracker, normalizer, arm_names)

    tot_inj_offered = sum(r.offered_count for r in portfolio.injection_history)
    tot_inj_accepted = sum(r.accepted_count for r in portfolio.injection_history)
    tot_inj_dup = sum(r.rejected_duplicate_count for r in portfolio.injection_history)
    tot_inj_dom = sum(r.rejected_dominated_count for r in portfolio.injection_history)
    tot_inj_surv = sum(r.surviving_in_population for r in portfolio.injection_history)
    tot_inj_time = sum(r.injection_time_seconds for r in portfolio.injection_history)

    summary = {
        "instance_name": inst_name,
        "seed": seed,
        "condition": cond_name,
        "cooperation_enabled": coop_enabled,
        "runtime_seconds": round(runtime, 4),
        "total_fe": fe_consumed,
        "fe_overshoot": fe_consumed - BUDGET,
        "final_hv": round(rt.current_hv, 8),
        "auc_hv": round(auc_val, 8),
        "archive_size": len(final_arch),
        "unique_genotypes": unique_genotypes,
        "unique_objectives": unique_objs,
        "moead_fe": fe_by_arm["MOEA/D"],
        "nsga2_fe": fe_by_arm["NSGA-II"],
        "spea2_fe": fe_by_arm["SPEA2"],
        "active_sols_moead": active_sols_by_arm["MOEA/D"],
        "active_sols_nsga2": active_sols_by_arm["NSGA-II"],
        "active_sols_spea2": active_sols_by_arm["SPEA2"],
        "marginal_loo_hv_moead": loo_contribs["marginal_loo_hv_moead"],
        "marginal_loo_hv_nsga2": loo_contribs["marginal_loo_hv_nsga2"],
        "marginal_loo_hv_spea2": loo_contribs["marginal_loo_hv_spea2"],
        "total_injections_offered": tot_inj_offered,
        "total_injections_accepted": tot_inj_accepted,
        "total_injections_rejected_dup": tot_inj_dup,
        "total_injections_rejected_dom": tot_inj_dom,
        "total_injections_surviving": tot_inj_surv,
        "total_injection_time_seconds": round(tot_inj_time, 6),
    }

    trace_data = tracker.export_traces_to_dict()
    trace_data["summary"] = summary
    trace_data["executed_sequence"] = executed_sequence
    trace_data["injection_history"] = [
        {
            "arm_name": r.arm_name,
            "offered_count": r.offered_count,
            "accepted_count": r.accepted_count,
            "rejected_duplicate_count": r.rejected_duplicate_count,
            "rejected_dominated_count": r.rejected_dominated_count,
            "accepted_genotype_ids": list(r.accepted_genotype_ids),
            "surviving_in_population": r.surviving_in_population,
            "injection_time_seconds": r.injection_time_seconds,
        }
        for r in portfolio.injection_history
    ]

    return summary, block_records, trace_data, executed_sequence


def run_cooperative_fixed_sequence(
    instance: Instance,
    inst_name: str,
    normalizer: ObjectiveNormalizer,
    seed: int,
    sequence: List[str],
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any]]:
    """Execute cooperative portfolio using an externally supplied paired sequence."""
    assert len(sequence) == BUDGET // BLOCK_SIZE, f"Sequence length {len(sequence)} != 20"

    seed_moead = (seed * 10007 + 17) % (2**31 - 1)
    seed_nsga2 = (seed * 10007 + 29) % (2**31 - 1)
    seed_spea2 = (seed * 10007 + 43) % (2**31 - 1)

    arm_m = MOEADArm(instance, population_size=POP_SIZE, seed=seed_moead)
    arm_n = NSGA2Arm(instance, population_size=POP_SIZE, max_generations=None, seed=seed_nsga2)
    arm_s = SPEA2Arm(instance, population_size=POP_SIZE, archive_size=POP_SIZE, seed=seed_spea2)

    tracker = ProvenanceTracker()
    arms_dict = {"MOEA/D": arm_m, "NSGA-II": arm_n, "SPEA2": arm_s}
    portfolio = CooperativePortfolio(
        arms=arms_dict,
        tracker=tracker,
        cooperation_enabled=True,
        observability_enabled=True,
        max_injections_per_block=MAX_INJECTIONS,
        min_cooperation_block=MIN_COOP_BLOCK,
        seed=seed,
    )
    arm_names = ["MOEA/D", "NSGA-II", "SPEA2"]
    rt = HypervolumeRewardTracker(normalizer=normalizer)

    t0 = time.perf_counter()
    fe_consumed = 0
    block_records = []
    checkpoints = [(0, 0.0)]

    for b_idx, chosen_arm in enumerate(sequence):
        b_budget = min(BLOCK_SIZE, BUDGET - fe_consumed)
        phase = "warmup" if b_idx < 3 else ("initial_probe" if b_idx < 6 else "adaptive_fixed_seq")

        inj_before_len = len(portfolio.injection_history)
        hv_before = rt.current_hv

        b_res = portfolio.run_arm(chosen_arm, budget=b_budget)
        fe_consumed += b_res.evaluations_used
        rew = rt.compute_reward(portfolio.global_archive)
        hv_after = rt.current_hv
        checkpoints.append((fe_consumed, hv_after))

        inj_rec = None
        if len(portfolio.injection_history) > inj_before_len:
            inj_rec = portfolio.injection_history[-1]

        rec = {
            "instance_name": inst_name,
            "seed": seed,
            "condition": "Portfolio_Coop_FixedSequence",
            "cooperation_enabled": True,
            "block_index": b_idx,
            "phase": phase,
            "arm_selected": chosen_arm,
            "budget_allocated": b_budget,
            "evaluations_used": b_res.evaluations_used,
            "cumulative_fe": fe_consumed,
            "reward": rew,
            "hv_before": hv_before,
            "hv_after": hv_after,
            "injections_offered": inj_rec.offered_count if inj_rec else 0,
            "injections_accepted": inj_rec.accepted_count if inj_rec else 0,
            "injections_rejected_dup": inj_rec.rejected_duplicate_count if inj_rec else 0,
            "injections_rejected_dom": inj_rec.rejected_dominated_count if inj_rec else 0,
            "injections_surviving": inj_rec.surviving_in_population if inj_rec else 0,
            "injection_time_seconds": inj_rec.injection_time_seconds if inj_rec else 0.0,
        }
        block_records.append(rec)

    runtime = time.perf_counter() - t0
    final_arch = portfolio.global_archive

    fe_vals = [pt[0] for pt in checkpoints]
    hv_vals = [pt[1] for pt in checkpoints]
    auc_val = trapezoid(hv_vals, fe_vals) / float(BUDGET)

    unique_genotypes = len(set(compute_genotype_id(e.solution) for e in final_arch.entries))
    unique_objs = len(set(compute_objective_key(e.objectives) for e in final_arch.entries))

    prov_summary = tracker.get_arm_contribution_summary()
    active_sols_by_arm = {
        arm: prov_summary.get(arm, {}).get("currently_active_in_archive", 0)
        for arm in arm_names
    }

    fe_by_arm = {
        "MOEA/D": sum(r["evaluations_used"] for r in block_records if r["arm_selected"] == "MOEA/D"),
        "NSGA-II": sum(r["evaluations_used"] for r in block_records if r["arm_selected"] == "NSGA-II"),
        "SPEA2": sum(r["evaluations_used"] for r in block_records if r["arm_selected"] == "SPEA2"),
    }

    loo_contribs = compute_leave_one_out_contributions(final_arch, tracker, normalizer, arm_names)

    tot_inj_offered = sum(r.offered_count for r in portfolio.injection_history)
    tot_inj_accepted = sum(r.accepted_count for r in portfolio.injection_history)
    tot_inj_dup = sum(r.rejected_duplicate_count for r in portfolio.injection_history)
    tot_inj_dom = sum(r.rejected_dominated_count for r in portfolio.injection_history)
    tot_inj_surv = sum(r.surviving_in_population for r in portfolio.injection_history)
    tot_inj_time = sum(r.injection_time_seconds for r in portfolio.injection_history)

    summary = {
        "instance_name": inst_name,
        "seed": seed,
        "condition": "Portfolio_Coop_FixedSequence",
        "cooperation_enabled": True,
        "runtime_seconds": round(runtime, 4),
        "total_fe": fe_consumed,
        "fe_overshoot": fe_consumed - BUDGET,
        "final_hv": round(rt.current_hv, 8),
        "auc_hv": round(auc_val, 8),
        "archive_size": len(final_arch),
        "unique_genotypes": unique_genotypes,
        "unique_objectives": unique_objs,
        "moead_fe": fe_by_arm["MOEA/D"],
        "nsga2_fe": fe_by_arm["NSGA-II"],
        "spea2_fe": fe_by_arm["SPEA2"],
        "active_sols_moead": active_sols_by_arm["MOEA/D"],
        "active_sols_nsga2": active_sols_by_arm["NSGA-II"],
        "active_sols_spea2": active_sols_by_arm["SPEA2"],
        "marginal_loo_hv_moead": loo_contribs["marginal_loo_hv_moead"],
        "marginal_loo_hv_nsga2": loo_contribs["marginal_loo_hv_nsga2"],
        "marginal_loo_hv_spea2": loo_contribs["marginal_loo_hv_spea2"],
        "total_injections_offered": tot_inj_offered,
        "total_injections_accepted": tot_inj_accepted,
        "total_injections_rejected_dup": tot_inj_dup,
        "total_injections_rejected_dom": tot_inj_dom,
        "total_injections_surviving": tot_inj_surv,
        "total_injection_time_seconds": round(tot_inj_time, 6),
    }

    trace_data = tracker.export_traces_to_dict()
    trace_data["summary"] = summary
    trace_data["paired_sequence_used"] = sequence
    trace_data["injection_history"] = [
        {
            "arm_name": r.arm_name,
            "offered_count": r.offered_count,
            "accepted_count": r.accepted_count,
            "rejected_duplicate_count": r.rejected_duplicate_count,
            "rejected_dominated_count": r.rejected_dominated_count,
            "accepted_genotype_ids": list(r.accepted_genotype_ids),
            "surviving_in_population": r.surviving_in_population,
            "injection_time_seconds": r.injection_time_seconds,
        }
        for r in portfolio.injection_history
    ]

    return summary, block_records, trace_data


def run_single_experiment(
    instance: Instance,
    inst_name: str,
    normalizer: ObjectiveNormalizer,
    cond_name: str,
    seed: int,
    passive_sequence: Optional[List[str]] = None,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any], Optional[List[str]]]:
    """Execute a single run given condition and parameters."""
    if cond_name.endswith("_Standalone"):
        summary, blocks, trace = run_standalone_condition(instance, inst_name, normalizer, cond_name, seed)
        return summary, blocks, trace, None
    elif cond_name == "Portfolio_RoundRobin_Passive":
        summary, blocks, trace, seq = run_portfolio_autonomous(
            instance, inst_name, normalizer, cond_name, seed, coop_enabled=False, c_val=None
        )
        return summary, blocks, trace, seq
    elif cond_name == "Portfolio_SWUCB_Passive":
        summary, blocks, trace, seq = run_portfolio_autonomous(
            instance, inst_name, normalizer, cond_name, seed, coop_enabled=False, c_val=UCB_C
        )
        return summary, blocks, trace, seq
    elif cond_name == "Portfolio_SWUCB_Cooperative":
        summary, blocks, trace, seq = run_portfolio_autonomous(
            instance, inst_name, normalizer, cond_name, seed, coop_enabled=True, c_val=UCB_C
        )
        return summary, blocks, trace, seq
    elif cond_name == "Portfolio_Coop_FixedSequence":
        if passive_sequence is None:
            raise ValueError(f"Passive sequence required for {cond_name} on {inst_name} seed={seed}")
        summary, blocks, trace = run_cooperative_fixed_sequence(
            instance, inst_name, normalizer, seed, passive_sequence
        )
        return summary, blocks, trace, None
    else:
        raise ValueError(f"Unknown condition {cond_name}")


def main() -> None:
    parser = argparse.ArgumentParser(description="P7 Expanded Empirical Validation Runner")
    parser.add_argument("--test-integration", action="store_true", help="Run a minimal integration test (1 instance, 1 seed, all 7 conditions)")
    parser.add_argument("--output-dir", type=str, default="results/pareto_cooperation_research/p7_validation", help="Directory to store outputs")
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    traces_dir = out_dir / "traces"
    traces_dir.mkdir(parents=True, exist_ok=True)

    summary_csv = out_dir / "p7_validation_summary.csv"
    blocks_csv = out_dir / "p7_validation_blocks_detail.csv"

    # Load existing summaries to support resumption
    completed_runs = set()
    existing_summaries = []
    if summary_csv.exists():
        with open(summary_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                completed_runs.add((row["instance_name"], int(row["seed"]), row["condition"]))
                existing_summaries.append(row)
        print(f"Loaded {len(completed_runs)} previously completed runs from {summary_csv}")

    instances_to_run = BASE_INSTANCES[:1] if args.test_integration else BASE_INSTANCES
    seeds_to_run = SEEDS[:1] if args.test_integration else SEEDS

    total_target_runs = len(instances_to_run) * len(seeds_to_run) * len(CONDITIONS_ORDER)
    print(f"=== P7 EXPANDED VALIDATION RUNNER ===")
    print(f"Target runs: {total_target_runs} (Integration test: {args.test_integration})")
    print(f"Instances: {[i[0] for i in instances_to_run]}")
    print(f"Seeds: {seeds_to_run}")
    print(f"Conditions: {CONDITIONS_ORDER}")

    all_summaries = list(existing_summaries)
    new_summaries = []
    new_blocks = []

    # Cache for passive sequences to feed fixed sequence condition: (inst_name, seed) -> sequence
    passive_sequences: Dict[Tuple[str, int], List[str]] = {}

    # Pre-populate passive sequences from existing traces if available
    for inst_name, _ in instances_to_run:
        for s in seeds_to_run:
            trace_p = traces_dir / f"trace_{inst_name}_seed_{s}_Portfolio_SWUCB_Passive.json"
            if trace_p.exists():
                try:
                    with open(trace_p, "r", encoding="utf-8") as tf:
                        tdata = json.load(tf)
                        if "executed_sequence" in tdata:
                            passive_sequences[(inst_name, s)] = tdata["executed_sequence"]
                except Exception as e:
                    print(f"Warning: could not read trace {trace_p}: {e}")

    start_campaign_time = time.perf_counter()
    run_counter = 0

    for inst_name, inst_path in instances_to_run:
        instance = load_dzn(inst_path, validate=True)
        normalizer = ObjectiveNormalizer(compute_instance_bounds(instance))

        for s in seeds_to_run:
            for cond_name in CONDITIONS_ORDER:
                run_key = (inst_name, s, cond_name)
                if run_key in completed_runs:
                    print(f"Skipping already completed run: {run_key}")
                    continue

                print(f"[{run_counter + 1}/{total_target_runs - len(completed_runs)}] Running {inst_name} | Seed {s} | {cond_name} ...")
                t_run_start = time.perf_counter()

                # Determine passive sequence if needed
                p_seq = None
                if cond_name == "Portfolio_Coop_FixedSequence":
                    p_seq = passive_sequences.get((inst_name, s))
                    if p_seq is None:
                        # Find from current session or raise error
                        raise RuntimeError(f"Cannot execute {cond_name}: Portfolio_SWUCB_Passive has not run yet for {inst_name} seed={s}")

                summary, blocks, trace, executed_seq = run_single_experiment(
                    instance=instance,
                    inst_name=inst_name,
                    normalizer=normalizer,
                    cond_name=cond_name,
                    seed=s,
                    passive_sequence=p_seq,
                )

                if cond_name == "Portfolio_SWUCB_Passive" and executed_seq is not None:
                    passive_sequences[(inst_name, s)] = executed_seq

                # Invariant checks
                assert summary["fe_overshoot"] == 0, f"FE overshoot != 0 on {run_key}"
                assert summary["total_fe"] == BUDGET, f"Total FE != 1000 on {run_key}"

                all_summaries.append(summary)
                new_summaries.append(summary)
                new_blocks.extend(blocks)
                completed_runs.add(run_key)
                run_counter += 1

                # Save trace json
                trace_file = traces_dir / f"trace_{inst_name}_seed_{s}_{cond_name}.json"
                with open(trace_file, "w", encoding="utf-8") as tf:
                    json.dump(trace, tf, indent=2)

                # Incremental CSV flush to protect progress
                fieldnames = list(summary.keys())
                write_header = not summary_csv.exists()
                with open(summary_csv, "a", newline="", encoding="utf-8") as sf:
                    writer = csv.DictWriter(sf, fieldnames=fieldnames)
                    if write_header:
                        writer.writeheader()
                    writer.writerow(summary)

                if blocks:
                    b_fieldnames = list(blocks[0].keys())
                    b_write_header = not blocks_csv.exists()
                    with open(blocks_csv, "a", newline="", encoding="utf-8") as bf:
                        b_writer = csv.DictWriter(bf, fieldnames=b_fieldnames)
                        if b_write_header:
                            b_writer.writeheader()
                        b_writer.writerows(blocks)

                elapsed_run = time.perf_counter() - t_run_start
                print(f"   -> Finished in {elapsed_run:.2f}s | Final HV: {summary['final_hv']} | AUC-HV: {summary['auc_hv']}")

    total_campaign_elapsed = time.perf_counter() - start_campaign_time
    print(f"=== CAMPAIGN EXECUTION BATCH FINISHED ===")
    print(f"Total newly executed runs: {run_counter}")
    print(f"Total time elapsed: {total_campaign_elapsed:.2f}s (Average: {total_campaign_elapsed / max(1, run_counter):.2f}s/run)")


if __name__ == "__main__":
    main()
