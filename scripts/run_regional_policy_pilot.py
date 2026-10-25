"""Separate budget assignment and native region guidance under frozen profiles."""
import argparse
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor,as_completed
from dataclasses import asdict
import json
from pathlib import Path
import shutil
from unittest.mock import patch

import numpy as np
from run_weighted_pilot import ROOT,auc,digest,write_json,write_csv
from run_portfolio_campaign import analyze
from validate_regional_expansion import independent_hv
from mojssp.evaluator import Evaluator
from mojssp.io import load_dzn
from mojssp.normalization import ObjectiveNormalizer,compute_instance_bounds
from mojssp.regional_portfolio import POLICY_PROFILES,run_regional_policy_experiment
from mojssp.runner import run_standalone_experiment


def execute(task):
    output,case,seed,treatment = task
    instance=load_dzn(output/'instances'/f'{case}.dzn')
    original=Evaluator.evaluate
    calls=0
    def counted(self,*a,**kw):
        nonlocal calls
        calls+=1
        return original(self,*a,**kw)
    with patch.object(Evaluator,'evaluate',counted):
        if treatment['phase']=='individuals':
            name=treatment['arms'][0]
            offset={'NSGA-II':29,'SPEA2':43}[name]
            r=asdict(run_standalone_experiment(instance,name,(seed*10007+offset)%(2**31-1),3000,50,30))
        else:
            r=run_regional_policy_experiment(instance,seed,treatment['arms'],treatment['policy'],treatment['guidance'])
    assert calls==r['evaluations_used']==3000
    norm=ObjectiveNormalizer(compute_instance_bounds(instance))
    hv=independent_hv([norm.normalize_tuple(p) for p in r['pareto_front']])
    assert abs(hv-r['hypervolume'])<1e-10
    r.update(case=case,master_seed=seed,method=treatment['name'],phase=treatment['phase'],
        actual_evaluator_calls=calls,auc_hv=auc(r['checkpoints'],3000),independent_hypervolume=hv)
    write_json(output/treatment['phase']/'runs'/f"{case}__{seed}__{treatment['name']}.json",r)
    return case,seed,treatment['name'],hv


def design():
    treatments=[]
    for native,label in [('MOEA/D','moead'),('NSGA-II','nsga2'),('SPEA2','spea2')]:
        for policy in ['uniform','scaled','dynamic']:
            treatments.append(dict(name=f'{label}_regional_{policy}',phase='assignment',
                arms=[native,'RegionExplorer'],policy=policy,guidance=False))
    for guided in [False,True]:
        treatments.append(dict(name='nsga2_spea2_scaled_'+('regions' if guided else 'plain'),
            phase='native_regions',arms=['NSGA-II','SPEA2'],policy='scaled',guidance=guided))
    for name,label in [('NSGA-II','nsga2'),('SPEA2','spea2')]:
        treatments.append(dict(name=label+'_individual',phase='individuals',arms=[name]))
    return treatments


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--workers',type=int,default=4)
    args=parser.parse_args()
    output=args.output_dir.resolve()
    if output.exists() or not output.is_relative_to(ROOT/'results/experiments'):
        parser.error('Choose a new experiment directory')
    if not 1<=args.workers<=8:
        parser.error('Use one to eight workers')
    source=ROOT/'results/experiments/regional_validation_expanded_20261023'
    previous=json.loads((source/'config.json').read_text())
    assert all(digest(ROOT/name)==sha for name,sha in previous['source_sha256'].items())
    cases=[c for c in previous['cases'] if c['group']=='fresh_seeds']
    seeds=[100,200,300]
    treatments=design()
    output.mkdir(parents=True)
    files=sorted((ROOT/'src/mojssp').glob('*.py'))+sorted((ROOT/'scripts').glob('*.py'))
    hashes={str(p.relative_to(ROOT)):digest(p) for p in files}
    for p in files:
        target=output/'code'/p.relative_to(ROOT)
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(p,target)
    references=[]
    reference_hashes={}
    for case in cases:
        p=source/'instances'/f"{case['name']}.dzn"
        assert digest(p)==case['sha256']
        target=output/'instances'/p.name
        target.parent.mkdir(exist_ok=True)
        shutil.copy2(p,target)
        for seed in seeds:
            for method in ['moead','explorer_solo','portfolio_20_80']:
                p=source/'runs'/f"{case['name']}__{seed}__{method}.json"
                r=json.loads(p.read_text())
                assert r['actual_evaluator_calls']==3000
                references.append(r)
                target=output/'reference'/p.name
                target.parent.mkdir(exist_ok=True)
                shutil.copy2(p,target)
                reference_hashes[str(p.relative_to(ROOT))]=digest(p)
    expected=len(cases)*len(seeds)*len(treatments)
    write_json(output/'config.json',dict(cases=cases,seeds=seeds,treatments=treatments,
        budget=3000,block_size=50,population_size=30,policy_profiles=POLICY_PROFILES,
        pilot_policies=['uniform','scaled','dynamic'],integration_policies=list(POLICY_PROFILES),
        expected_new_runs=expected,expected_new_search_fe=expected*3000,reused_reference_runs=len(references),
        source_sha256=hashes,reference_sha256=reference_hashes,
        guidance='One uniformly random region per native block; up to five evaluated global parents, second parent replaced every tenth crossover; no native operators changed',
        explorer='Previously validated random-region arm unchanged; parent context refreshed immediately before each selected block',
        reward='Marginal global HV gain credited to executing arm, not an estimate of independent causal contribution',
        initialization='One full block per arm, included in FE but excluded from policy learning; first round uniform for dynamic',
        scope='Exploratory development comparison; six previously studied cases, three seeds; multiple comparisons, no confirmatory claims',
        timing='Concurrent process wall times are descriptive and not a fixed-time comparison',workers=args.workers))
    tasks=[(output,c['name'],s,t) for c in cases for s in seeds for t in treatments]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for count,future in enumerate(as_completed([pool.submit(execute,t) for t in tasks]),1):
            case,seed,method,hv=future.result()
            print(f'{count}/{expected} {case} seed={seed} {method} HV={hv:.6f}',flush=True)
    assert all(digest(ROOT/name)==sha for name,sha in hashes.items())
    records=[]
    for phase in ['individuals','assignment','native_regions']:
        records.extend(json.loads(p.read_text()) for p in (output/phase/'runs').glob('*.json'))
    assert len(records)==expected
    controls=references+[r for r in records if r['phase']=='individuals']
    control_names=['moead','explorer_solo','portfolio_20_80','nsga2_individual','spea2_individual']
    for phase in ['assignment','native_regions']:
        candidates=[t['name'] for t in treatments if t['phase']==phase]
        analyze(output/phase,controls+[r for r in records if r['phase']==phase],candidates,control_names)
    write_csv(output/'individuals/runs.csv',[{k:r[k] for k in ['case','master_seed','method','hypervolume','auc_hv','runtime_seconds']} for r in controls])
    allocations=[]
    for r in records:
        for arm,fe in (r.get('allocations') or {}).items():
            allocations.append(dict(phase=r['phase'],case=r['case'],master_seed=r['master_seed'],
                method=r['method'],arm=arm,evaluations=fe,percentage=100*fe/3000))
    write_csv(output/'allocations.csv',allocations)
    by=defaultdict(list)
    for row in allocations: by[row['method'],row['arm']].append(row['percentage'])
    write_csv(output/'allocation_summary.csv',[dict(method=m,arm=a,mean_percentage=float(np.mean(v)),
        minimum_percentage=min(v),maximum_percentage=max(v)) for (m,a),v in sorted(by.items())])
    cells=defaultdict(list)
    for r in controls+[r for r in records if r['phase']!='individuals']:
        cells[r['case'],r['method']].append(r['hypervolume'])
    native=[r for r in records if r['phase']=='native_regions']
    differences=[]
    for case in cases:
        c=case['name']
        delta=np.mean(cells[c,'nsga2_spea2_scaled_regions'])-np.mean(cells[c,'nsga2_spea2_scaled_plain'])
        differences.append(dict(case=c,regions_minus_plain=float(delta)))
    write_csv(output/'native_regions/regions_minus_plain.csv',differences)
    write_json(output/'validation.json',dict(new_runs=len(records),new_search_fe=len(records)*3000,
        all_actual_fe_exact=True,all_hv_independently_recomputed=True,
        guidance_events=sum(len(r.get('guidance_events',[])) for r in native),
        source_hashes_unchanged=True))
    write_json(output/'artifact_manifest.json',{str(p.relative_to(output)):digest(p)
        for p in sorted(output.rglob('*')) if p.is_file() and p.name!='artifact_manifest.json'})


if __name__=='__main__': main()
