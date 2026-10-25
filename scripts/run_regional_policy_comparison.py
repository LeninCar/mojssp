"""Compare five SPEA2 regional policies with matched individual controls."""
import argparse
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor,as_completed
import json
from pathlib import Path
import shutil
import time
from unittest.mock import patch

import numpy as np
from run_weighted_pilot import ROOT,auc,digest,write_csv,write_json
from run_portfolio_campaign import analyze
from run_regional_explorer_controls import run_individual
from validate_regional_expansion import independent_hv
from mojssp.arms import MOPSOArm
from mojssp.spea2 import SPEA2Arm
from mojssp.evaluator import Evaluator
from mojssp.io import load_dzn
from mojssp.normalization import ObjectiveNormalizer,compute_instance_bounds
from mojssp.hypervolume import compute_archive_hypervolume
from mojssp.regional_portfolio import POLICY_PROFILES,run_regional_policy_experiment

POLICIES=('uniform','sw_ucb','scaled','ph','dynamic')
CONTROLS=('spea2_individual','explorer_solo','mopso_individual')

def native_individual(instance,seed,name,budget=3000):
    cls,offset=(SPEA2Arm,43) if name=='spea2_individual' else (MOPSOArm,97)
    arm=cls(instance,population_size=30,seed=(seed*10007+offset)%(2**31-1),max_evaluations=budget)
    norm=ObjectiveNormalizer(compute_instance_bounds(instance))
    checkpoints=[]
    start=time.perf_counter()
    while arm.total_evaluations<budget:
        result=arm.run(min(50,budget-arm.total_evaluations))
        assert result.evaluations_used>0
        checkpoints.append([arm.total_evaluations,compute_archive_hypervolume(result.solutions,norm)])
    entries=list(result.solutions.entries)
    return dict(budget=budget,evaluations_used=arm.total_evaluations,
        checkpoints=checkpoints,hypervolume=checkpoints[-1][1],runtime_seconds=time.perf_counter()-start,
        front_entries=[dict(sequence=list(e.solution.sequence),modes=list(e.solution.modes),objectives=list(e.objectives)) for e in entries],
        pareto_front=[list(e.objectives) for e in entries],completed=True)

def execute(task):
    output,case,seed,method=task
    instance=load_dzn(output/'instances'/f'{case}.dzn')
    original=Evaluator.evaluate
    calls=0
    def counted(self,*a,**kw):
        nonlocal calls
        calls+=1
        return original(self,*a,**kw)
    with patch.object(Evaluator,'evaluate',counted):
        if method=='explorer_solo':
            r=run_individual(instance,seed,'random')
        elif method in CONTROLS:
            r=native_individual(instance,seed,method)
        else:
            r=run_regional_policy_experiment(instance,seed,['SPEA2','RegionExplorer'],method.removeprefix('spea2_regional_'))
    assert calls==r['evaluations_used']==3000
    norm=ObjectiveNormalizer(compute_instance_bounds(instance))
    hv=independent_hv([norm.normalize_tuple(p) for p in r['pareto_front']])
    assert abs(hv-r['hypervolume'])<1e-10
    r.update(case=case,master_seed=seed,method=method,actual_evaluator_calls=calls,
             auc_hv=auc(r['checkpoints'],3000),independent_hypervolume=hv)
    write_json(output/'runs'/f'{case}__{seed}__{method}.json',r)
    return case,seed,method,hv

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--workers',type=int,default=4,choices=range(1,9))
    args=parser.parse_args()
    output=args.output_dir.resolve()
    if output.exists() or not output.is_relative_to(ROOT/'results/experiments'):
        parser.error('Choose a new directory in results/experiments')
    prior=ROOT/'results/experiments/regional_policy_integration_development_20261023'
    config=json.loads((prior/'config.json').read_text())
    cases=config['cases'];seeds=[100,200,300]
    candidates=['spea2_regional_'+p for p in POLICIES]
    methods=list(CONTROLS)+candidates
    output.mkdir(parents=True)
    for case in cases:
        src=prior/'instances'/f"{case['name']}.dzn"
        assert digest(src)==case['sha256']
        (output/'instances').mkdir(exist_ok=True)
        shutil.copy2(src,output/'instances'/src.name)
    files=sorted((ROOT/'src/mojssp').glob('*.py'))+sorted((ROOT/'scripts').glob('*.py'))
    hashes={str(p.relative_to(ROOT)).replace('\\','/'):digest(p) for p in files}
    for path in files:
        dest=output/'code'/path.relative_to(ROOT)
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,dest)
    write_json(output/'config.json',dict(cases=cases,seeds=seeds,methods=methods,budget=3000,
        block_size=50,population_size=30,policy_profiles=POLICY_PROFILES,guidance=False,
        expected_runs=144,expected_search_fe=432000,source_sha256=hashes,
        seed_offsets=dict(SPEA2=43,BLMR_operator=71,BLMR_initialization=83,MOPSO=97),
        scope='Exploratory development; five policies on the same six cases; no untouched confirmation',
        timing='Concurrent wall times descriptive only; not a fixed-time comparison',
        mopso='Mandatory individual control; native discrete MOPSO unchanged; swarm size 30',
        reuse='All 144 runs newly executed; prior controls used only for reproducibility checks'))
    tasks=[]
    for ci,c in enumerate(cases):
        for si,seed in enumerate(seeds):
            shift=(ci*len(seeds)+si)%len(methods)
            tasks.extend((output,c['name'],seed,m) for m in methods[shift:]+methods[:shift])
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for i,f in enumerate(as_completed([pool.submit(execute,t) for t in tasks]),1):
            case,seed,method,hv=f.result()
            print(f'{i}/144 {case} {seed} {method} HV={hv:.6f}',flush=True)
    assert all(digest(ROOT/p)==sha for p,sha in hashes.items())
    records=[json.loads(p.read_text()) for p in sorted((output/'runs').glob('*.json'))]
    assert len(records)==144
    analyze(output,records,candidates,list(CONTROLS))
    cells=defaultdict(list)
    for r in records: cells[r['case'],r['method']].append(r['hypervolume'])
    write_csv(output/'winners.csv',[dict(case=c['name'],
        winner=max(methods,key=lambda m:np.mean(cells[c['name'],m])),
        best_individual=max(CONTROLS,key=lambda m:np.mean(cells[c['name'],m]))) for c in cases])
    allocations=[dict(case=r['case'],master_seed=r['master_seed'],method=r['method'],arm=a,
                      evaluations=fe,percentage=100*fe/3000)
                 for r in records for a,fe in r.get('allocations',{}).items()]
    write_csv(output/'allocations.csv',allocations)
    by=defaultdict(list)
    for r in allocations: by[r['method'],r['arm']].append(r['percentage'])
    write_csv(output/'allocation_summary.csv',[dict(method=m,arm=a,mean_percentage=float(np.mean(v)),
        minimum_percentage=min(v),maximum_percentage=max(v)) for (m,a),v in sorted(by.items())])
    reproductions=[]
    for r in records:
        if r['method'] in ['spea2_regional_uniform','spea2_regional_scaled','spea2_regional_dynamic']:
            p=prior/'assignment/runs'/f"{r['case']}__{r['master_seed']}__{r['method']}.json"
        elif r['method']=='spea2_individual':
            p=prior/'individuals/runs'/f"{r['case']}__{r['master_seed']}__{r['method']}.json"
        else: continue
        old=json.loads(p.read_text())
        assert r['pareto_front']==old['pareto_front']
        assert r['checkpoints']==old['checkpoints']
        if 'blocks' in r: assert r['blocks']==old['blocks']
        reproductions.append(dict(case=r['case'],seed=r['master_seed'],method=r['method'],
                                   prior_path=str(p.relative_to(ROOT)),prior_sha256=digest(p),exact=True))
    write_csv(output/'reproductions.csv',reproductions)
    write_json(output/'execution_validation.json',dict(runs=144,search_fe=432000,
        all_actual_fe_exact=True,all_final_hv_independent=True,prior_trajectories_reproduced=len(reproductions)))
    write_json(output/'artifact_manifest.json',{str(p.relative_to(output)):digest(p)
        for p in sorted(output.rglob('*')) if p.is_file() and p.name!='artifact_manifest.json'})

if __name__=='__main__': main()

