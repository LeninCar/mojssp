from pathlib import Path
from unittest.mock import patch

from mojssp.evaluator import Evaluator
from mojssp.decoder import Decoder
from mojssp.io import load_dzn
from mojssp.normalization import ObjectiveNormalizer, compute_instance_bounds
from mojssp.pareto_archive import ArchiveEntry
from mojssp.regional_explorer import RegionalExplorerArm, region_geometry
from mojssp.solution import Solution
import random
from run_regional_cooperation_pilot import run_regional
from run_regional_explorer_controls import run_individual
from run_regional_budget_pilot import run_explorer_dominant

ROOT = Path(__file__).resolve().parents[1]


def test_constant_objectives_are_removed_and_duplicate_vectors_do_not_inflate_density():
    points = [(.1,0,.9),(.5,0,.5),(.9,0,.1),(.1,0,.9)]
    geometry = region_geometry(points)
    assert geometry['active_objectives']==[True,False,True]
    assert len(geometry['weights'])==3
    assert all(w[1]==0 for w in geometry['weights'])
    assert geometry['densities']==[1,1,1]


def test_regional_pair_uses_real_evaluations_and_leaves_moead_unchanged():
    instance = load_dzn(ROOT/'data/validation/small_3x3.dzn')
    random_control = run_regional(instance,42,'random_regions',budget=500,population_size=10)
    original = Evaluator.evaluate
    calls = []
    def counted(self,*a,**kw):
        calls.append(1)
        return original(self,*a,**kw)
    with patch.object(Evaluator,'evaluate',counted):
        sparse = run_regional(instance,42,'sparse_regions',budget=500,population_size=10)
    assert len(calls)==sparse['evaluations_used']==500
    assert sparse['allocations']=={'MOEA/D':400,'RegionExplorer':100}
    assert sparse['moead_trace']==random_control['moead_trace']
    assert len(sparse['region_trace'])==2
    assert sum(sum(row['operators'].values()) for row in sparse['region_trace'])==100
    for row in sparse['region_trace']:
        g = row['geometry']
        assert g['densities'][row['selected_region']]==min(g['densities'])
        assert set(row['seed_parent_ids'])<=set(row['global_parent_ids'])


def test_energy_directed_mode_move_reduces_evaluated_energy():
    instance = load_dzn(ROOT/'data/validation/small_3x3.dzn')
    initial = Solution.random(instance,rng=random.Random(3))
    solution = Solution(initial.sequence,tuple(max(op.modes,key=lambda m:m.energy).mode_id for op in instance.all_operations))
    schedule = Decoder().decode(instance,solution)
    objectives = Evaluator().evaluate(instance,schedule)
    parent = ArchiveEntry(solution,schedule,objectives)
    explorer = RegionalExplorerArm(instance,ObjectiveNormalizer(compute_instance_bounds(instance)))
    explorer._weight = (0.,0.,1.)
    child,operator = explorer._mode_move(parent)
    child.validate_with_instance(instance)
    evaluated = Evaluator().evaluate(instance,Decoder().decode(instance,child))
    assert operator=='directed_mode'
    assert child.sequence==solution.sequence
    assert evaluated.energy<objectives.energy


def test_individual_explorer_pays_for_initialization_within_total_budget():
    instance = load_dzn(ROOT/'data/validation/small_3x3.dzn')
    original = Evaluator.evaluate
    calls = []
    def counted(self,*a,**kw):
        calls.append(1)
        return original(self,*a,**kw)
    with patch.object(Evaluator,'evaluate',counted):
        result = run_individual(instance,42,'sparse',budget=300,population_size=10)
    assert len(calls)==result['evaluations_used']==300
    assert result['initialization_fe']==10 and result['evolution_fe']==290
    assert sum(row['evaluations'] for row in result['region_trace'])==290
    assert result['checkpoints'][0][0]==50


def test_explorer_dominant_pair_counts_both_quotas_exactly():
    instance = load_dzn(ROOT/'data/validation/small_3x3.dzn')
    original = Evaluator.evaluate
    calls = []
    def counted(self,*a,**kw):
        calls.append(1)
        return original(self,*a,**kw)
    with patch.object(Evaluator,'evaluate',counted):
        result = run_explorer_dominant(instance,42,budget=500,population_size=10)
    assert len(calls)==result['evaluations_used']==500
    assert result['allocations']=={'MOEA/D':100,'RegionExplorer':400}
    assert sum(row['evaluations'] for row in result['region_trace'])==400
