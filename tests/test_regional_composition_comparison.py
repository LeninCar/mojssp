from dataclasses import asdict
from pathlib import Path

import pytest

from mojssp.experiments.methods import NATIVE, run_native
from mojssp.io import load_dzn
from mojssp.runner import run_standalone_experiment
from mojssp.regional_portfolio import run_regional_policy_experiment

ROOT = Path(__file__).resolve().parents[1]
ARM_NAMES = {'moead': 'MOEA/D', 'nsga2_individual': 'NSGA-II', 'spea2_individual': 'SPEA2',
             'nsga2_ls_individual': 'NSGA-II+LS', 'mopso_individual': 'MOPSO'}
QUARTET = ['MOEA/D', 'NSGA-II', 'SPEA2', 'RegionExplorer']


@pytest.mark.parametrize('method', NATIVE)
def test_native_control_preserves_reference_trajectory(method):
    instance = load_dzn(ROOT / 'data/validation/small_3x3.dzn')
    offset = NATIVE[method][1]
    result = run_native(instance, 100, method, budget=163)
    control = asdict(run_standalone_experiment(
        instance, ARM_NAMES[method], (100 * 10007 + offset) % (2**31 - 1), 163, 50, 30))
    assert result['evaluations_used'] == control['evaluations_used'] == 163
    assert result['checkpoints'] == [list(p) for p in control['checkpoints']]
    assert result['pareto_front'] == [list(p) for p in control['pareto_front']]


@pytest.mark.parametrize('policy', ['scaled', 'dynamic'])
def test_quartet_round_budget_and_reproduction(policy):
    instance = load_dzn(ROOT / 'data/validation/small_3x3.dzn')
    arms = QUARTET
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
