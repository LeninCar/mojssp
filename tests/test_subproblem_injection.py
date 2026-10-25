from pathlib import Path
from unittest.mock import patch

from mojssp.io import load_dzn
from mojssp.evaluator import Evaluator
from mojssp.provenance import compute_genotype_id
from mojssp.regional_portfolio import run_regional_policy_experiment
from mojssp.subproblem_injection import run_subproblem_injection

ROOT=Path(__file__).resolve().parents[1]


def test_disabled_compatible_injection_preserves_dynamic_search():
    instance=load_dzn(ROOT/'data/validation/small_3x3.dzn')
    a=run_subproblem_injection(instance,100,False,budget=613,population_size=10)
    b=run_regional_policy_experiment(instance,100,['MOEA/D','RegionExplorer'],'dynamic',budget=613,population_size=10)
    for key in ['blocks','region_trace','pareto_front','allocations','checkpoints']:
        assert a[key]==b[key]
    assert not a['migration_events']


def test_live_subproblem_scores_exact_fe_and_reproduction():
    instance=load_dzn(ROOT/'data/validation/small_3x3.dzn')
    original=Evaluator.evaluate;calls=[]
    def counted(self,*a,**kw):
        calls.append(1);return original(self,*a,**kw)
    with patch.object(Evaluator,'evaluate',counted):
        result=run_subproblem_injection(instance,100,budget=1000,population_size=10)
    repeat=run_subproblem_injection(instance,100,budget=1000,population_size=10)
    assert len(calls)==sum(result['allocations'].values())==1000
    assert result['migration_events']
    for key in ['blocks','pareto_front','injection_trace','migration_events']:
        assert result[key]==repeat[key]
    origins={};seen={'MOEA/D':set(),'RegionExplorer':set()}
    events=result['migration_events']
    for row in result['injection_trace']:
        used=set()
        block_events=[e for e in events if e['block_index']==row['block_index']]
        assert len(block_events)<=5
        for event in block_events:
            points=row['global_points_before'];w=event['target_weight'];z=event['ideal_point']
            eligible=[g for g in row['prepared_donor_ids'] if g not in used and g!=event['native_parent_id']]
            def score(g):return max(w[k]*abs(points[g][k]-z[k]) for k in range(3))
            assert event['donor_id']==min(eligible,key=lambda g:(score(g),g))
            assert abs(score(event['donor_id'])-event['donor_scalar_score'])<1e-12
            assert origins[event['donor_id']]=='RegionExplorer'
            assert event['donor_id'] not in seen['MOEA/D']
            used.add(event['donor_id'])
        for g in row['new_observed_ids']:
            origins.setdefault(g,row['arm']);seen[row['arm']].add(g)
