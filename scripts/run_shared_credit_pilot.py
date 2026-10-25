"""Frozen development comparison of direct-offspring shared credit."""
import argparse,json,shutil
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
from unittest.mock import patch
from run_weighted_pilot import ROOT,auc,digest,write_csv,write_json
from run_portfolio_campaign import analyze
from validate_regional_expansion import independent_hv
from mojssp.io import load_dzn
from mojssp.evaluator import Evaluator
from mojssp.normalization import ObjectiveNormalizer,compute_instance_bounds
from mojssp.shared_credit import run_shared_credit

REFERENCES=['moead','nsga2_individual','spea2_individual','nsga2_ls_individual','mopso_individual',
            'explorer_solo','passive','compatible_replay']

def execute(task):
    out,case,seed,alpha=task
    instance=load_dzn(out/'instances'/f'{case}.dzn')
    original=Evaluator.evaluate;calls=0
    def counted(self,*a,**kw):
        nonlocal calls
        calls+=1;return original(self,*a,**kw)
    with patch.object(Evaluator,'evaluate',counted):
        r=run_shared_credit(instance,seed,alpha)
    assert calls==r['evaluations_used']==3000
    norm=ObjectiveNormalizer(compute_instance_bounds(instance))
    assert abs(independent_hv([norm.normalize_tuple(p) for p in r['pareto_front']])-r['hypervolume'])<1e-10
    if alpha==0:
        source=json.loads((out/'reference'/f'{case}__{seed}__compatible_live.json').read_text())
        for key in ['blocks','allocations','region_trace','pareto_front','checkpoints','migration_events','injection_trace']:
            assert json.loads(json.dumps(r[key]))==source[key],(case,seed,key)
    r.update(case=case,master_seed=seed,method='alpha0' if alpha==0 else 'shared',
        origin='new',actual_evaluator_calls=calls,auc_hv=auc(r['checkpoints'],3000))
    write_json(out/'runs'/f"{case}__{seed}__{r['method']}.json",r)
    return case,seed,r['method'],r['hypervolume']

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--workers',type=int,choices=range(1,9),default=4)
    args=parser.parse_args();out=args.output_dir.resolve()
    if out.exists() or not out.is_relative_to(ROOT/'results/experiments'):parser.error('Choose new output folder')
    prior=ROOT/'results/experiments/subproblem_injection_fixed_trace_20261024'
    previous=json.loads((prior/'config.json').read_text())
    assert all(digest(ROOT/p)==sha for p,sha in previous['source_sha256'].items() if p.startswith('src/'))
    manifests={p.replace('\\','/'):sha for p,sha in json.loads((prior/'artifact_manifest.json').read_text()).items()}
    out.mkdir(parents=True)
    files=sorted((ROOT/'src/mojssp').glob('*.py'))+sorted((ROOT/'scripts').glob('*.py'))
    hashes={str(p.relative_to(ROOT)).replace('\\','/'):digest(p) for p in files}
    for path in files:
        dest=out/'code'/path.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest)
    tasks=[];inputs=[]
    for ci,c in enumerate(previous['cases']):
        name=c['name'];path=prior/'instances'/f'{name}.dzn'
        assert digest(path)==c['sha256']
        dest=out/'instances'/path.name;dest.parent.mkdir(exist_ok=True);shutil.copy2(path,dest)
        for si,seed in enumerate(previous['seeds']):
            for method in REFERENCES+['compatible_live']:
                path=prior/'runs'/f'{name}__{seed}__{method}.json'
                sha=digest(path);assert sha==manifests[str(path.relative_to(prior)).replace('\\','/')]
                r=json.loads(path.read_text())
                assert r['actual_evaluator_calls']==r['evaluations_used']==3000
                dest=out/'reference'/path.name;dest.parent.mkdir(exist_ok=True);shutil.copy2(path,dest)
                inputs.append(dict(case=name,seed=seed,method=method,path=str(path.relative_to(ROOT)).replace('\\','/'),sha256=sha))
                if method!='compatible_live':
                    r.update(origin='reused',source_path=inputs[-1]['path'],source_file_sha256=sha)
                    write_json(out/'runs'/path.name,r)
            for alpha in ([0.,.5] if (ci+si)%2==0 else [.5,0.]):
                tasks.append((out,name,seed,alpha))
    write_json(out/'config.json',dict(cases=previous['cases'],seeds=previous['seeds'],budget=3000,population_size=30,
        arms=['MOEA/D','RegionExplorer'],alphas=[0.,.5],policy='dynamic rounds',
        round_size=300,block_size=50,minimum_share=.1,
        expected_new_runs=36,expected_new_search_fe=108000,reused_records=144,
        source_sha256=hashes,credit='Only direct assisted offspring: alpha to donor source, remainder to recipient; unassisted full recipient; warmup excluded',
        instrumentation='Shadow archive only; real global archive unchanged until block end; alpha0 must reproduce all original trajectories',
        learning='Credited gains divided by actual scored FE; unchanged round_shares and evaluation_quotas',
        gate='Shared mean exceeds passive, alpha0 and BLMR; wins over passive in at least four of six instance means',
        scope='Fixed alpha 0.5 exploratory development; no alpha sweep or untouched confirmation',
        replay='External schedule context only; not an autonomous same-cost comparator',
        timings='Concurrent recorded runtimes descriptive; no fixed-wall-time superiority claim'))
    write_csv(out/'reused_inputs.csv',inputs)
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for i,f in enumerate(as_completed([pool.submit(execute,t) for t in tasks]),1):
            case,seed,method,hv=f.result()
            print(f'{i}/36 {case} {seed} {method} HV={hv:.6f}',flush=True)
    assert all(digest(ROOT/p)==sha for p,sha in hashes.items())
    records=[json.loads(p.read_text()) for p in (out/'runs').glob('*.json')]
    assert len(records)==180
    analyze(out,records,['shared'],REFERENCES+['alpha0'])
    write_json(out/'execution_validation.json',dict(new_runs=36,new_search_fe=108000,
        alpha0_exact_reproductions=18,all_actual_fe_exact=True,all_hv_independent=True))
    write_json(out/'artifact_manifest.json',{str(p.relative_to(out)):digest(p)
        for p in out.rglob('*') if p.is_file() and p.name!='artifact_manifest.json'})

if __name__=='__main__':main()

