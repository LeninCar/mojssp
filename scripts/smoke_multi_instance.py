"""Multi-instance smoke test execution script for MO-JSSP portfolio (Phase 7.7)."""

from pathlib import Path
import sys

# Add src directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

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


def main() -> None:
    data_dir = Path(__file__).resolve().parent.parent / "data"
    instances_info = [
        ("toy_instance", data_dir / "toy_instance.dzn"),
        ("small_3x2", data_dir / "small_3x2.dzn"),
        ("small_3x3", data_dir / "small_3x3.dzn"),
    ]

    seed = 42
    arm_classes = [NSGA2Arm, MOPSOArm, NSGA2LSArm]

    print("=" * 75)
    print("PHASE 7.7: MULTI-INSTANCE SMOKE TEST - INDIVIDUAL ARMS")
    print("=" * 75)
    header_arms = f"{'Instance':<15} {'Arm':<15} {'Evals':<8} {'Completed':<12} {'Archive':<10} {'HV':<10}"
    print(header_arms)
    print("-" * len(header_arms))

    for name, path in instances_info:
        inst = load_dzn(path, validate=True)
        bounds = compute_instance_bounds(inst)
        norm = ObjectiveNormalizer(bounds)

        for ArmCls in arm_classes:
            arm = ArmCls(inst, population_size=10, seed=seed)
            res = arm.run(budget=25)
            hv = compute_archive_hypervolume(res.solutions, norm)
            print(
                f"{name:<15} {arm.arm_name:<15} {res.evaluations_used:<8} "
                f"{str(res.completed):<12} {len(res.solutions):<10} {hv:<10.6f}"
            )
        print("-" * len(header_arms))

    print("\n" + "=" * 75)
    print("PHASE 7.7: MULTI-INSTANCE SMOKE TEST - ADAPTIVE PIPELINE")
    print("=" * 75)
    header_pipe = f"{'Instance':<15} {'Blocks':<8} {'Evals':<8} {'HV Initial':<12} {'HV Final':<12} {'Archive':<8}"
    print(header_pipe)
    print("-" * len(header_pipe))

    for name, path in instances_info:
        inst = load_dzn(path, validate=True)
        bounds = compute_instance_bounds(inst)
        norm = ObjectiveNormalizer(bounds)

        portfolio = Portfolio([
            NSGA2Arm(inst, population_size=10, seed=seed),
            MOPSOArm(inst, population_size=10, seed=seed),
            NSGA2LSArm(inst, population_size=10, seed=seed),
        ])
        dmab = SlidingWindowUCB(portfolio.arm_names, window_size=5, seed=seed)
        tracker = HypervolumeRewardTracker(norm)
        orchestrator = AdaptivePortfolioOrchestrator(portfolio, dmab, tracker)

        hv_initial = tracker.current_hv
        res = orchestrator.run(total_budget=45, block_size=15)
        hv_final = tracker.current_hv

        print(
            f"{name:<15} {res.total_blocks:<8} {res.total_evaluations:<8} "
            f"{hv_initial:<12.6f} {hv_final:<12.6f} {len(res.global_archive):<8}"
        )

    print("-" * len(header_pipe))
    print("Smoke test completed successfully on all instances.\n")


if __name__ == "__main__":
    main()
