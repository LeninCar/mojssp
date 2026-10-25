"""Matched live dynamic MOEA/D plus BLMR with optional one-way parent injection."""
import argparse,json,shutil
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
from unittest.mock import patch
from collections import defaultdict
import numpy as np
from run_weighted_pilot import ROOT,digest,write_json,write_csv,auc
from run_portfolio_campaign import analyze
from validate_regional_expansion import independent_hv
from mojssp.io import load_dzn
from mojssp.evaluator import Evaluator
from mojssp.normalization import ObjectiveNormalizer,compute_instance_bounds
from mojssp.regional_injection import run_blmr_injection

CONTROLS=['moead','nsga2_individual','spea2_individual','nsga2_ls_individual','mopso_individual','explorer_solo']

def execute(task):
    output,group,case,seed,active=task
    instance=load_dzn(output/'instances'/f'{case}.dzn')
    original=Evaluator.evaluate;calls=0
    def counted(self,*a,**kw):
        nonlocal calls
        calls+=1;return original(self,*a,**kw)
    with patch.object(Evaluator,'evaluate',counted):
        r=run_blmr_injection(instance,seed,active)
    assert calls==r['evaluations_used']==3000
    norm=ObjectiveNormalizer(compute_instance_bounds(instance))
    assert abs(independent_hv([norm.normalize_tuple(p) for p in r['pareto_front']])-r['hypervolume'])<1e-10
    r.update(group=group,case=case,master_seed=seed,method='active' if active else 'passive',
        actual_evaluator_calls=calls,auc_hv=auc(r['checkpoints'],3000),origin='new')
    if not active:
        old=json.loads((output/'reference'/group/f'{case}__{seed}__passive.json').read_text())
        for key in ['blocks','allocations','region_trace','pareto_front','checkpoints']:
            assert json.loads(json.dumps(r[key]))==old[key],(case,seed,key)
        assert r['migration_uses']==0
        r['reproduced_prior_trajectory']=True
    write_json(output/group/'runs'/f"{case}__{seed}__{r['method']}.json",r)
    return group,case,seed,r['method'],r['hypervolume'],r['migration_uses']

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',required=True,type=Path)
    parser.add_argument('--workers',type=int,choices=range(1,9),default=4)
    args=parser.parse_args();out=args.output_dir.resolve()
    if out.exists() or not out.is_relative_to(ROOT/'results/experiments'):parser.error('Choose a new experiment folder')
    prior=ROOT/'results/experiments/regional_compositions_two_banks_20261024'
    previous=json.loads((prior/'config.json').read_text())
    assert all(digest(ROOT/p)==sha for p,sha in previous['source_sha256'].items() if p.startswith('src/'))
    manifest={p.replace('\\','/'):sha for p,sha in json.loads((prior/'artifact_manifest.json').read_text()).items()}
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
        for si,seed in enumerate([100,200,300]):
            for method in CONTROLS+['passive']:
                oldmethod='moead_regional_dynamic' if method=='passive' else method
                source=prior/group/'runs'/f'{name}__{seed}__{oldmethod}.json'
                source_sha=digest(source)
                assert source_sha==manifest[str(source.relative_to(prior)).replace('\\','/')]
                r=json.loads(source.read_text())
                assert r['actual_evaluator_calls']==r['budget']==r['evaluations_used']==3000
                dest=out/'reference'/group/f'{name}__{seed}__{method}.json'
                dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
                references.append(dict(group=group,case=name,seed=seed,method=method,
                    path=str(source.relative_to(ROOT)).replace('\\','/'),sha256=source_sha))
                if method!='passive':
                    r.update(origin='reused_control',source_path=references[-1]['path'],source_file_sha256=source_sha)
                    write_json(out/group/'runs'/f'{name}__{seed}__{method}.json',r)
            for active in ([False,True] if (ci+si)%2==0 else [True,False]):
                tasks.append((out,group,name,seed,active))
    write_json(out/'config.json',dict(cases=previous['cases'],seeds=[100,200,300],budget=3000,
        population_size=30,block_size=50,policy='dynamic',policy_profile=dict(round_size=300,minimum_share=.1),
        arms=['MOEA/D','RegionExplorer'],controls=CONTROLS,methods=CONTROLS+['passive','active'],
        migration=dict(source='RegionExplorer',recipient='MOEA/D',m=5,every=10,
            selection='Deterministic max-min normalized distance from recipient archive and previously selected donors',
            eligibility='First observed in source archive; present in global archive; not observed in recipient archive or subproblems',
            meaning='First observed ownership is not complete genetic ancestry',
            scope='Replace second crossover parent only; all offspring decoded and evaluated natively within the same total FE'),
        expected_new_runs=114,expected_new_search_fe=342000,reused_individual_runs=342,
        passive_reproducibility_reference_runs=57,total_analysis_rows=456,
        source_sha256=hashes,reference_config_sha256=digest(prior/'config.json'),
        scope='Exploratory evaluation on previously observed development and additional banks; no untouched holdout',
        contrast='Active versus passive total intervention effect with live adaptive feedback; quotas may change as a consequence',
        timings='Concurrent execution and reused individual controls; not a fixed-wall-time experiment'))
    write_csv(out/'reused_inputs.csv',references)
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for i,f in enumerate(as_completed([pool.submit(execute,t) for t in tasks]),1):
            group,case,seed,method,hv,uses=f.result()
            print(f'{i}/114 {group} {case} {seed} {method} HV={hv:.6f} uses={uses}',flush=True)
    assert all(digest(ROOT/p)==sha for p,sha in hashes.items())
    for group in ['development','transfer']:
        records=[json.loads(p.read_text()) for p in (out/group/'runs').glob('*.json')]
        assert len(records)==(6 if group=='development' else 13)*3*8
        analyze(out/group,records,['active'],CONTROLS+['passive'])
        write_csv(out/group/'injection_runs.csv',[dict(case=r['case'],seed=r['master_seed'],method=r['method'],
            migration_uses=r['migration_uses'],moead_fe=r['allocations']['MOEA/D'],
            explorer_fe=r['allocations']['RegionExplorer'],hypervolume=r['hypervolume'])
            for r in records if r['method'] in ('active','passive')])
    write_json(out/'execution_validation.json',dict(new_runs=114,new_search_fe=342000,
        reused_individuals=342,passive_trajectories_exact=57,all_new_fe_exact=True,all_new_hv_independent=True))
    write_json(out/'artifact_manifest.json',{str(p.relative_to(out)):digest(p)
        for p in out.rglob('*') if p.is_file() and p.name!='artifact_manifest.json'})

if __name__=='__main__':main()

