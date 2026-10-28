from pathlib import Path
from unittest.mock import patch
from dataclasses import asdict
import json
import math
import pytest

from mojssp.model.evaluator import Evaluator
from mojssp.model.io import load_dzn
from mojssp.portfolio.regional_portfolio import POLICY_PROFILES,run_regional_policy_experiment
from mojssp.portfolio.runner import run_phase2_portfolio_experiment

ROOT=Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('policy',POLICY_PROFILES)
@pytest.mark.parametrize('native',['MOEA/D','NSGA-II','SPEA2'])
def test_all_policies_execute_exact_budget_with_regional_arm_and_reproduce(policy,native):
    instance=load_dzn(ROOT/'data/validation/small_3x3.dzn')
    original=Evaluator.evaluate
    calls=[]
    def counted(self,*a,**kw):
        calls.append(1)
        return original(self,*a,**kw)
    arguments=dict(seed=42,selected_arms=[native,'RegionExplorer'],policy=policy,budget=613,population_size=10)
    with patch.object(Evaluator,'evaluate',counted):
        first=run_regional_policy_experiment(instance,**arguments)
    second=run_regional_policy_experiment(instance,**arguments)
    json.dumps(first,allow_nan=False)
    assert len(calls)==sum(first['allocations'].values())==613
    assert first['pareto_front']==second['pareto_front']
    assert first['blocks']==second['blocks']
    assert first['allocations']==second['allocations']
    assert sum(t['evaluations'] for t in first['region_trace'])==first['allocations']['RegionExplorer']
    if policy=='dynamic':
        assert {r['round_index'] for r in first['blocks']}=={0,1,2}


def test_disabled_guidance_matches_original_native_portfolio():
    instance=load_dzn(ROOT/'data/validation/small_3x3.dzn')
    original,history=run_phase2_portfolio_experiment(instance,42,total_budget=600,
        block_size=50,population_size=10,policy='scaled',selected_arms=['NSGA-II','SPEA2'])
    regional=run_regional_policy_experiment(instance,42,['NSGA-II','SPEA2'],'scaled',budget=600,population_size=10)
    assert regional['pareto_front']==[list(p) for p in original.pareto_front]
    expected=[asdict(r) for r in history]
    for row in expected:
        if row['ucb_indices'] is not None:
            row['ucb_indices']={name:value if math.isfinite(value) else None for name,value in row['ucb_indices'].items()}
    assert regional['blocks']==expected
    assert not regional['guidance_events']


def test_native_region_guidance_uses_only_evaluated_archive_parents_and_keeps_budget():
    instance=load_dzn(ROOT/'data/validation/small_3x3.dzn')
    result=run_regional_policy_experiment(instance,42,['NSGA-II','SPEA2'],'scaled',True,budget=600,population_size=10)
    assert result['guidance_events']
    contexts={(t['arm'],t['global_fe_before']):t for t in result['guidance_trace']}
    for event in result['guidance_events']:
        context=contexts[event['arm'],event['global_fe_before']]
        assert event['donor_id'] in context['donor_ids']
        assert event['donor_id'] in context['global_parent_ids']
        assert event['mating_index']%10==0
    assert sum(result['allocations'].values())==600


def test_regional_arm_cannot_start_without_an_evaluated_archive():
    instance=load_dzn(ROOT/'data/validation/small_3x3.dzn')
    with pytest.raises(ValueError,match='seed the archive'):
        run_regional_policy_experiment(instance,42,['RegionExplorer','MOEA/D'])


def test_reset_restores_native_guidance_and_its_random_stream():
    from mojssp.portfolio.regional_portfolio import RegionAwarePortfolio
    from mojssp.algorithms.arms import NSGA2Arm
    from mojssp.algorithms.spea2 import SPEA2Arm
    from mojssp.metrics.normalization import ObjectiveNormalizer,compute_instance_bounds
    instance=load_dzn(ROOT/'data/validation/small_3x3.dzn')
    arms={'NSGA-II':NSGA2Arm(instance,population_size=10,max_generations=None,seed=1),
          'SPEA2':SPEA2Arm(instance,population_size=10,archive_size=10,seed=2)}
    portfolio=RegionAwarePortfolio(arms,ObjectiveNormalizer(compute_instance_bounds(instance)),instance,42,True)
    def run():
        for name in ['NSGA-II','SPEA2']*4:
            portfolio.run_arm(name,50)
        return ([list(e.objectives) for e in portfolio.global_archive.entries],
                [event for guide in portfolio.guides.values() for event in guide.events])
    first=run()
    assert first[1]
    portfolio.reset()
    assert portfolio.total_evaluations==0
    assert run()==first


@pytest.mark.parametrize('policy',POLICY_PROFILES)
def test_four_arms_can_share_each_policy_with_native_region_guidance(policy):
    instance=load_dzn(ROOT/'data/validation/small_3x3.dzn')
    result=run_regional_policy_experiment(instance,42,
        ['MOEA/D','NSGA-II','SPEA2','RegionExplorer'],policy,True,budget=650,population_size=10)
    assert set(result['allocations'])=={'MOEA/D','NSGA-II','SPEA2','RegionExplorer'}
    assert sum(result['allocations'].values())==650
    assert all(v>=50 for v in result['allocations'].values())
    json.dumps(result,allow_nan=False)


@pytest.mark.parametrize('minimum_share',[.1,.05,.01])
def test_smaller_dynamic_reserves_preserve_exact_evaluation_budget(minimum_share):
    instance=load_dzn(ROOT/'data/validation/small_3x3.dzn')
    original=Evaluator.evaluate
    calls=[]
    def counted(self,*a,**kw):
        calls.append(1)
        return original(self,*a,**kw)
    with patch.object(Evaluator,'evaluate',counted):
        result=run_regional_policy_experiment(instance,42,['SPEA2','RegionExplorer'],'dynamic',
            budget=913,population_size=10,minimum_share=minimum_share)
    assert len(calls)==sum(result['allocations'].values())==913
    assert result['policy_profile']['minimum_share']==minimum_share
    assert sum(t['evaluations'] for t in result['region_trace'])==result['allocations']['RegionExplorer']


def test_explicit_original_reserve_matches_default_profile():
    instance=load_dzn(ROOT/'data/validation/small_3x3.dzn')
    arguments=dict(seed=42,selected_arms=['SPEA2','RegionExplorer'],policy='dynamic',budget=600,population_size=10)
    default=run_regional_policy_experiment(instance,**arguments)
    explicit=run_regional_policy_experiment(instance,**arguments,minimum_share=.1)
    assert default['pareto_front']==explicit['pareto_front']
    assert default['blocks']==explicit['blocks']
    assert default['policy_profile']==explicit['policy_profile']


@pytest.mark.parametrize('policy,share',[('scaled',.01),('dynamic',-.1),('dynamic',.6),('dynamic',float('nan'))])
def test_invalid_reserve_configuration_is_rejected(policy,share):
    instance=load_dzn(ROOT/'data/validation/small_3x3.dzn')
    with pytest.raises(ValueError):
        run_regional_policy_experiment(instance,42,['SPEA2','RegionExplorer'],policy,minimum_share=share)
