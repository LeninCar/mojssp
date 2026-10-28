from pathlib import Path
from unittest.mock import patch

import pytest

from mojssp.model.evaluator import Evaluator
from mojssp.model.io import load_dzn
from mojssp.portfolio.runner import run_phase2_portfolio_experiment, run_standalone_experiment

ROOT = Path(__file__).resolve().parents[1]


def test_pair_has_equal_quotas_and_matches_union_of_its_individual_prefixes():
    instance = load_dzn(ROOT / "data/validation/small_3x3.dzn")
    calls = 0
    original = Evaluator.evaluate

    def counted(self, *args, **kwargs):
        nonlocal calls
        calls += 1
        return original(self, *args, **kwargs)

    with (
        patch.object(Evaluator, "evaluate", counted),
        patch("mojssp.portfolio.runner.MOEADArm", side_effect=AssertionError("MOEA/D must be absent")),
    ):
        result, history = run_phase2_portfolio_experiment(
            instance,
            seed=42,
            total_budget=240,
            block_size=20,
            population_size=10,
            policy="uniform",
            selected_arms=["NSGA-II", "SPEA2"],
        )
    assert calls == result.evaluations_used == 240
    assert {name: value.evaluations_assigned for name, value in result.arm_allocations.items()} == {
        "NSGA-II": 120,
        "SPEA2": 120,
    }
    assert {block.arm_name for block in history} == {"NSGA-II", "SPEA2"}
    points = set()
    for name, offset in [("NSGA-II", 29), ("SPEA2", 43)]:
        individual = run_standalone_experiment(
            instance, name, (42 * 10007 + offset) % (2**31 - 1), 120, 20, 10
        )
        points.update(individual.pareto_front)
    nondominated = {
        p for p in points if not any(q != p and all(a <= b for a, b in zip(q, p)) for q in points)
    }
    assert set(result.pareto_front) == nondominated


@pytest.mark.parametrize("members", [["NSGA-II"], ["NSGA-II", "NSGA-II"], ["NSGA-II", "unknown"]])
def test_invalid_members_are_rejected(members):
    instance = load_dzn(ROOT / "data/validation/small_3x3.dzn")
    with pytest.raises(ValueError):
        run_phase2_portfolio_experiment(instance, seed=42, selected_arms=members)


def test_scaled_pair_uses_only_selected_algorithms_and_exact_total_budget():
    instance = load_dzn(ROOT / "data/validation/small_3x3.dzn")
    arguments = dict(
        seed=42,
        total_budget=241,
        block_size=20,
        population_size=10,
        policy="scaled",
        selected_arms=["NSGA-II", "SPEA2"],
    )
    first, history = run_phase2_portfolio_experiment(instance, **arguments)
    second, replay = run_phase2_portfolio_experiment(instance, **arguments)
    assert first.evaluations_used == 241
    assert sum(block.evaluations_used for block in history) == 241
    assert set(first.arm_allocations) == {"NSGA-II", "SPEA2"}
    assert first.pareto_front == second.pareto_front
    assert history == replay
