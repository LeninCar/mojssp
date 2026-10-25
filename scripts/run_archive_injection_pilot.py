"""Matched solo, passive and unidirectional external-parent injection experiment."""
import argparse
import json
from pathlib import Path
import shutil
import time
from unittest.mock import patch

from run_weighted_pilot import ROOT, auc, digest, write_csv, write_json
from run_portfolio_campaign import analyze
from mojssp.archive_injection import ArchiveParentInjection
from mojssp.evaluator import Evaluator
from mojssp.hypervolume import compute_archive_hypervolume, compute_hypervolume
from mojssp.io import load_dzn
from mojssp.moead import MOEADArm
from mojssp.normalization import ObjectiveNormalizer, compute_instance_bounds
from mojssp.portfolio import Portfolio
from mojssp.provenance import compute_genotype_id
from mojssp.reward import HypervolumeRewardTracker
from mojssp.spea2 import SPEA2Arm


def fixed_schedule(quotas, block_size):
    if any(q % block_size for q in quotas.values()):
        raise ValueError('Quotas must be divisible by block size')
    used = dict.fromkeys(quotas,0)
    schedule = []
    while sum(used.values())<sum(quotas.values()):
        available = [name for name in quotas if used[name]<quotas[name]]
        name = min(available,key=lambda name:used[name]/quotas[name])
        schedule.append(name)
        used[name] += block_size
    return schedule


def archive_ids(arm):
    return sorted(compute_genotype_id(entry.solution) for entry in arm.current_archive.entries)


def run_injection(instance, seed, method, budget=3000, block_size=50, population_size=30, m=5):
    if method not in ('moead','passive','active'):
        raise ValueError('Expected moead, passive or active')
    quotas = {'MOEA/D':budget} if method=='moead' else {'MOEA/D':budget*4//5,'SPEA2':budget//5}
    if sum(quotas.values())!=budget or min(quotas.values())<population_size:
        raise ValueError('Budget must cover full initial populations')
    arms = {'MOEA/D':MOEADArm(instance,population_size=population_size,seed=(seed*10007+17)%(2**31-1))}
    if method!='moead':
        arms['SPEA2'] = SPEA2Arm(instance,population_size=population_size,archive_size=population_size,
                                seed=(seed*10007+43)%(2**31-1))
    portfolio = Portfolio(arms)
    norm = ObjectiveNormalizer(compute_instance_bounds(instance))
    tracker = HypervolumeRewardTracker(norm)
    guide = ArchiveParentInjection(instance,norm,m=m,every=10)
    if method=='active':
        arms['MOEA/D'].set_archive_guidance(guide)
    used = dict.fromkeys(arms,0)
    history,checkpoints,spea2_trace = [],[],[]
    started = time.perf_counter()
    for index,name in enumerate(fixed_schedule(quotas,block_size)):
        before,hv_before = portfolio.total_evaluations,tracker.current_hv
        global_ids_before = (sorted(compute_genotype_id(entry.solution) for entry in portfolio.global_archive.entries)
                             if method=='active' and name=='MOEA/D' else [])
        selected = guide.prepare(arms[name],portfolio.global_archive,index,before) if method=='active' and name=='MOEA/D' else []
        events_before = len(guide.events)
        seen_before = set(guide.seen_by.get(name,set()))
        result = portfolio.run_arm(name,block_size)
        assert result.evaluations_used==block_size
        used[name] += result.evaluations_used
        guide.observe(arms[name])
        gain = tracker.compute_reward(portfolio.global_archive)
        checkpoints.append([portfolio.total_evaluations,tracker.current_hv])
        row = dict(index=index,arm=name,fe_before=before,fe_after=portfolio.total_evaluations,
            hv_before=hv_before,hv_after=tracker.current_hv,gain=gain,
            prepared_donor_ids=selected,used_donors=len(guide.events)-events_before,
            global_ids_before=global_ids_before,new_observed_ids=sorted(guide.seen_by[name]-seen_before))
        assert row['used_donors']<=m
        history.append(row)
        if name=='SPEA2':
            spea2_trace.append(dict(fe=used[name],ids=archive_ids(arms[name]),
                hv=compute_archive_hypervolume(arms[name].current_archive,norm)))
    assert used==quotas and portfolio.total_evaluations==budget
    front = [list(entry.objectives) for entry in portfolio.global_archive.entries]
    assert abs(compute_hypervolume([norm.normalize_tuple(p) for p in front])-tracker.current_hv)<1e-12
    return dict(budget=budget,evaluations_used=budget,hypervolume=tracker.current_hv,pareto_front=front,
        runtime_seconds=time.perf_counter()-started,auc_hv=auc(checkpoints,budget),checkpoints=checkpoints,
        allocations=used,blocks=history,migration_events=guide.events,migration_uses=len(guide.events),
        moead_local_hv=compute_archive_hypervolume(arms['MOEA/D'].current_archive,norm),
        moead_front=[list(entry.objectives) for entry in arms['MOEA/D'].current_archive.entries],
        spea2_trace=spea2_trace,completed=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if output.exists() or not output.is_relative_to(ROOT/'results/experiments'):
        parser.error('Choose a new directory inside results/experiments')
    source = ROOT/'results/experiments/weighted_pilot_development_20261023'
    prior = json.loads((source/'config.json').read_text(encoding='utf-8'))
    methods = ['moead','passive','active']
    files = [*sorted((ROOT/'src/mojssp').glob('*.py')),Path(__file__).resolve(),
             ROOT/'scripts/run_weighted_pilot.py',ROOT/'scripts/run_portfolio_campaign.py',ROOT/'scripts/run_dynamic_pilot.py']
    hashes = {str(p.relative_to(ROOT)):digest(p) for p in files}
    output.mkdir(parents=True)
    for p in files:
        destination = output/'code'/p.relative_to(ROOT)
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(p,destination)
    inputs = {}
    for case in prior['cases']:
        path = source/'instances'/f"{case['name']}.dzn"
        assert digest(path)==case['sha256']
        inputs[str(path.relative_to(ROOT))] = digest(path)
        destination = output/'instances'/path.name
        destination.parent.mkdir(exist_ok=True)
        shutil.copy2(path,destination)
    write_json(output/'config.json',dict(cases=prior['cases'],seeds=prior['master_seeds'],methods=methods,
        budget=3000,block_size=50,population_size=30,pair_quotas={'MOEA/D':2400,'SPEA2':600},
        migration=dict(source='SPEA2',recipient='MOEA/D',m=5,every=10,
            type='External parent replacement during native mating, not incumbent population replacement',
            eligibility='Global Pareto archive; first observed in SPEA2; never observed in MOEA/D archive or population',
            selection='Deterministic max-min normalized objective distance from recipient archive and already selected donors',
            cadence='Prepare before each MOEA/D block; use one donor every ten mating calls, at most five per block',
            provenance='Observe executed arm immediately after each block; archive and current MOEA/D population membership'),
        schedule='Least consumed quota proportion, stable MOEA/D then SPEA2 tie order; identical active/passive schedule',
        seed_formula='(master_seed*10007+offset) modulo (2**31-1)',seed_offsets={'MOEA/D':17,'SPEA2':43},
        evaluation_accounting='All native offspring and initial population evaluations counted; donors already evaluated on same instance; no donor-only extra FE',
        primary_comparisons=['active minus passive global HV','active minus solo global HV'],
        secondary='MOEA/D local archive HV; source SPEA2 trace equality; used migration events',
        source_sha256=hashes,input_sha256=inputs,new_runs=54,new_search_fe=162000,
        scope='Six development instances, three seeds; exploratory, no holdout selection'))
    original = Evaluator.evaluate
    records,allocations = [],[]
    for ci,case in enumerate(prior['cases']):
        instance = load_dzn(output/'instances'/f"{case['name']}.dzn")
        for si,seed in enumerate(prior['master_seeds']):
            shift = (ci*3+si)%3
            paired = {}
            for method in methods[shift:]+methods[:shift]:
                assert all(digest(ROOT/p)==sha for p,sha in hashes.items())
                calls = 0
                def counted(self,*a,**kw):
                    nonlocal calls
                    calls += 1
                    return original(self,*a,**kw)
                try:
                    with patch.object(Evaluator,'evaluate',counted):
                        record = run_injection(instance,seed,method)
                    assert calls==record['evaluations_used']==3000
                    record.update(case=case['name'],master_seed=seed,method=method,actual_evaluator_calls=calls)
                    write_json(output/'runs'/f"{case['name']}__{seed}__{method}.json",record)
                except Exception as error:
                    write_json(output/'failure.json',dict(case=case['name'],seed=seed,method=method,
                        actual_evaluator_calls=calls,error=repr(error)))
                    raise
                records.append(record)
                paired[method] = record
                allocations.append(dict(case=case['name'],seed=seed,method=method,moead_fe=record['allocations']['MOEA/D'],
                    spea2_fe=record['allocations'].get('SPEA2',0),migration_uses=record['migration_uses'],
                    moead_local_hv=record['moead_local_hv'],global_hv=record['hypervolume']))
                print(f"{len(records)}/54 {case['name']} seed={seed} {method} HV={record['hypervolume']:.6f} uses={record['migration_uses']}",flush=True)
            assert paired['passive']['spea2_trace']==paired['active']['spea2_trace']
            assert [b['arm'] for b in paired['passive']['blocks']]==[b['arm'] for b in paired['active']['blocks']]
    analyze(output,records,['active'],['moead','passive'])
    write_csv(output/'allocations.csv',allocations)
    write_json(output/'validation.json',dict(new_runs=len(records),new_search_fe=sum(r['actual_evaluator_calls'] for r in records),
        all_budgets_exact=True,source_traces_identical=True,pair_schedules_identical=True,
        total_migration_uses=sum(r['migration_uses'] for r in records),runs_with_migration=sum(r['migration_uses']>0 for r in records)))
    write_json(output/'artifact_manifest.json',{str(p.relative_to(output)):digest(p)
        for p in sorted(output.rglob('*')) if p.is_file() and p.name!='artifact_manifest.json'})


if __name__=='__main__':
    main()
