"""Compare MOEA/D plus NSGA-II with local search against compatible individual controls."""
import argparse
from dataclasses import asdict
import json
import math
from pathlib import Path
import shutil
import time
from unittest.mock import patch

from run_weighted_pilot import ROOT, auc, digest, write_csv, write_json
from run_dynamic_pilot import compatible_controls
from run_portfolio_campaign import analyze
from mojssp.arms import NSGA2Arm, NSGA2LSArm
from mojssp.evaluator import Evaluator
from mojssp.hypervolume import compute_hypervolume
from mojssp.io import load_dzn
from mojssp.moead import MOEADArm
from mojssp.normalization import ObjectiveNormalizer, compute_instance_bounds
from mojssp.portfolio import Portfolio
from mojssp.reward import HypervolumeRewardTracker
from mojssp.orchestrator import AdaptivePortfolioOrchestrator
from mojssp.selectors import make_selector
from mojssp.spea2 import SPEA2Arm


def run_without_moead(instance, seed, policy, budget=3000, block_size=50, population_size=30):
    if policy not in ('uniform','scaled'):
        raise ValueError('Expected uniform or scaled policy')
    arms = {
        'NSGA-II':NSGA2Arm(instance,population_size,max_generations=None,seed=(seed*10007+29)%(2**31-1)),
        'SPEA2':SPEA2Arm(instance,population_size,archive_size=population_size,seed=(seed*10007+43)%(2**31-1)),
        'NSGA-II+LS':NSGA2LSArm(instance,population_size,max_generations=None,
            max_ls_iterations=10,max_ls_neighbors=10,seed=(seed*10007+59)%(2**31-1))}
    portfolio = Portfolio(arms)
    normalizer = ObjectiveNormalizer(compute_instance_bounds(instance))
    reward = HypervolumeRewardTracker(normalizer)
    selector = make_selector(policy,list(arms),seed=seed,window_size=10,exploration_factor=.07)
    orchestrator = AdaptivePortfolioOrchestrator(portfolio,selector,reward)
    started = time.perf_counter()
    execution = orchestrator.run(total_budget=budget,block_size=block_size,neutral_warmup=True)
    blocks = []
    used = dict.fromkeys(arms,0)
    for block in execution.history:
        row = asdict(block)
        if row['ucb_indices'] is not None:
            row['ucb_indices'] = {name:value if math.isfinite(value) else None for name,value in row['ucb_indices'].items()}
        blocks.append(row)
        used[block.arm_name] += block.evaluations_used
    assert portfolio.total_evaluations==sum(used.values())==budget
    front = [list(entry.objectives) for entry in portfolio.global_archive.entries]
    assert abs(compute_hypervolume([normalizer.normalize_tuple(p) for p in front])-reward.current_hv)<1e-12
    checkpoints = [[block.fe_after,block.hv_after] for block in execution.history]
    return dict(budget=budget,evaluations_used=budget,allocations=used,
        ls_evaluations=arms['NSGA-II+LS'].ls_evaluations,hypervolume=reward.current_hv,
        pareto_front=front,checkpoints=checkpoints,blocks=blocks,auc_hv=auc(checkpoints,budget),
        runtime_seconds=time.perf_counter()-started,completed=True)


def run_composition(instance, seed, quotas, block_size=50, population_size=30):
    if not quotas or set(quotas)-{'MOEA/D','NSGA-II+LS'}:
        raise ValueError('Expected MOEA/D and/or NSGA-II+LS quotas')
    if any(q < population_size or q % block_size for q in quotas.values()):
        raise ValueError('Quotas must cover initialization and use complete blocks')
    arms = {}
    if 'MOEA/D' in quotas:
        arms['MOEA/D'] = MOEADArm(instance,population_size=population_size,
            seed=(seed*10007+17)%(2**31-1))
    if 'NSGA-II+LS' in quotas:
        arms['NSGA-II+LS'] = NSGA2LSArm(instance,population_size=population_size,
            max_generations=None,max_ls_iterations=10,max_ls_neighbors=10,
            seed=(seed*10007+59)%(2**31-1))
    portfolio = Portfolio(arms)
    normalizer = ObjectiveNormalizer(compute_instance_bounds(instance))
    reward = HypervolumeRewardTracker(normalizer)
    used = {name:0 for name in quotas}
    history,checkpoints = [],[]
    started = time.perf_counter()
    while portfolio.total_evaluations < sum(quotas.values()):
        available = [name for name in quotas if used[name] < quotas[name]]
        name = min(available,key=lambda name:used[name]/quotas[name])
        before,hv_before = portfolio.total_evaluations,reward.current_hv
        result = portfolio.run_arm(name,block_size)
        assert result.evaluations_used==block_size
        gain = reward.compute_reward(portfolio.global_archive)
        used[name] += result.evaluations_used
        checkpoints.append([portfolio.total_evaluations,reward.current_hv])
        history.append(dict(arm=name,fe_before=before,fe_after=portfolio.total_evaluations,
                            hv_before=hv_before,hv_after=reward.current_hv,gain=gain))
    assert used==quotas
    front = [list(e.objectives) for e in portfolio.global_archive.entries]
    assert abs(compute_hypervolume([normalizer.normalize_tuple(p) for p in front])-reward.current_hv)<1e-12
    return dict(budget=sum(quotas.values()),evaluations_used=portfolio.total_evaluations,
        allocations=used,ls_evaluations=arms['NSGA-II+LS'].ls_evaluations if 'NSGA-II+LS' in arms else 0,
        hypervolume=reward.current_hv,pareto_front=front,checkpoints=checkpoints,blocks=history,
        auc_hv=auc(checkpoints,sum(quotas.values())),runtime_seconds=time.perf_counter()-started,completed=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--without-moead',action='store_true',help='Evaluate NSGA-II/SPEA2/NSGA-II+LS with uniform and scaled budgets')
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if output.exists() or not output.is_relative_to(ROOT/'results/experiments'):
        parser.error('Choose a new output inside results/experiments')
    source = ROOT/'results/experiments/weighted_pilot_development_20261023'
    previous = json.loads((source/'config.json').read_text(encoding='utf-8'))
    provenance = compatible_controls(source,previous)
    manifest = json.loads((source/'artifact_manifest.json').read_text(encoding='utf-8'))
    controls,inputs = [],{}
    for case in previous['cases']:
        path = source/'instances'/f"{case['name']}.dzn"
        assert digest(path)==case['sha256']
        inputs[str(path.relative_to(ROOT))] = digest(path)
        for seed in previous['master_seeds']:
            for method in ['moead','nsga2','spea2']:
                path = source/'runs'/f"{case['name']}__{seed}__{method}.json"
                assert digest(path)==manifest[str(path.relative_to(source)).replace('\\','/')]
                controls.append(json.loads(path.read_text(encoding='utf-8')))
                inputs[str(path.relative_to(ROOT))] = digest(path)
    treatments = [
        ('nsga2_ls',{'NSGA-II+LS':3000}),
        ('moead_nsga2_ls_50_50',{'MOEA/D':1500,'NSGA-II+LS':1500}),
        ('moead_nsga2_ls_80_20',{'MOEA/D':2400,'NSGA-II+LS':600})]
    control_methods = ['moead','nsga2','spea2']
    if args.without_moead:
        treatments = [('nsga2_spea2_ls_uniform','uniform'),('nsga2_spea2_ls_scaled','scaled')]
        locations = [
            ('moead_nsga2_ls_development_20261023','nsga2_ls'),
            ('nsga2_spea2_pair_development_20261023','nsga2_spea2_uniform'),
            ('nsga2_spea2_scaled_development_20261023','nsga2_spea2_scaled')]
        for folder,method in locations:
            location = ROOT/'results/experiments'/folder
            hashes_saved = json.loads((location/'artifact_manifest.json').read_text(encoding='utf-8'))
            for case in previous['cases']:
                assert digest(location/'code/src/mojssp/arms.py')==digest(ROOT/'src/mojssp/arms.py')
                for seed in previous['master_seeds']:
                    path = location/'runs'/f"{case['name']}__{seed}__{method}.json"
                    key = str(path.relative_to(location))
                    assert digest(path)==hashes_saved.get(key,hashes_saved.get(key.replace('\\','/')))
                    record = json.loads(path.read_text(encoding='utf-8'))
                    assert record['actual_evaluator_calls']==3000
                    controls.append(record)
                    inputs[str(path.relative_to(ROOT))] = digest(path)
            control_methods.append(method)
    expected_runs = len(previous['cases'])*len(previous['master_seeds'])*len(treatments)
    files = [*sorted((ROOT/'src/mojssp').glob('*.py')),Path(__file__).resolve(),
        ROOT/'scripts/run_weighted_pilot.py',ROOT/'scripts/run_dynamic_pilot.py',ROOT/'scripts/run_portfolio_campaign.py']
    hashes = {str(path.relative_to(ROOT)):digest(path) for path in files}
    output.mkdir(parents=True)
    for path in files:
        destination = output/'code'/path.relative_to(ROOT)
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,destination)
    for case in previous['cases']:
        destination = output/'instances'/f"{case['name']}.dzn"
        destination.parent.mkdir(exist_ok=True)
        shutil.copy2(source/'instances'/destination.name,destination)
    write_json(output/'config.json',dict(cases=previous['cases'],seeds=previous['master_seeds'],
        treatments=treatments,budget=3000,block_size=50,population_size=30,
        without_moead=args.without_moead,policies=dict(window_size=10,exploration_factor=.07,neutral_warmup=True),
        local_search=dict(max_ls_iterations=10,max_ls_neighbors=10,max_generations=None,
                          other_parameters='NSGA2LSArm defaults; see frozen source'),
        seed_offsets={'MOEA/D':17,'NSGA-II':29,'SPEA2':43,'NSGA-II+LS':59},seed_formula='(master_seed*10007+offset) modulo (2**31-1)',
        budget_rule='Native orchestrator with neutral warmup for no-MOEA/D treatments; otherwise fixed quota proportions; initialization included',
        cooperation='Passive union of cumulative archives; no external parents or population injection',
        source_sha256=hashes,input_sha256=inputs,control_provenance=provenance,
        scope='Six development cases, three seeds; saved control timings are descriptive'))
    original = Evaluator.evaluate
    records,allocations = [],[]
    for ci,case in enumerate(previous['cases']):
        instance = load_dzn(output/'instances'/f"{case['name']}.dzn")
        for si,seed in enumerate(previous['master_seeds']):
            shift = (ci*3+si)%len(treatments)
            for method,quotas in treatments[shift:]+treatments[:shift]:
                assert all(digest(ROOT/path)==sha for path,sha in hashes.items())
                calls = 0
                def counted(self,*a,**kw):
                    nonlocal calls
                    calls += 1
                    return original(self,*a,**kw)
                try:
                    with patch.object(Evaluator,'evaluate',counted):
                        record = (run_without_moead(instance,seed,quotas) if args.without_moead
                                  else run_composition(instance,seed,quotas))
                    assert calls==record['evaluations_used']==3000
                    assert record['ls_evaluations']<=record['allocations']['NSGA-II+LS']
                    record.update(case=case['name'],instance=case['name'],master_seed=seed,
                                  method=method,actual_evaluator_calls=calls)
                    write_json(output/'runs'/f"{case['name']}__{seed}__{method}.json",record)
                except Exception as error:
                    write_json(output/'failure.json',dict(case=case['name'],seed=seed,method=method,
                        actual_evaluator_calls=calls,error=repr(error)))
                    raise
                records.append(record)
                allocations.append(dict(case=case['name'],seed=seed,method=method,
                    moead_fe=record['allocations'].get('MOEA/D',0),
                    nsga2_ls_fe=record['allocations']['NSGA-II+LS'],local_search_fe=record['ls_evaluations']))
                print(f"{len(records)}/{expected_runs} {case['name']} seed={seed} {method} HV={record['hypervolume']:.6f} LS_FE={record['ls_evaluations']}",flush=True)
    analyze(output,controls+records,[method for method,_ in treatments],control_methods)
    write_csv(output/'allocations.csv',allocations)
    assert len(records)==expected_runs
    write_json(output/'validation.json',dict(new_runs=expected_runs,new_search_fe=sum(r['actual_evaluator_calls'] for r in records),
        all_budgets_exact=True,all_final_hv_recomputed=True,all_local_search_fe_included=True,reused_controls=len(controls)))
    write_json(output/'artifact_manifest.json',{str(p.relative_to(output)):digest(p)
        for p in sorted(output.rglob('*')) if p.is_file() and p.name!='artifact_manifest.json'})


if __name__=='__main__':
    main()
