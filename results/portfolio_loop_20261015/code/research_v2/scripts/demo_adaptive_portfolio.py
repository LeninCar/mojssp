"""Demonstration script for the Adaptive Portfolio on MO-JSSP (Phase 7.6)."""

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
    compute_instance_bounds,
    load_dzn,
)


def main() -> None:
    toy_path = Path(__file__).resolve().parent.parent / "data" / "toy_instance.dzn"
    instance = load_dzn(toy_path)
    bounds = compute_instance_bounds(instance)
    normalizer = ObjectiveNormalizer(bounds)

    seed = 42
    total_budget = 90
    block_size = 15

    # 1. Instantiate arms
    arm1 = NSGA2Arm(instance, population_size=10, seed=seed)
    arm2 = MOPSOArm(instance, population_size=10, seed=seed)
    arm3 = NSGA2LSArm(instance, population_size=10, seed=seed)

    # 2. Portfolio, DMAB selector, and Reward Tracker
    portfolio = Portfolio(arms=[arm1, arm2, arm3])
    dmab = SlidingWindowUCB(arm_names=portfolio.arm_names, window_size=5, seed=seed)
    tracker = HypervolumeRewardTracker(normalizer)

    # 3. Adaptive Orchestrator
    orchestrator = AdaptivePortfolioOrchestrator(
        portfolio=portfolio,
        dmab=dmab,
        reward_tracker=tracker,
    )

    result = orchestrator.run(total_budget=total_budget, block_size=block_size)

    print("Adaptive Portfolio Run")
    print("----------------------\n")
    print(f"Total evaluations: {result.total_evaluations}")
    print(f"Total blocks: {result.total_blocks}\n")

    header = f"{'Block':<6} {'Arm':<12} {'Evals':<8} {'HV Before':<12} {'HV After':<12} {'Reward':<12}"
    print(header)
    print("-" * len(header))

    for rec in result.history:
        b_idx = rec.block_index + 1
        print(
            f"{b_idx:<6} {rec.arm_name:<12} {rec.evaluations_used:<8} "
            f"{rec.hv_before:<12.6f} {rec.hv_after:<12.6f} {rec.reward:<12.6f}"
        )

    print("-" * len(header))
    print(f"Final archive size: {len(result.global_archive)}")
    print(f"Final HV: {tracker.current_hv:.6f}\n")


if __name__ == "__main__":
    main()
