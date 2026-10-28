from pathlib import Path
from fractions import Fraction

import pytest

from mojssp.portfolio.fixed_budget import evaluation_quotas
from mojssp.model.io import load_dzn
from mojssp.portfolio.runner import run_phase2_portfolio_experiment, run_standalone_experiment

SHARES = {"MOEA/D": Fraction(41, 60), "NSGA-II": Fraction(13, 60), "SPEA2": Fraction(1, 10)}


def test_exact_experimental_quota_at_3000_evaluations():
    assert evaluation_quotas(3000, SHARES) == {"MOEA/D": 2050, "NSGA-II": 650, "SPEA2": 300}


@pytest.mark.parametrize("budget", [1, 7, 120, 241, 1000, 3000])
def test_integer_quotas_partition_every_evaluation(budget):
    quotas = evaluation_quotas(budget, SHARES)
    assert sum(quotas.values()) == budget
    assert all(value >= 0 for value in quotas.values())


@pytest.mark.parametrize("warmup", [True, False])
def test_execution_consumes_exact_quotas_and_is_reproducible(warmup):
    root = Path(__file__).resolve().parents[1]
    instance = load_dzn(root / "data/validation/small_3x3.dzn")
    arguments = dict(
        seed=42,
        total_budget=241,
        population_size=10,
        block_size=20,
        policy="weighted",
        neutral_warmup=warmup,
        budget_shares=SHARES,
    )
    first, history = run_phase2_portfolio_experiment(instance, **arguments)
    second, replay = run_phase2_portfolio_experiment(instance, **arguments)
    quotas = evaluation_quotas(241, SHARES)
    actual = {
        name: sum(block.evaluations_used for block in history if block.arm_name == name) for name in quotas
    }
    assert actual == quotas
    assert first.evaluations_used == 241
    assert first.pareto_front == second.pareto_front
    assert history == replay
    assert all(block.phase in ("warmup", "fixed") for block in history)
    assert sum(block.phase == "warmup" for block in history) == (3 if warmup else 0)


def test_rejects_budget_that_cannot_initialize_every_algorithm():
    root = Path(__file__).resolve().parents[1]
    instance = load_dzn(root / "data/validation/small_3x3.dzn")
    with pytest.raises(ValueError, match="initial population"):
        run_phase2_portfolio_experiment(
            instance, seed=42, total_budget=100, policy="weighted", population_size=30, budget_shares=SHARES
        )


def test_weighted_front_matches_individual_runs_at_their_assigned_quotas():
    root = Path(__file__).resolve().parents[1]
    instance = load_dzn(root / "data/validation/small_3x3.dzn")
    result, _ = run_phase2_portfolio_experiment(
        instance,
        seed=42,
        total_budget=241,
        block_size=20,
        population_size=10,
        policy="weighted",
        budget_shares=SHARES,
    )
    points = set()
    for (name, quota), offset in zip(evaluation_quotas(241, SHARES).items(), [17, 29, 43]):
        individual = run_standalone_experiment(
            instance,
            name,
            seed=(42 * 10007 + offset) % (2**31 - 1),
            budget=quota,
            block_size=20,
            population_size=10,
        )
        points.update(individual.pareto_front)
    expected = {
        point
        for point in points
        if not any(other != point and all(a <= b for a, b in zip(other, point)) for other in points)
    }
    assert set(result.pareto_front) == expected
