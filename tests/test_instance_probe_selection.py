from pathlib import Path
from unittest.mock import patch
from mojssp.evaluator import Evaluator
from mojssp.io import load_dzn
from mojssp.runner import run_standalone_experiment
from run_instance_probe_selection import run_probe


def test_probe_cost_is_included_and_selected_state_continues_without_restart():
    root = Path(__file__).resolve().parents[1]
    instance = load_dzn(root/'data/validation/small_3x3.dzn')
    original = Evaluator.evaluate
    calls = []
    def counted(self,*a,**kw):
        calls.append(1)
        return original(self,*a,**kw)
    with patch.object(Evaluator,'evaluate',counted):
        r = run_probe(instance,42,50,'greedy',None,budget=300,population_size=10)
    assert len(calls)==300
    assert sorted(r['allocations'].values())==[50,250]
    points = set()
    for method,name,offset in [('nsga2','NSGA-II',29),('spea2','SPEA2',43)]:
        result = run_standalone_experiment(instance,name,42*10007+offset,r['allocations'][method],50,10)
        points.update(map(tuple,result.pareto_front))
    nondominated = {p for p in points if not any(q!=p and all(a<=b for a,b in zip(q,p)) for q in points)}
    assert set(map(tuple,r['pareto_front']))==nondominated
