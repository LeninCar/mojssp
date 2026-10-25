from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import pytest

from mojssp.io import load_dzn
from mojssp.evaluator import Evaluator
from mojssp.regional_portfolio import run_regional_policy_experiment
from mojssp.subproblem_replay import run_subproblem_replay

ROOT=Path(__file__).resolve().parents[1]


def test_replay_without_injection_exactly_reproduces_passive_dynamic():
    instance=load_dzn(ROOT/'data/validation/small_3x3.dzn')
    source=run_regional_policy_experiment(instance,100,['MOEA/D','RegionExplorer'],'dynamic',budget=613,population_size=10)
    original=deepcopy(source)
    result=run_subproblem_replay(instance,100,source['blocks'],False,budget=613,population_size=10)
    for key in ['blocks','allocations','region_trace','pareto_front','checkpoints']:
        assert result[key]==source[key]
    assert original==source
    assert result['migration_uses']==0


def test_injected_replay_keeps_full_trace_and_exact_native_fe():
    instance=load_dzn(ROOT/'data/validation/small_3x3.dzn')
    source=run_regional_policy_experiment(instance,100,['MOEA/D','RegionExplorer'],'dynamic',budget=1000,population_size=10)
    original=Evaluator.evaluate;calls=[]
    def counted(self,*a,**kw):
        calls.append(1);return original(self,*a,**kw)
    with patch.object(Evaluator,'evaluate',counted):
        result=run_subproblem_replay(instance,100,source['blocks'],True,budget=1000,population_size=10)
    repeat=run_subproblem_replay(instance,100,source['blocks'],True,budget=1000,population_size=10)
    assert len(calls)==result['evaluations_used']==1000
    assert result['allocations']==source['allocations']
    assert [(b['arm_name'],b['evaluations_used'],b['fe_before'],b['fe_after']) for b in result['blocks']]==[
        (b['arm_name'],b['evaluations_used'],b['fe_before'],b['fe_after']) for b in source['blocks']]
    assert result['migration_uses']>0
    for key in ['blocks','pareto_front','migration_events','injection_trace']:
        assert result[key]==repeat[key]


@pytest.mark.parametrize('mutation',['gap','unknown_arm','budget'])
def test_invalid_schedule_rejected_before_evaluation(mutation):
    instance=load_dzn(ROOT/'data/validation/small_3x3.dzn')
    schedule=[dict(arm_name='MOEA/D',evaluations_used=50,budget_allocated=50,fe_before=0,fe_after=50)]
    if mutation=='gap':schedule[0]['fe_before']=1
    if mutation=='unknown_arm':schedule[0]['arm_name']='other'
    if mutation=='budget':schedule[0]['budget_allocated']=49
    with patch.object(Evaluator,'evaluate',side_effect=AssertionError('No FE allowed')):
        with pytest.raises(ValueError):run_subproblem_replay(instance,100,schedule,budget=50)
