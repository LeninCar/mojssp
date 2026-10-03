"""Smoke test execution script for the 25 newly generated MO-JSSP instances (Phase F8.6.3).

Executes all 4 algorithm configurations on each of the 25 instances:
1. NSGA-II
2. MOPSO
3. NSGA-II+LS
4. Portfolio + DMAB (SlidingWindowUCB)

Ensures zero exceptions, correct FE accounting, and valid Pareto archives.
"""

import sys
import time
from pathlib import Path

# Add project root and src to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

from mojssp import (
    AdaptivePortfolioOrchestrator,
    HypervolumeRewardTracker,
    MOPSOArm,
    NSGA2Arm,
    NSGA2LSArm,
    ObjectiveNormalizer,
    Portfolio,
    SlidingWindowUCB,
    compute_archive_hypervolume,
    compute_instance_bounds,
    load_dzn,
)


def run_smoke_test_all() -> None:
    data_dir = PROJECT_ROOT / "data" / "generated" / "f86_3"
    dzn_files = sorted(data_dir.rglob("*.dzn"))

    if len(dzn_files) != 25:
        raise ValueError(f"Expected 25 instances, found {len(dzn_files)} in {data_dir}")

    seed = 42
    arm_classes = [
        ("NSGA-II", NSGA2Arm),
        ("MOPSO", MOPSOArm),
        ("NSGA-II+LS", NSGA2LSArm),
    ]

    print("=" * 80)
    print("PHASE F8.6.3: SMOKE TEST ON 25 NEW INSTANCES")
    print(f"Total instances to verify: {len(dzn_files)}")
    print("=" * 80)

    header = f"{'Instance':<24} {'Algorithm':<16} {'Evals':<8} {'Archive':<8} {'Status':<10}"
    print(header)
    print("-" * len(header))

    passed_count = 0
    total_checks = 0
    start_total = time.time()

    for idx, fpath in enumerate(dzn_files, 1):
        inst_name = fpath.stem
        inst = load_dzn(fpath, validate=True)
        bounds = compute_instance_bounds(inst)
        norm = ObjectiveNormalizer(bounds)

        # 1. Individual Arms (budget=20 FE)
        for arm_name, ArmCls in arm_classes:
            total_checks += 1
            arm = ArmCls(inst, population_size=10, seed=seed)
            res = arm.run(budget=20)
            assert res.evaluations_used == 20, f"{arm_name} did not use 20 evaluations on {inst_name} (got {res.evaluations_used})"
            assert len(res.solutions) > 0, f"{arm_name} produced empty archive on {inst_name}"
            passed_count += 1
            print(f"[{idx:02d}/25] {inst_name:<17} {arm_name:<16} {res.evaluations_used:<8} {len(res.solutions):<8} OK")

        # 2. Portfolio + DMAB (total_budget=30 FE, block_size=10 FE)
        total_checks += 1
        portfolio = Portfolio([
            NSGA2Arm(inst, population_size=10, seed=seed),
            MOPSOArm(inst, population_size=10, seed=seed),
            NSGA2LSArm(inst, population_size=10, seed=seed),
        ])
        dmab = SlidingWindowUCB(portfolio.arm_names, window_size=5, seed=seed)
        tracker = HypervolumeRewardTracker(norm)
        orchestrator = AdaptivePortfolioOrchestrator(portfolio, dmab, tracker)

        orch_res = orchestrator.run(total_budget=30, block_size=10)
        assert orch_res.total_evaluations == 30, f"Portfolio budget mismatch on {inst_name}"
        assert len(orch_res.global_archive) > 0, f"Portfolio archive empty on {inst_name}"
        passed_count += 1
        print(f"[{idx:02d}/25] {inst_name:<17} {'Portfolio+DMAB':<16} {orch_res.total_evaluations:<8} {len(orch_res.global_archive):<8} OK")
        print("-" * len(header))

    elapsed = time.time() - start_total
    print("=" * 80)
    print(f"ALL CHECKS PASSED: {passed_count}/{total_checks} across all 25 instances in {elapsed:.2f}s!")
    print("=" * 80)


if __name__ == "__main__":
    run_smoke_test_all()

