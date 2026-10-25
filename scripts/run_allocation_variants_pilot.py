"""MOEA/D plus BLMR with sharpened or front-loaded dynamic budget allocation."""
import argparse,json,shutil
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
from unittest.mock import patch
import numpy as np
from run_weighted_pilot import ROOT,digest,write_json,write_csv,auc
from run_portfolio_campaign import analyze
from validate_regional_expansion import independent_hv
from mojssp.io import load_dzn
from mojssp.evaluator import Evaluator
from mojssp.normalization import ObjectiveNormalizer,compute_instance_bounds
from mojssp.regional_portfolio import run_regional_policy_experiment

REFERENCE='results/experiments/blmr_to_moead_dynamic_injection_20261024'
CONTROLS=['moead','nsga2_individual','spea2_individual','nsga2_ls_individual','mopso_individual','explorer_solo','passive']
VARIANTS={
    'passive_repro':{},
    'greedy_p3':dict(share_power=3.),
    'early_moead_600':dict(exclusive_arm='RegionExplorer',exclusive_after=600),
}
CANDIDATES=['greedy_p3','early_moead_600']
RULE=('A variant is adopted only if its mean HV exceeds explorer_solo and the current dynamic pair (passive) '
      'on both the development and the additional bank; instance means first, then equal instance weights.')

def execute(task):
    output,group,case,seed,method=task
    instance=load_dzn(output/'instances'/f'{case}.dzn')
    original=Evaluator.evaluate;calls=0
    def counted(self,*a,**kw):
        nonlocal calls
        calls+=1;return original(self,*a,**kw)
    with patch.object(Evaluator,'evaluate',counted):
        r=run_regional_policy_experiment(instance,seed,['MOEA/D','RegionExplorer'],'dynamic',False,
                                         dynamic_options=VARIANTS[method] or None)
    assert calls==r['evaluations_used']==3000
    norm=ObjectiveNormalizer(compute_instance_bounds(instance))
    assert abs(independent_hv([norm.normalize_tuple(p) for p in r['pareto_front']])-r['hypervolume'])<1e-10
    r.update(group=group,case=case,master_seed=seed,method=method,actual_evaluator_calls=calls,
             auc_hv=auc(r['checkpoints'],3000),origin='new')
    if method=='passive_repro':
        old=json.loads((output/'reference'/group/f'{case}__{seed}__passive.json').read_text())
        same=all(json.loads(json.dumps(r[k]))==old[k] for k in ['blocks','allocations','pareto_front','checkpoints'])
        assert same,(case,seed)
        return group,case,seed,method,r['hypervolume'],r['allocations']
    write_json(output/group/'runs'/f'{case}__{seed}__{method}.json',r)
    return group,case,seed,method,r['hypervolume'],r['allocations']

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',required=True,type=Path)
    parser.add_argument('--workers',type=int,choices=range(1,13),default=6)
    args=parser.parse_args();out=args.output_dir.resolve()
    if out.exists() or not out.is_relative_to(ROOT/'results/experiments'):parser.error('Choose a new experiment folder')
    prior=ROOT/REFERENCE
    previous=json.loads((prior/'config.json').read_text())
    out.mkdir(parents=True)
    files=sorted((ROOT/'src/mojssp').glob('*.py'))+sorted((ROOT/'scripts').glob('*.py'))
    hashes={str(p.relative_to(ROOT)).replace('\\','/'):digest(p) for p in files}
    for p in files:
        dest=out/'code'/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
    tasks=[];references=[]
    for case in previous['cases']:
        name,group=case['name'],case['group']
        source=prior/'instances'/f'{name}.dzn';assert digest(source)==case['sha256']
        dest=out/'instances'/source.name;dest.parent.mkdir(exist_ok=True);shutil.copy2(source,dest)
        for seed in [100,200,300]:
            for method in CONTROLS:
                source=prior/'reference'/group/f'{name}__{seed}__{method}.json'
                r=json.loads(source.read_text())
                assert r['actual_evaluator_calls']==r['budget']==r['evaluations_used']==3000
                dest=out/'reference'/group/source.name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
                references.append(dict(group=group,case=name,seed=seed,method=method,
                    path=str(source.relative_to(ROOT)).replace('\\','/'),sha256=digest(source)))
                r.update(method=method,origin='reused_control',source_path=references[-1]['path'])
                write_json(out/group/'runs'/f'{name}__{seed}__{method}.json',r)
            for method in VARIANTS:
                tasks.append((out,group,name,seed,method))
    write_json(out/'config.json',dict(cases=previous['cases'],seeds=[100,200,300],budget=3000,
        population_size=30,block_size=50,policy='dynamic',arms=['MOEA/D','RegionExplorer'],
        base_profile=dict(round_size=300,minimum_share=.1),variants=VARIANTS,candidates=CANDIDATES,
        controls=CONTROLS,decision_rule=RULE,fixed_before_running=True,
        rationale=('Offline diagnosis: the pair beats BLMR given the same FE on every instance, but proportional '
                   'shares give MOEA/D about 30% while its later gain per FE is about a third of BLMR. '
                   'Power 3 and the 600 FE switch were fixed before running; no other values are tried.'),
        source_sha256=hashes,reference=REFERENCE,
        scope='Exploratory: both banks were observed before; the untouched holdout is reserved for a frozen winner',
        timings='Concurrent execution and reused controls; not a fixed-wall-time comparison'))
    write_csv(out/'reused_inputs.csv',references)
    allocations=[]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for i,f in enumerate(as_completed([pool.submit(execute,t) for t in tasks]),1):
            group,case,seed,method,hv,alloc=f.result()
            allocations.append(dict(group=group,case=case,seed=seed,method=method,hypervolume=hv,
                moead_fe=alloc.get('MOEA/D',0),explorer_fe=alloc.get('RegionExplorer',0)))
            print(f'{i}/{len(tasks)} {group} {case} {seed} {method} HV={hv:.6f} MOEA/D={alloc.get("MOEA/D",0)}',flush=True)
    assert all(digest(ROOT/p)==sha for p,sha in hashes.items())
    write_csv(out/'allocations.csv',sorted(allocations,key=lambda r:(r['group'],r['case'],r['seed'],r['method'])))
    means={}
    for group in ['development','transfer']:
        records=[json.loads(p.read_text()) for p in (out/group/'runs').glob('*.json')]
        assert len(records)==(6 if group=='development' else 13)*3*(len(CONTROLS)+len(CANDIDATES))
        analyze(out/group,records,CANDIDATES,CONTROLS)
        cases=sorted({r['case'] for r in records})
        means[group]={m:float(np.mean([np.mean([r['hypervolume'] for r in records if r['case']==c and r['method']==m])
                       for c in cases])) for m in CONTROLS+CANDIDATES}
    gates={c:all(means[g][c]>means[g]['explorer_solo'] and means[g][c]>means[g]['passive'] for g in means)
           for c in CANDIDATES}
    beats_all={c:{g:all(means[g][c]>means[g][m] for m in CONTROLS) for g in means} for c in CANDIDATES}
    write_json(out/'decision.json',dict(means=means,decision_rule=RULE,adoption_gates=gates,
        adopt_any=any(gates.values()),beats_every_control=beats_all,
        passive_trajectories_reproduced=sum(1 for t in tasks if t[4]=='passive_repro')))
    write_json(out/'artifact_manifest.json',{str(p.relative_to(out)).replace('\\','/'):digest(p)
        for p in out.rglob('*') if p.is_file() and p.name!='artifact_manifest.json'})

if __name__=='__main__':main()
