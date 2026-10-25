"""Matched MOEA/D and archive-region explorer pilot with random-region control."""
import argparse
import json
from pathlib import Path
import shutil
import time
from unittest.mock import patch

from run_weighted_pilot import ROOT, auc, digest, write_csv, write_json
from run_archive_injection_pilot import fixed_schedule, archive_ids
from run_portfolio_campaign import analyze
from mojssp.evaluator import Evaluator
from mojssp.hypervolume import compute_archive_hypervolume, compute_hypervolume
from mojssp.io import load_dzn
from mojssp.moead import MOEADArm
from mojssp.normalization import ObjectiveNormalizer, compute_instance_bounds
from mojssp.portfolio import Portfolio
from mojssp.provenance import compute_genotype_id
from mojssp.regional_explorer import RegionalExplorerArm
from mojssp.reward import HypervolumeRewardTracker


def run_regional(instance,seed,method,budget=3000,block_size=50,population_size=30):
    if method not in ('moead','random_regions','sparse_regions'):
        raise ValueError('Unknown regional treatment')
    norm = ObjectiveNormalizer(compute_instance_bounds(instance))
    arms = {'MOEA/D':MOEADArm(instance,population_size=population_size,seed=(seed*10007+17)%(2**31-1))}
    quotas = {'MOEA/D':budget}
    if method!='moead':
        quotas = {'MOEA/D':budget*4//5,'RegionExplorer':budget//5}
        arms['RegionExplorer'] = RegionalExplorerArm(instance,norm,
            policy='random' if method=='random_regions' else 'sparse',
            seed=(seed*10007+71)%(2**31-1),max_evaluations=quotas['RegionExplorer'],parent_count=5)
    if sum(quotas.values())!=budget or quotas['MOEA/D']<population_size:
        raise ValueError('Invalid total or initialization budget')
    portfolio = Portfolio(arms)
    tracker = HypervolumeRewardTracker(norm)
    used = dict.fromkeys(arms,0)
    history,checkpoints,moead_trace = [],[],[]
    started = time.perf_counter()
    for index,name in enumerate(fixed_schedule(quotas,block_size)):
        before,hv_before = portfolio.total_evaluations,tracker.current_hv
        if name=='RegionExplorer':
            archive = portfolio.global_archive
            region = arms[name].prepare(archive)
            region['global_fe_before'] = before
            region['global_parent_ids'] = sorted(compute_genotype_id(entry.solution) for entry in archive.entries)
        result = portfolio.run_arm(name,block_size)
        assert result.evaluations_used==block_size
        used[name] += block_size
        gain = tracker.compute_reward(portfolio.global_archive)
        history.append(dict(index=index,arm=name,fe_before=before,fe_after=portfolio.total_evaluations,
                            hv_before=hv_before,hv_after=tracker.current_hv,gain=gain))
        checkpoints.append([portfolio.total_evaluations,tracker.current_hv])
        if name=='MOEA/D':
            moead_trace.append(dict(fe=used[name],ids=archive_ids(arms[name]),hv=compute_archive_hypervolume(arms[name].current_archive,norm)))
    assert used==quotas and portfolio.total_evaluations==budget
    front = [list(entry.objectives) for entry in portfolio.global_archive.entries]
    assert abs(compute_hypervolume([norm.normalize_tuple(p) for p in front])-tracker.current_hv)<1e-12
    explorer = arms.get('RegionExplorer')
    return dict(budget=budget,evaluations_used=budget,hypervolume=tracker.current_hv,pareto_front=front,
        runtime_seconds=time.perf_counter()-started,auc_hv=auc(checkpoints,budget),checkpoints=checkpoints,
        allocations=used,blocks=history,moead_trace=moead_trace,
        moead_local_hv=compute_archive_hypervolume(arms['MOEA/D'].current_archive,norm),
        region_trace=explorer.trace if explorer else [],
        explorer_front=[dict(sequence=list(entry.solution.sequence),modes=list(entry.solution.modes),objectives=list(entry.objectives))
                        for entry in explorer.current_archive.entries] if explorer else [],completed=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if output.exists() or not output.is_relative_to(ROOT/'results/experiments'):
        parser.error('Choose a new directory inside results/experiments')
    source = ROOT/'results/experiments/weighted_pilot_development_20261023'
    prior = json.loads((source/'config.json').read_text(encoding='utf-8'))
    methods = ['moead','random_regions','sparse_regions']
    files = [*sorted((ROOT/'src/mojssp').glob('*.py')),Path(__file__).resolve(),ROOT/'scripts/run_archive_injection_pilot.py',
             ROOT/'scripts/run_weighted_pilot.py',ROOT/'scripts/run_portfolio_campaign.py',ROOT/'scripts/run_dynamic_pilot.py']
    hashes = {str(p.relative_to(ROOT)):digest(p) for p in files}
    output.mkdir(parents=True)
    for p in files:
        target = output/'code'/p.relative_to(ROOT)
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(p,target)
    inputs = {}
    for case in prior['cases']:
        path = source/'instances'/f"{case['name']}.dzn"
        assert digest(path)==case['sha256']
        inputs[str(path.relative_to(ROOT))] = digest(path)
        target = output/'instances'/path.name
        target.parent.mkdir(exist_ok=True)
        shutil.copy2(path,target)
    write_json(output/'config.json',dict(cases=prior['cases'],seeds=prior['master_seeds'],methods=methods,
        budget=3000,block_size=50,population_size=30,pair_quotas={'MOEA/D':2400,'RegionExplorer':600},
        parent_count=5,reference_directions='Three objective axes, three pairwise combinations, balanced; project away constant observed objectives',
        association='Cosine distance in normalized achievement space (observed nadir minus f)/(nadir minus ideal)',
        density='Distinct global objective vectors per cell; equal objective vectors counted once',
        sparse_policy='Uniform random tie-break among least populated cells; not an HV-contribution policy',
        random_control='Uniform random cell; identical parent selection, local acceptance, operators and budget',
        operators=['Critical-path sequence swap','Late-job priority swap for tardiness-directed cells','Mode choice using weighted duration/energy proxy'],
        operator_probability='Mode 0.8 for energy-dominant; 0.3 for time-dominant; otherwise 0.5',
        local_acceptance='Five-parent working pool ranked by weighted Tchebycheff score against the frozen block geometry',
        initialization='Explorer reuses evaluated global parents, with no independent random population; all children count as real FE',
        exchange='Global archive to explorer at every explorer block; no injection into MOEA/D',
        seed_formula='(master_seed*10007+offset) modulo (2**31-1)',seed_offsets={'MOEA/D':17,'RegionExplorer':71},
        schedule='Same least-consumed quota schedule for both pairs, block size 50',
        primary_comparisons=['Sparse minus random region selection','Sparse minus solo MOEA/D'],
        secondary_comparison='Random region selection minus solo MOEA/D',
        source_sha256=hashes,input_sha256=inputs,new_runs=54,new_search_fe=162000,
        scope='Six development instances and three seeds; no tuning on evaluation instances'))
    original = Evaluator.evaluate
    records,allocation_rows = [],[]
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
                        r = run_regional(instance,seed,method)
                    assert calls==r['evaluations_used']==3000
                    r.update(case=case['name'],master_seed=seed,method=method,actual_evaluator_calls=calls)
                    write_json(output/'runs'/f"{case['name']}__{seed}__{method}.json",r)
                except Exception as error:
                    write_json(output/'failure.json',dict(case=case['name'],seed=seed,method=method,error=repr(error),actual_evaluator_calls=calls))
                    raise
                records.append(r)
                paired[method] = r
                allocation_rows.append(dict(case=case['name'],seed=seed,method=method,
                    moead_fe=r['allocations']['MOEA/D'],explorer_fe=r['allocations'].get('RegionExplorer',0),
                    targeted_blocks=len(r['region_trace'])))
                print(f"{len(records)}/54 {case['name']} seed={seed} {method} HV={r['hypervolume']:.6f}",flush=True)
            assert paired['random_regions']['moead_trace']==paired['sparse_regions']['moead_trace']
            assert [b['arm'] for b in paired['random_regions']['blocks']]==[b['arm'] for b in paired['sparse_regions']['blocks']]
    analyze(output,records,['sparse_regions'],['moead','random_regions'])
    write_csv(output/'allocations.csv',allocation_rows)
    write_json(output/'validation.json',dict(new_runs=len(records),new_search_fe=sum(r['actual_evaluator_calls'] for r in records),
        all_budgets_exact=True,moead_traces_identical_in_pairs=True,pair_schedules_identical=True,
        total_explorer_blocks=sum(len(r['region_trace']) for r in records)))
    write_json(output/'artifact_manifest.json',{str(p.relative_to(output)):digest(p)
        for p in sorted(output.rglob('*')) if p.is_file() and p.name!='artifact_manifest.json'})


if __name__=='__main__':
    main()
