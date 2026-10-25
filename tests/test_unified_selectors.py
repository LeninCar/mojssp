"""Reproducibility and budget checks shared by the four portfolio policies."""
from pathlib import Path

import pytest

from mojssp.io import load_dzn
from mojssp.runner import run_phase2_portfolio_experiment
from mojssp.selectors import POLICIES, make_selector

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('policy', POLICIES)
def test_same_seed_preserves_front_and_allocation_with_partial_final_block(policy):
    instance = load_dzn(ROOT / 'data/validation/small_3x3.dzn')
    arguments = dict(seed=42, total_budget=241, block_size=20, population_size=10, policy=policy)
    first, first_history = run_phase2_portfolio_experiment(instance, **arguments)
    second, second_history = run_phase2_portfolio_experiment(instance, **arguments)
    assert first.evaluations_used == second.evaluations_used == 241
    assert first.pareto_front == second.pareto_front
    assert first.hypervolume == second.hypervolume
    assert first.arm_allocations == second.arm_allocations
    assert first_history == second_history
    assert sum(block.evaluations_used for block in first_history) == 241
    assert first_history[-1].evaluations_used == 1


def test_unknown_policy_is_rejected():
    with pytest.raises(ValueError):
        make_selector('unknown', ['MOEA/D', 'NSGA-II', 'SPEA2'])
