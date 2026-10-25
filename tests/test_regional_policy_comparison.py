from dataclasses import asdict
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from run_regional_policy_comparison import native_individual, CONTROLS, POLICIES
from mojssp.io import load_dzn
from mojssp.evaluator import Evaluator
from mojssp.runner import run_standalone_experiment


@pytest.mark.parametrize('method,name,offset', [
    ('mopso_individual', 'MOPSO', 97),
    ('spea2_individual', 'SPEA2', 43),
])
def test_saved_individual_genotypes_preserve_native_trajectory(method, name, offset):
    instance = load_dzn(ROOT / 'data/validation/small_3x3.dzn')
    original = Evaluator.evaluate
    calls = []
    def counted(self, *args, **kwargs):
        calls.append(1)
        return original(self, *args, **kwargs)
    with patch.object(Evaluator, 'evaluate', counted):
        result = native_individual(instance, 100, method, budget=163)
    control = asdict(run_standalone_experiment(
        instance, name, (100 * 10007 + offset) % (2**31 - 1), 163, 50, 30))
    assert len(calls) == result['evaluations_used'] == 163
    assert result['checkpoints'] == [list(p) for p in control['checkpoints']]
    assert result['pareto_front'] == [list(p) for p in control['pareto_front']]
    assert result['hypervolume'] == control['hypervolume']
    assert len(result['front_entries']) == len(result['pareto_front'])


def test_comparison_includes_mopso_and_all_five_policies():
    assert 'mopso_individual' in CONTROLS
    assert set(POLICIES) == {'uniform', 'sw_ucb', 'scaled', 'ph', 'dynamic'}
