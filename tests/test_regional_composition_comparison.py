from dataclasses import asdict
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from run_regional_composition_comparison import (
    native_individual, INDIVIDUALS, COMPOSITIONS, POLICIES, compatible_sources,
)
from mojssp.io import load_dzn
from mojssp.runner import run_standalone_experiment
from mojssp.regional_portfolio import run_regional_policy_experiment


@pytest.mark.parametrize('method', INDIVIDUALS)
def test_native_control_preserves_reference_trajectory(method):
    instance = load_dzn(ROOT / 'data/validation/small_3x3.dzn')
    name, _, offset = INDIVIDUALS[method]
    result = native_individual(instance, 100, method, budget=163)
    control = asdict(run_standalone_experiment(
        instance, name, (100 * 10007 + offset) % (2**31 - 1), 163, 50, 30))
    assert result['evaluations_used'] == control['evaluations_used'] == 163
    assert result['checkpoints'] == [list(p) for p in control['checkpoints']]
    assert result['pareto_front'] == [list(p) for p in control['pareto_front']]


@pytest.mark.parametrize('policy', POLICIES)
def test_quartet_round_budget_and_reproduction(policy):
    instance = load_dzn(ROOT / 'data/validation/small_3x3.dzn')
    arms = COMPOSITIONS['quartet_regional']
    args = dict(seed=100, selected_arms=arms, policy=policy, budget=613, population_size=10)
    first = run_regional_policy_experiment(instance, **args)
    second = run_regional_policy_experiment(instance, **args)
    assert sum(first['allocations'].values()) == 613
    assert first['blocks'] == second['blocks']
    assert first['pareto_front'] == second['pareto_front']
    if policy == 'dynamic':
        initial = first['blocks'][:8]
        assert {a:sum(b['evaluations_used'] for b in initial if b['arm_name']==a)
                for a in arms} == dict.fromkeys(arms,75)


@pytest.mark.skip(reason='Source hash guard for the 2026-10-23 frozen code; the default-preserving '
                  'allocation options added later are checked by exact reproduction of 57 passive '
                  'trajectories in allocation_variants_moead_blmr_20261024')
def test_prior_regional_api_only_differs_by_inactive_reserve_override():
    folder = ROOT / 'results/experiments/regional_policy_integration_development_20261023'
    differences = compatible_sources(folder)
    assert len(differences) == 1
    assert differences[0]['path'] == 'src/mojssp/regional_portfolio.py'
