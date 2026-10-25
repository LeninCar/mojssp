from pathlib import Path
from unittest.mock import patch

from mojssp.evaluator import Evaluator
from mojssp.io import load_dzn
from run_composition_pilot import run_composition, run_without_moead
import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_pair_matches_union_of_individual_prefixes_and_counts_local_search():
    instance = load_dzn(ROOT/'data/validation/small_3x3.dzn')
    original = Evaluator.evaluate
    calls = []
    def counted(self,*a,**kw):
        calls.append(1)
        return original(self,*a,**kw)
    with patch.object(Evaluator,'evaluate',counted):
        pair = run_composition(instance,42,{'MOEA/D':200,'NSGA-II+LS':100},block_size=50,population_size=10)
    assert len(calls)==pair['evaluations_used']==300
    assert pair['allocations']=={'MOEA/D':200,'NSGA-II+LS':100}
    assert 0 < pair['ls_evaluations'] <=100
    points = set()
    for name,budget in pair['allocations'].items():
        result = run_composition(instance,42,{name:budget},block_size=50,population_size=10)
        points.update(map(tuple,result['pareto_front']))
    nondominated = {p for p in points if not any(q!=p and all(a<=b for a,b in zip(q,p)) for q in points)}
    assert set(map(tuple,pair['pareto_front']))==nondominated


@pytest.mark.parametrize('policy',['uniform','scaled'])
def test_no_moead_is_constructed_and_budget_includes_all_three_members(policy):
    instance = load_dzn(ROOT/'data/validation/small_3x3.dzn')
    original = Evaluator.evaluate
    calls = []
    def counted(self,*a,**kw):
        calls.append(1)
        return original(self,*a,**kw)
    with patch('run_composition_pilot.MOEADArm',side_effect=AssertionError('MOEA/D excluded')), patch.object(Evaluator,'evaluate',counted):
        result = run_without_moead(instance,42,policy,budget=300,block_size=50,population_size=10)
    assert len(calls)==result['evaluations_used']==300
    assert set(result['allocations'])=={'NSGA-II','SPEA2','NSGA-II+LS'}
    assert sum(result['allocations'].values())==300
    if policy=='uniform':
        assert set(result['allocations'].values())=={100}
