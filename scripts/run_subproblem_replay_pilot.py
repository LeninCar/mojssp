"""Replay passive dynamic schedules to isolate compatible injection at equal allocation."""
import argparse,json,shutil
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
from unittest.mock import patch
from run_weighted_pilot import ROOT,digest,write_json,write_csv,auc
from run_portfolio_campaign import analyze
from validate_regional_expansion import independent_hv
from mojssp.io import load_dzn
from mojssp.evaluator import Evaluator
from mojssp.normalization import ObjectiveNormalizer,compute_instance_bounds
from mojssp.subproblem_replay import run_subproblem_replay

CONTROLS=['moead','nsga2_individual','spea2_individual','nsga2_ls_individual','mopso_individual',
          'explorer_solo','passive','maxmin','compatible_live']

def execute(task):
    out,case,seed,active=task
    source=json.loads((out/'reference'/f'{case}__{seed}__passive.json').read_text())
    instance=load_dzn(out/'instances'/f'{case}.dzn')
    original=Evaluator.evaluate;calls=0
    def counted(self,*a,**kw):
        nonlocal calls
        calls+=1;return original(self,*a,**kw)
    with patch.object(Evaluator,'evaluate',counted):
        r=run_subproblem_replay(instance,seed,source['blocks'],active)
    assert calls==r['evaluations_used']==3000
    def allocation(rows):return [(b['arm_name'],b['evaluations_used'],b['fe_before'],b['fe_after']) for b in rows]
    assert allocation(r['blocks'])==allocation(source['blocks'])
    assert r['allocations']==source['allocations']
    if not active:
        for key in ['blocks','region_trace','pareto_front','checkpoints']:
            assert json.loads(json.dumps(r[key]))==source[key],(case,seed,key)
    norm=ObjectiveNormalizer(compute_instance_bounds(instance))
    assert abs(independent_hv([norm.normalize_tuple(p) for p in r['pareto_front']])-r['hypervolume'])<1e-10
    r.update(case=case,master_seed=seed,method='compatible_replay' if active else 'passive',
        origin='new',actual_evaluator_calls=calls,auc_hv=auc(r['checkpoints'],3000),
        trace_input_sha256=digest(out/'reference'/f'{case}__{seed}__passive.json'))
    write_json(out/'runs'/f"{case}__{seed}__{r['method']}.json",r)
    return case,seed,r['method'],r['hypervolume'],r['migration_uses']

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',required=True,type=Path)
    parser.add_argument('--workers',type=int,choices=range(1,9),default=4)
    args=parser.parse_args();out=args.output_dir.resolve()
    if out.exists() or not out.is_relative_to(ROOT/'results/experiments'):parser.error('Choose a new output folder')
    prior=ROOT/'results/experiments/subproblem_compatible_injection_development_20261024'
    previous=json.loads((prior/'config.json').read_text())
    assert all(digest(ROOT/p)==sha for p,sha in previous['source_sha256'].items() if p.startswith('src/'))
    manifest={p.replace('\\','/'):sha for p,sha in json.loads((prior/'artifact_manifest.json').read_text()).items()}
    out.mkdir(parents=True);files=sorted((ROOT/'src/mojssp').glob('*.py'))+sorted((ROOT/'scripts').glob('*.py'))
    hashes={str(p.relative_to(ROOT)).replace('\\','/'):digest(p) for p in files}
    for p in files:
        dest=out/'code'/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
    tasks=[];references=[]
    for ci,case in enumerate(previous['cases']):
        name=case['name'];source=prior/'instances'/f'{name}.dzn'
        assert digest(source)==case['sha256']
        dest=out/'instances'/source.name;dest.parent.mkdir(exist_ok=True);shutil.copy2(source,dest)
        for si,seed in enumerate(previous['seeds']):
            for method in CONTROLS:
                oldmethod='compatible' if method=='compatible_live' else method
                p=prior/'runs'/f'{name}__{seed}__{oldmethod}.json'
                sha=digest(p);assert sha==manifest[str(p.relative_to(prior)).replace('\\','/')]
                r=json.loads(p.read_text());assert r['actual_evaluator_calls']==3000
                dest=out/'reference'/f'{name}__{seed}__{method}.json'
                dest.parent.mkdir(exist_ok=True);shutil.copy2(p,dest)
                references.append(dict(case=name,seed=seed,method=method,path=str(p.relative_to(ROOT)).replace('\\','/'),sha256=sha))
                if method!='passive':
                    r.update(method=method,origin='reused',source_path=references[-1]['path'],source_file_sha256=sha)
                    write_json(out/'runs'/f'{name}__{seed}__{method}.json',r)
            for active in ([False,True] if (ci+si)%2==0 else [True,False]):tasks.append((out,name,seed,active))
    write_json(out/'config.json',dict(cases=previous['cases'],seeds=previous['seeds'],
        controls=CONTROLS,methods=CONTROLS+['compatible_replay'],budget=3000,population_size=30,
        expected_new_runs=36,expected_new_search_fe=108000,reused_analysis_runs=144,
        trace_inputs=18,total_analysis_records=180,source_sha256=hashes,
        primary_comparisons=['compatible_replay minus passive','compatible_replay minus compatible_live'],
        secondary='BLMR and all five native individuals retained',
        intervention='Same compatible donor selector; same block order, sizes, initialization and native arm seeds as passive control',
        interpretation='Conditional effect of injection at fixed realized allocation; future BLMR parents may still change',
        deployment_cost='Passive trace requires 3000 FE on this case and seed; trace plus replay costs 6000 FE from scratch',
        scope='Diagnostic only, not a new autonomous policy or untouched confirmation',
        timings='Concurrent timings descriptive only'))
    write_csv(out/'reused_inputs.csv',references)
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for i,f in enumerate(as_completed([pool.submit(execute,t) for t in tasks]),1):
            case,seed,method,hv,uses=f.result()
            print(f'{i}/36 {case} {seed} {method} HV={hv:.6f} uses={uses}',flush=True)
    assert all(digest(ROOT/p)==sha for p,sha in hashes.items())
    records=[json.loads(p.read_text()) for p in (out/'runs').glob('*.json')]
    assert len(records)==180
    analyze(out,records,['compatible_replay'],CONTROLS)
    write_json(out/'execution_validation.json',dict(new_runs=36,new_search_fe=108000,reused_analysis_runs=144,
        exact_passive_reproductions=18,all_actual_fe_exact=True,all_replay_block_allocations_identical=True))
    write_json(out/'artifact_manifest.json',{str(p.relative_to(out)):digest(p)
        for p in out.rglob('*') if p.is_file() and p.name!='artifact_manifest.json'})

if __name__=='__main__':main()

