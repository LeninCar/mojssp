from pathlib import Path
from unittest.mock import patch

from mojssp.evaluator import Evaluator
from mojssp.io import load_dzn
from mojssp.runner import run_standalone_experiment
from run_stagnation_pilot import run_intervention

ROOT = Path(__file__).resolve().parents[1]


def test_disabled_detection_matches_native_moead_and_uses_no_spea2_budget():
    instance = load_dzn(ROOT/'data/validation/small_3x3.dzn')
    record = run_intervention(instance,42,0,budget=300,block_size=50,population_size=10)
    solo = run_standalone_experiment(instance,'MOEA/D',42*10007+17,300,50,10)
    assert set(map(tuple,record['pareto_front']))==set(solo.pareto_front)
    assert record['hypervolume']==solo.hypervolume
    assert record['allocations']=={'MOEA/D':300,'SPEA2':0}


def test_two_low_gain_blocks_trigger_one_rescue_and_return_with_exact_real_budget():
    instance = load_dzn(ROOT/'data/validation/small_3x3.dzn')
    original = Evaluator.evaluate
    calls = []
    def counted(self,*a,**kw):
        calls.append(1)
        return original(self,*a,**kw)
    with patch.object(Evaluator,'evaluate',counted):
        record = run_intervention(instance,42,10,budget=300,block_size=50,population_size=10)
    assert len(calls)==300
    assert [b['arm'] for b in record['blocks']]==['MOEA/D','MOEA/D','SPEA2']*2
    assert record['allocations']=={'MOEA/D':200,'SPEA2':100}
    assert record['interventions']==2
    assert all(b['streak_after']==0 for b in record['blocks'] if b['arm']=='SPEA2')
