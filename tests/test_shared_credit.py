from pathlib import Path
from unittest.mock import patch
import pytest
from mojssp.io import load_dzn
from mojssp.evaluator import Evaluator
from mojssp.shared_credit import run_shared_credit
from mojssp.subproblem_injection import run_subproblem_injection

ROOT=Path(__file__).resolve().parents[1]


def test_zero_alpha_observer_preserves_live_native_search_exactly():
    instance=load_dzn(ROOT/'data/validation/small_3x3.dzn')
    observed=run_shared_credit(instance,100,0.,budget=613,population_size=10)
    native=run_subproblem_injection(instance,100,budget=613,population_size=10)
    for key in ['blocks','allocations','pareto_front','region_trace','migration_events','injection_trace']:
        assert observed[key]==native[key]
    assert len(observed['child_ledger'])==observed['allocations']['MOEA/D']


def test_shared_credit_conserves_gain_real_fe_and_reproduces():
    instance=load_dzn(ROOT/'data/validation/small_3x3.dzn')
    original=Evaluator.evaluate;calls=[]
    def counted(self,*a,**kw):
        calls.append(1);return original(self,*a,**kw)
    with patch.object(Evaluator,'evaluate',counted):
        result=run_shared_credit(instance,100,.5,budget=1000,population_size=10)
    repeat=run_shared_credit(instance,100,.5,budget=1000,population_size=10)
    assert len(calls)==sum(result['allocations'].values())==1000
    for key in ['blocks','child_ledger','credit_trace','pareto_front']:
        assert result[key]==repeat[key]
    assert any(c['assisted'] and c['marginal_gain']>0 for c in result['child_ledger'])
    for row in result['credit_trace']:
        assert sum(row['credits'].values())==pytest.approx(row['raw_reward'] if row['scored'] else 0.,abs=1e-12)
        if row['arm']=='MOEA/D' and row['scored']:
            assert row['credits']['RegionExplorer']==pytest.approx(.5*row['assisted_child_gain'],abs=1e-12)
    assert len({c['global_fe'] for c in result['child_ledger']})==len(result['child_ledger'])


@pytest.mark.parametrize('alpha',[-.1,1.1,float('nan')])
def test_invalid_credit_fraction_rejected_before_evaluation(alpha):
    instance=load_dzn(ROOT/'data/validation/small_3x3.dzn')
    with patch.object(Evaluator,'evaluate',side_effect=AssertionError('No FE allowed')):
        with pytest.raises(ValueError):run_shared_credit(instance,100,alpha)
