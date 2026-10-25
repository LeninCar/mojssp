from pathlib import Path
import json
import shutil
from unittest.mock import patch

import pytest

from mojssp.io import load_dzn
from mojssp.evaluator import Evaluator
from mojssp.regional_injection import run_blmr_injection
from mojssp.regional_portfolio import run_regional_policy_experiment
from mojssp.regional_injection import InjectedRegionalPortfolio
from mojssp.moead import MOEADArm
from mojssp.regional_explorer import RegionalExplorerArm
from mojssp.normalization import ObjectiveNormalizer, compute_instance_bounds

ROOT = Path(__file__).resolve().parents[1]


def test_disabled_injection_preserves_live_dynamic_trajectory():
    instance = load_dzn(ROOT/'data/validation/small_3x3.dzn')
    result = run_blmr_injection(instance, 100, False, budget=613, population_size=10)
    control = run_regional_policy_experiment(instance, 100, ['MOEA/D','RegionExplorer'],
        'dynamic', budget=613, population_size=10)
    for key in ['blocks','allocations','region_trace','pareto_front','checkpoints']:
        assert result[key] == control[key]
    assert result['migration_uses'] == 0


def test_active_injection_has_real_eligible_donors_and_exact_fe():
    instance = load_dzn(ROOT/'results/experiments/weighted_pilot_development_20261023/instances/development_00_5x5.dzn')
    original = Evaluator.evaluate
    calls = []
    def counted(self,*a,**kw):
        calls.append(1)
        return original(self,*a,**kw)
    with patch.object(Evaluator,'evaluate',counted):
        result = run_blmr_injection(instance,100,True,budget=1000,population_size=10)
    repeat = run_blmr_injection(instance,100,True,budget=1000,population_size=10)
    assert len(calls)==sum(result['allocations'].values())==1000
    assert result['migration_uses']>0
    for key in ['blocks','region_trace','pareto_front','migration_events','injection_trace']:
        assert result[key]==repeat[key]
    origins,seen = {},{'MOEA/D':set(),'RegionExplorer':set()}
    for row in result['injection_trace']:
        events=[e for e in result['migration_events'] if e['block_index']==row['block_index']]
        assert len(events)==row['used_donors']<=5
        for event in events:
            gid=event['donor_id']
            assert event['source']=='RegionExplorer' and event['recipient']=='MOEA/D'
            assert origins[gid]=='RegionExplorer'
            assert gid not in seen['MOEA/D']
            assert gid in row['global_points_before']
            assert gid in row['prepared_donor_ids']
            assert event['mating_index']%10==0
        for gid in row['new_observed_ids']:
            origins.setdefault(gid,row['arm']);seen[row['arm']].add(gid)


@pytest.mark.parametrize('m,every',[(0,10),(5,0)])
def test_invalid_migration_profile_rejected(m,every):
    instance=load_dzn(ROOT/'data/validation/small_3x3.dzn')
    with pytest.raises(ValueError):
        run_blmr_injection(instance,100,m=m,every=every)


def test_reset_clears_injection_provenance_and_reproduces_search():
    instance=load_dzn(ROOT/'data/validation/small_3x3.dzn')
    norm=ObjectiveNormalizer(compute_instance_bounds(instance))
    arms={'MOEA/D':MOEADArm(instance,population_size=10,seed=17),
          'RegionExplorer':RegionalExplorerArm(instance,norm,policy='random',seed=71)}
    portfolio=InjectedRegionalPortfolio(arms,norm,instance,100)
    for name in ['MOEA/D','RegionExplorer','MOEA/D']:
        portfolio.run_arm(name,50)
    before=portfolio.injection_trace.copy()
    events=portfolio.injection.events.copy()
    front=[tuple(e.objectives) for e in portfolio.global_archive.entries]
    portfolio.reset()
    assert not portfolio.injection.events
    assert not portfolio.injection.origins
    assert not portfolio.injection_trace
    assert portfolio.total_evaluations==0
    for name in ['MOEA/D','RegionExplorer','MOEA/D']:
        portfolio.run_arm(name,50)
    assert portfolio.injection_trace==before
    assert portfolio.injection.events==events
    assert [tuple(e.objectives) for e in portfolio.global_archive.entries]==front


def test_campaign_control_compares_serialized_region_trace(tmp_path):
    from run_blmr_injection_pilot import execute
    case='small_3x3'
    source=ROOT/'data/validation/small_3x3.dzn'
    (tmp_path/'instances').mkdir()
    shutil.copy2(source,tmp_path/'instances'/f'{case}.dzn')
    control=run_regional_policy_experiment(load_dzn(source),100,['MOEA/D','RegionExplorer'],'dynamic')
    folder=tmp_path/'reference/development'
    folder.mkdir(parents=True)
    (folder/f'{case}__100__passive.json').write_text(json.dumps(control),encoding='utf-8')
    _,_,_,method,_,uses=execute((tmp_path,'development',case,100,False))
    assert method=='passive' and uses==0
    saved=json.loads((tmp_path/f'development/runs/{case}__100__passive.json').read_text())
    assert saved['reproduced_prior_trajectory']
