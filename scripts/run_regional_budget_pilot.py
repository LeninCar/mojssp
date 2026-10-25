"""Evaluate an explorer-dominant regional portfolio after individual screening."""
import argparse
import json
from pathlib import Path
import shutil
import time
from unittest.mock import patch

from run_weighted_pilot import ROOT,auc,digest,write_csv,write_json
from run_archive_injection_pilot import fixed_schedule,archive_ids
from mojssp.evaluator import Evaluator
from mojssp.hypervolume import compute_archive_hypervolume,compute_hypervolume
from mojssp.io import load_dzn
from mojssp.moead import MOEADArm
from mojssp.normalization import ObjectiveNormalizer,compute_instance_bounds
from mojssp.portfolio import Portfolio
from mojssp.provenance import compute_genotype_id
from mojssp.regional_explorer import RegionalExplorerArm
from mojssp.reward import HypervolumeRewardTracker


def run_explorer_dominant(instance,seed,budget=3000,population_size=30,block_size=50):
    quotas = {'MOEA/D':budget//5,'RegionExplorer':budget*4//5}
    if sum(quotas.values())!=budget or quotas['MOEA/D']<population_size:
        raise ValueError('Invalid budget')
    norm = ObjectiveNormalizer(compute_instance_bounds(instance))
    arms = {'MOEA/D':MOEADArm(instance,population_size=population_size,seed=(seed*10007+17)%(2**31-1)),
            'RegionExplorer':RegionalExplorerArm(instance,norm,policy='random',seed=(seed*10007+71)%(2**31-1),
                max_evaluations=quotas['RegionExplorer'],parent_count=5)}
    portfolio = Portfolio(arms)
    tracker = HypervolumeRewardTracker(norm)
    used = dict.fromkeys(arms,0)
    blocks,checkpoints,moead_trace = [],[],[]
    started = time.perf_counter()
    for index,name in enumerate(fixed_schedule(quotas,block_size)):
        before,hv_before = portfolio.total_evaluations,tracker.current_hv
        if name=='RegionExplorer':
            archive = portfolio.global_archive
            row = arms[name].prepare(archive)
            row['global_fe_before'] = before
            row['global_parent_ids'] = sorted(compute_genotype_id(entry.solution) for entry in archive.entries)
        result = portfolio.run_arm(name,block_size)
        assert result.evaluations_used==block_size
        used[name] += block_size
        gain = tracker.compute_reward(portfolio.global_archive)
        checkpoints.append([portfolio.total_evaluations,tracker.current_hv])
        blocks.append(dict(index=index,arm=name,fe_before=before,fe_after=portfolio.total_evaluations,
                           hv_before=hv_before,hv_after=tracker.current_hv,gain=gain))
        if name=='MOEA/D':
            moead_trace.append(dict(fe=used[name],ids=archive_ids(arms[name]),hv=compute_archive_hypervolume(arms[name].current_archive,norm)))
    assert used==quotas and portfolio.total_evaluations==budget
    front = [list(e.objectives) for e in portfolio.global_archive.entries]
    assert abs(compute_hypervolume([norm.normalize_tuple(p) for p in front])-tracker.current_hv)<1e-12
    return dict(budget=budget,evaluations_used=budget,hypervolume=tracker.current_hv,pareto_front=front,
        allocations=used,blocks=blocks,checkpoints=checkpoints,moead_trace=moead_trace,
        moead_local_hv=compute_archive_hypervolume(arms['MOEA/D'].current_archive,norm),
        region_trace=arms['RegionExplorer'].trace,
        explorer_front=[dict(sequence=list(e.solution.sequence),modes=list(e.solution.modes),objectives=list(e.objectives))
                        for e in arms['RegionExplorer'].current_archive.entries],
        auc_hv=auc(checkpoints,budget),runtime_seconds=time.perf_counter()-started,completed=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if output.exists() or not output.is_relative_to(ROOT/'results/experiments'):
        parser.error('Choose a new output inside results/experiments')
    source = ROOT/'results/experiments/weighted_pilot_development_20261023'
    prior = json.loads((source/'config.json').read_text(encoding='utf-8'))
    files = [*sorted((ROOT/'src/mojssp').glob('*.py')),Path(__file__).resolve(),ROOT/'scripts/run_weighted_pilot.py',
             ROOT/'scripts/run_archive_injection_pilot.py',ROOT/'scripts/run_portfolio_campaign.py',ROOT/'scripts/run_dynamic_pilot.py']
    hashes = {str(p.relative_to(ROOT)):digest(p) for p in files}
    output.mkdir(parents=True)
    for path in files:
        target = output/'code'/path.relative_to(ROOT)
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,target)
    for case in prior['cases']:
        path = source/'instances'/f"{case['name']}.dzn"
        assert digest(path)==case['sha256']
        target = output/'instances'/path.name
        target.parent.mkdir(exist_ok=True)
        shutil.copy2(path,target)
    write_json(output/'config.json',dict(cases=prior['cases'],seeds=prior['master_seeds'],
        budget=3000,block_size=50,population_size=30,quotas={'MOEA/D':600,'RegionExplorer':2400},
        region_policy='random',parent_count=5,source_sha256=hashes,
        hypothesis='Allocate more budget to the newly stronger explorer; test whether MOEA/D archive seeds compensate the reduced explorer quota',
        scope='Exploratory follow-up motivated by development results; same six instances, not independent confirmation',
        comparison='Solo MOEA/D, explorer individuals and 80/20 pairs stored in the two regional campaigns'))
    original = Evaluator.evaluate
    records = []
    for case in prior['cases']:
        instance = load_dzn(output/'instances'/f"{case['name']}.dzn")
        for seed in prior['master_seeds']:
            assert all(digest(ROOT/path)==sha for path,sha in hashes.items())
            calls = 0
            def counted(self,*a,**kw):
                nonlocal calls
                calls += 1
                return original(self,*a,**kw)
            try:
                with patch.object(Evaluator,'evaluate',counted):
                    r = run_explorer_dominant(instance,seed)
                assert calls==r['evaluations_used']==3000
                r.update(case=case['name'],master_seed=seed,method='explorer_dominant_random',actual_evaluator_calls=calls)
                write_json(output/'runs'/f"{case['name']}__{seed}__explorer_dominant_random.json",r)
            except Exception as error:
                write_json(output/'failure.json',dict(case=case['name'],seed=seed,error=repr(error),actual_evaluator_calls=calls))
                raise
            records.append(r)
            print(f"{len(records)}/18 {case['name']} seed={seed} HV={r['hypervolume']:.6f}",flush=True)
    write_csv(output/'runs.csv',[{k:r[k] for k in ['case','master_seed','method','hypervolume','auc_hv','runtime_seconds']} for r in records])
    write_json(output/'validation.json',dict(new_runs=len(records),new_search_fe=sum(r['actual_evaluator_calls'] for r in records),
        all_budgets_exact=True,quotas={'MOEA/D':600,'RegionExplorer':2400}))
    write_json(output/'artifact_manifest.json',{str(p.relative_to(output)):digest(p)
        for p in sorted(output.rglob('*')) if p.is_file() and p.name!='artifact_manifest.json'})


if __name__=='__main__':
    main()
