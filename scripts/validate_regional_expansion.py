"""Frozen regional comparison with fresh seeds, transfer cases and exact FE audit."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import random
import shutil
from unittest.mock import patch

from run_weighted_pilot import ROOT, digest, write_csv, write_json
from run_regional_cooperation_pilot import run_regional
from run_regional_budget_pilot import run_explorer_dominant
from run_regional_explorer_controls import run_individual
from mojssp.evaluator import Evaluator
from mojssp.decoder import Decoder
from mojssp.io import load_dzn
from mojssp.normalization import ObjectiveNormalizer, compute_instance_bounds
from mojssp.schedule_validator import validate_schedule
from mojssp.solution import Solution
import numpy as np


def independent_hv(points, reference=(1.1,1.1,1.1)):
    """Union of boxes by a 2D grid and minimum covering z; no project HV calls."""
    p = np.unique(np.asarray(points,dtype=float),axis=0)
    p = p[np.all(p < np.asarray(reference),axis=1)]
    if not len(p):
        return 0.
    xs = sorted(set(p[:,0])|{reference[0]})
    ys = sorted(set(p[:,1])|{reference[1]})
    volume = 0.
    for x,x1 in zip(xs,xs[1:]):
        active = p[p[:,0]<=x]
        for y,y1 in zip(ys,ys[1:]):
            covered = active[active[:,1]<=y]
            if len(covered):
                volume += (x1-x)*(y1-y)*(reference[2]-float(covered[:,2].min()))
    return volume


def summarize(output, records):
    write_csv(output/'runs.csv',records)
    means = defaultdict(list)
    for r in records:
        means[r['group'],r['case'],r['method']].append(r['hypervolume'])
    cases = sorted({(r['group'],r['case']) for r in records})
    bycase = [dict(group=g,case=c,**{m:float(np.mean(means[g,c,m])) for m in METHODS}) for g,c in cases]
    write_csv(output/'by_instance.csv',bycase)
    rows, comparisons = [],[]
    rng = np.random.default_rng(20261023)
    for group in sorted({r['group'] for r in records}):
        selected = [r for r in bycase if r['group']==group]
        for method in METHODS:
            runs = [r for r in records if r['group']==group and r['method']==method]
            rows.append(dict(group=group,method=method,instances=len(selected),runs=len(runs),
                mean_hv=float(np.mean([r[method] for r in selected])),
                mean_runtime_seconds=float(np.mean([r['runtime_seconds'] for r in runs]))))
        for control in ('moead','explorer_solo'):
            differences = np.array([r['portfolio_20_80']-r[control] for r in selected])
            samples = rng.choice(differences,(20000,len(differences)),replace=True).mean(axis=1)
            comparisons.append(dict(group=group,candidate='portfolio_20_80',control=control,
                mean_difference=float(differences.mean()),bootstrap95_low=float(np.quantile(samples,.025)),
                bootstrap95_high=float(np.quantile(samples,.975)),
                wins=int(sum(differences>1e-12)),ties=int(sum(abs(differences)<=1e-12)),losses=int(sum(differences< -1e-12))))
    write_csv(output/'summary.csv',rows)
    write_csv(output/'comparisons.csv',comparisons)


METHODS = ['moead','explorer_solo','portfolio_20_80']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if output.exists() or not output.is_relative_to(ROOT/'results/experiments'):
        parser.error('Choose a new experiment directory')
    original = ROOT/'results/experiments/weighted_pilot_development_20261023/instances'
    bank = ROOT/'data/generated/f86_3'
    cases = [('fresh_seeds',p,[100,200,300,400,500]) for p in sorted(original.glob('*.dzn'))]
    cases += [('transfer',p,[100,200,300]) for folder in ('base','interactions') for p in sorted((bank/folder).glob('*.dzn'))]
    assert len(cases)==19 and len({digest(p) for _,p,_ in cases})==19
    files = sorted((ROOT/'src/mojssp').glob('*.py'))+sorted((ROOT/'scripts').glob('*.py'))
    hashes = {str(p.relative_to(ROOT)):digest(p) for p in files}
    output.mkdir(parents=True)
    for p in files:
        target = output/'code'/p.relative_to(ROOT)
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(p,target)
    for _,p,_ in cases:
        target = output/'instances'/p.name
        target.parent.mkdir(exist_ok=True)
        shutil.copy2(p,target)
    write_json(output/'config.json',dict(budget=3000,block_size=50,population_size=30,
        methods=METHODS,portfolio_quota={'MOEA/D':600,'RegionExplorer':2400},
        cases=[dict(group=g,name=p.stem,source=str(p.relative_to(ROOT)),sha256=digest(p),seeds=s) for g,p,s in cases],
        source_sha256=hashes,planned_runs=207,planned_search_fe=621000,
        scope='Frozen parameters; fresh seeds and instances new to regional experiments, not a project-wide untouched holdout',
        inference='Case-level paired differences, 20000 bootstrap resamples; synthetic related cases limit external generalization',
        runtime='Sequential wall times include logging and FE instrumentation; not a fixed-wall-time comparison'))
    evaluator = Evaluator.evaluate
    records, unique_checked = [],0
    for ci,(group,path,seeds) in enumerate(cases):
        instance = load_dzn(path)
        norm = ObjectiveNormalizer(compute_instance_bounds(instance))
        checked = set()
        for si,seed in enumerate(seeds):
            order = METHODS[(ci+si)%3:]+METHODS[:(ci+si)%3]
            results = {}
            for method in order:
                assert all(digest(ROOT/p)==sha for p,sha in hashes.items())
                calls = 0
                def counted(self,*a,**kw):
                    nonlocal calls
                    calls += 1
                    return evaluator(self,*a,**kw)
                with patch.object(Evaluator,'evaluate',counted):
                    if method=='moead':
                        r = run_regional(instance,seed,'moead')
                    elif method=='explorer_solo':
                        r = run_individual(instance,seed,'random')
                    else:
                        r = run_explorer_dominant(instance,seed)
                assert calls==r['evaluations_used']==3000
                hv = independent_hv([norm.normalize_tuple(p) for p in r['pareto_front']])
                assert abs(hv-r['hypervolume'])<1e-10
                assert len(r['checkpoints'])==60 and r['checkpoints'][-1][0]==3000
                for entry in r.get('front_entries',r.get('explorer_front',[])):
                    key = (tuple(entry['sequence']),tuple(entry['modes']))
                    if key in checked:
                        continue
                    solution = Solution(*key)
                    solution.validate_with_instance(instance)
                    schedule = Decoder().decode(instance,solution)
                    assert not validate_schedule(instance,schedule)
                    values = tuple(evaluator(Evaluator(),instance,schedule))
                    assert np.allclose(values,entry['objectives'],rtol=0,atol=1e-9)
                    checked.add(key)
                    unique_checked += 1
                if method=='portfolio_20_80':
                    assert r['allocations']=={'MOEA/D':600,'RegionExplorer':2400}
                r.update(group=group,case=path.stem,master_seed=seed,method=method,actual_evaluator_calls=calls,
                    independent_hypervolume=hv)
                write_json(output/'runs'/f'{path.stem}__{seed}__{method}.json',r)
                results[method] = r
                records.append({k:r[k] for k in ['group','case','master_seed','method','hypervolume','auc_hv','runtime_seconds','actual_evaluator_calls']})
                print(f"{len(records)}/207 {group} {path.stem} seed={seed} {method} HV={hv:.6f}",flush=True)
            assert results['portfolio_20_80']['moead_trace']==results['moead']['moead_trace'][:12]
    summarize(output,records)
    write_json(output/'validation.json',dict(runs=len(records),search_fe=sum(r['actual_evaluator_calls'] for r in records),
        independent_hv_all_passed=True,exact_fe_all_passed=True,moead_prefix_all_passed=True,
        unique_saved_genotypes_redecoded_and_validated=unique_checked,extra_validation_fe=unique_checked))
    write_json(output/'artifact_manifest.json',{str(p.relative_to(output)):digest(p)
        for p in sorted(output.rglob('*')) if p.is_file() and p.name!='artifact_manifest.json'})


if __name__=='__main__':
    main()
