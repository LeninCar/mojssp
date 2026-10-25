"""MultiEA-style winner-take-all selection for MOEA/D plus BLMR with five seeds on both banks."""
import argparse,json,shutil
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
from unittest.mock import patch
import numpy as np
from run_weighted_pilot import ROOT,digest,write_json,write_csv,auc
from run_portfolio_campaign import analyze
from run_regional_explorer_controls import run_individual
from run_regional_composition_comparison import native_individual
from validate_regional_expansion import independent_hv
from mojssp.io import load_dzn
from mojssp.evaluator import Evaluator
from mojssp.normalization import ObjectiveNormalizer,compute_instance_bounds
from mojssp.regional_portfolio import run_regional_policy_experiment

REFERENCE='results/experiments/blmr_to_moead_dynamic_injection_20261024'
ALLOCATION='results/experiments/allocation_variants_moead_blmr_20261024'
SEEDS=[100,200,300,400,500]
NEW_SEEDS=[400,500]
INDIVIDUALS=['moead','nsga2_individual','spea2_individual','nsga2_ls_individual','mopso_individual','explorer_solo']
CONTROLS=INDIVIDUALS+['passive','early_moead_600']
CANDIDATES=['multiea_own','multiea_credit']
PAIRS={
    'passive':('dynamic',None),
    'early_moead_600':('dynamic',dict(exclusive_arm='RegionExplorer',exclusive_after=600)),
    'multiea_own':('multiea',None),
    'multiea_credit':('multiea_credit',None),
}
RULE=('A MultiEA variant is adopted only if its five-seed mean HV exceeds explorer_solo and passive on both banks. '
      'Among gate-passing methods including early_moead_600, the holdout candidate is the one with the largest '
      'minimum advantage over explorer_solo across the two banks.')

def run_method(instance,seed,method):
    if method=='explorer_solo':return run_individual(instance,seed,'random')
    if method in INDIVIDUALS:return native_individual(instance,seed,method)
    policy,options=PAIRS[method]
    return run_regional_policy_experiment(instance,seed,['MOEA/D','RegionExplorer'],policy,False,dynamic_options=options)

def execute(task):
    output,group,case,seed,method,expected=task
    instance=load_dzn(output/'instances'/f'{case}.dzn')
    original=Evaluator.evaluate;calls=0
    def counted(self,*a,**kw):
        nonlocal calls
        calls+=1;return original(self,*a,**kw)
    with patch.object(Evaluator,'evaluate',counted):
        r=run_method(instance,seed,method)
    assert calls==r['evaluations_used']==3000
    norm=ObjectiveNormalizer(compute_instance_bounds(instance))
    assert abs(independent_hv([norm.normalize_tuple(p) for p in r['pareto_front']])-r['hypervolume'])<1e-10
    if expected is not None:
        assert abs(r['hypervolume']-expected)<1e-12,(case,seed,method,r['hypervolume'],expected)
        return group,case,seed,method,r['hypervolume'],'reproduced'
    r.update(group=group,case=case,master_seed=seed,method=method,actual_evaluator_calls=calls,
             auc_hv=auc(r['checkpoints'],3000),origin='new')
    write_json(output/group/'runs'/f'{case}__{seed}__{method}.json',r)
    return group,case,seed,method,r['hypervolume'],r.get('allocations',{})

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',required=True,type=Path)
    parser.add_argument('--workers',type=int,choices=range(1,15),default=12)
    args=parser.parse_args();out=args.output_dir.resolve()
    if out.exists() or not out.is_relative_to(ROOT/'results/experiments'):parser.error('Choose a new experiment folder')
    prior,alloc=ROOT/REFERENCE,ROOT/ALLOCATION
    previous=json.loads((prior/'config.json').read_text())
    out.mkdir(parents=True)
    files=sorted((ROOT/'src/mojssp').glob('*.py'))+sorted((ROOT/'scripts').glob('*.py'))
    hashes={str(p.relative_to(ROOT)).replace('\\','/'):digest(p) for p in files}
    for p in files:
        dest=out/'code'/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
    tasks=[];references=[]
    for ci,case in enumerate(previous['cases']):
        name,group=case['name'],case['group']
        source=prior/'instances'/f'{name}.dzn';assert digest(source)==case['sha256']
        dest=out/'instances'/source.name;dest.parent.mkdir(exist_ok=True);shutil.copy2(source,dest)
        for seed in SEEDS:
            for method in CONTROLS+CANDIDATES:
                if seed in NEW_SEEDS or method in CANDIDATES:
                    tasks.append((out,group,name,seed,method,None));continue
                base=alloc if method=='early_moead_600' else prior/'reference'
                source=(base/group/'runs' if method=='early_moead_600' else base/group)/f'{name}__{seed}__{method}.json'
                r=json.loads(source.read_text())
                assert r['budget']==r['evaluations_used']==3000
                references.append(dict(group=group,case=name,seed=seed,method=method,
                    path=str(source.relative_to(ROOT)).replace('\\','/'),sha256=digest(source)))
                r.update(method=method,master_seed=seed,case=name,group=group,origin='reused_control',
                         source_path=references[-1]['path'])
                write_json(out/group/'runs'/f'{name}__{seed}__{method}.json',r)
                if ci==0 and seed==100 and method in INDIVIDUALS:
                    tasks.append((out,group,name,seed,method,r['hypervolume']))
    write_json(out/'config.json',dict(cases=previous['cases'],seeds=SEEDS,new_seeds=NEW_SEEDS,budget=3000,
        population_size=30,block_size=50,arms=['MOEA/D','RegionExplorer'],pairs=PAIRS,controls=CONTROLS,
        candidates=CANDIDATES,decision_rule=RULE,fixed_before_running=True,
        design=dict(predictor='Least-squares lines on the last l=2..k curve points, floored at the latest value, '
                              'one prediction sampled with equal weight (MultiEA, Yuen et al. GECCO 2013)',
                    target='Nearest common future point max(arm FE + 50)',
                    selection='Winner takes the next 50 FE block',
                    initialization='Two blocks per arm, continued until the curve changes, at most six blocks',
                    curves=dict(multiea_own='HV of the arm own archive vs its FE',
                                multiea_credit='Cumulative global HV gain credited to the arm vs its FE; first block earns nothing')),
        development_note=('Curve choice and change-based initialization were added after smoke runs on three '
                          'instances showed lock-in; no pilot results were seen before fixing the design.'),
        source_sha256=hashes,reference=REFERENCE,allocation_reference=ALLOCATION,
        scope='Exploratory: both banks were observed before; the untouched holdout is reserved',
        timings='Concurrent execution and reused controls; not a fixed-wall-time comparison'))
    write_csv(out/'reused_inputs.csv',references)
    allocations=[];reproduced=0
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for i,f in enumerate(as_completed([pool.submit(execute,t) for t in tasks]),1):
            group,case,seed,method,hv,alloc_=f.result()
            if alloc_=='reproduced':reproduced+=1
            elif alloc_:
                allocations.append(dict(group=group,case=case,seed=seed,method=method,hypervolume=hv,
                    moead_fe=alloc_.get('MOEA/D',0),explorer_fe=alloc_.get('RegionExplorer',0)))
            print(f'{i}/{len(tasks)} {group} {case} {seed} {method} HV={hv:.6f}',flush=True)
    assert all(digest(ROOT/p)==sha for p,sha in hashes.items())
    write_csv(out/'allocations.csv',sorted(allocations,key=lambda r:(r['group'],r['case'],r['seed'],r['method'])))
    means={}
    for group in ['development','transfer']:
        records=[json.loads(p.read_text()) for p in (out/group/'runs').glob('*.json')]
        assert len(records)==(6 if group=='development' else 13)*len(SEEDS)*(len(CONTROLS)+len(CANDIDATES))
        analyze(out/group,records,CANDIDATES+['early_moead_600'],INDIVIDUALS+['passive'])
        cases=sorted({r['case'] for r in records})
        means[group]={m:float(np.mean([np.mean([r['hypervolume'] for r in records if r['case']==c and r['method']==m])
                       for c in cases])) for m in CONTROLS+CANDIDATES}
    passes=lambda m:all(means[g][m]>means[g]['explorer_solo'] and means[g][m]>means[g]['passive'] for g in means)
    gates={m:passes(m) for m in CANDIDATES+['early_moead_600']}
    margin={m:min(means[g][m]-means[g]['explorer_solo'] for g in means) for m in gates}
    eligible=[m for m in gates if gates[m]]
    write_json(out/'decision.json',dict(means=means,decision_rule=RULE,adoption_gates=gates,
        minimum_margin_over_explorer=margin,holdout_candidate=max(eligible,key=margin.get) if eligible else None,
        individual_controls_reproduced=reproduced))
    write_json(out/'artifact_manifest.json',{str(p.relative_to(out)).replace('\\','/'):digest(p)
        for p in out.rglob('*') if p.is_file() and p.name!='artifact_manifest.json'})

if __name__=='__main__':main()
