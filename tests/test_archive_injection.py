from pathlib import Path
from unittest.mock import patch

from mojssp.evaluator import Evaluator
from mojssp.io import load_dzn
from mojssp.runner import run_standalone_experiment
from run_archive_injection_pilot import run_injection

ROOT = Path(__file__).resolve().parents[1]


def test_solo_control_preserves_native_moead_trajectory():
    instance = load_dzn(ROOT/'data/validation/small_3x3.dzn')
    result = run_injection(instance,42,'moead',budget=300,population_size=10)
    native = run_standalone_experiment(instance,'MOEA/D',42*10007+17,300,50,10)
    assert result['hypervolume']==native.hypervolume
    assert set(map(tuple,result['pareto_front']))==set(native.pareto_front)
    assert result['migration_uses']==0


def test_migration_changes_only_recipient_and_keeps_exact_real_budget():
    instance = load_dzn(ROOT/'results/experiments/weighted_pilot_development_20261023/instances/development_00_5x5.dzn')
    passive = run_injection(instance,42,'passive',budget=1000,population_size=10)
    original = Evaluator.evaluate
    calls = []
    def counted(self,*a,**kw):
        calls.append(1)
        return original(self,*a,**kw)
    with patch.object(Evaluator,'evaluate',counted):
        active = run_injection(instance,42,'active',budget=1000,population_size=10)
    assert len(calls)==active['evaluations_used']==1000
    assert active['allocations']=={'MOEA/D':800,'SPEA2':200}
    assert active['spea2_trace']==passive['spea2_trace']
    assert [b['arm'] for b in active['blocks']]==[b['arm'] for b in passive['blocks']]
    assert active['migration_uses']>0
    assert passive['migration_uses']==0
    origins,seen = {},{'MOEA/D':set(),'SPEA2':set()}
    for b in active['blocks']:
        events = [e for e in active['migration_events'] if e['block_index']==b['index']]
        assert len(events)==b['used_donors']<=5
        for event in events:
            gid = event['donor_id']
            assert origins[gid]=='SPEA2'
            assert gid not in seen['MOEA/D']
            assert gid in b['global_ids_before']
            assert gid in b['prepared_donor_ids']
            assert event['recipient']=='MOEA/D' and event['source']=='SPEA2'
        for gid in b['new_observed_ids']:
            origins.setdefault(gid,b['arm'])
            seen[b['arm']].add(gid)
