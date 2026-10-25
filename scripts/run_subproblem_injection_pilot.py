"""Development gate and fresh-instance evaluation for compatible parent injection."""
import argparse,json,shutil
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
from collections import defaultdict
from dataclasses import replace,asdict
from unittest.mock import patch
import numpy as np
from run_weighted_pilot import ROOT,auc,digest,write_json,write_csv
from run_portfolio_campaign import analyze
from run_regional_composition_comparison import native_individual,INDIVIDUALS
from run_regional_explorer_controls import run_individual
from generate_mojssp_instances import INSTANCES_CONFIG,generate_single_instance
from validate_regional_expansion import independent_hv
from mojssp.io import load_dzn
from mojssp.evaluator import Evaluator
from mojssp.normalization import ObjectiveNormalizer,compute_instance_bounds
from mojssp.regional_injection import run_blmr_injection
from mojssp.subproblem_injection import run_subproblem_injection

CONTROLS=list(INDIVIDUALS)+['explorer_solo','passive','maxmin']
METHODS=CONTROLS+['compatible']
FRESH_SEEDS=[5001,5002,5003]

def execute(task):
    out,case,seed,method=task
    instance=load_dzn(out/'instances'/f'{case}.dzn')
    original=Evaluator.evaluate;calls=0
    def counted(self,*a,**kw):
        nonlocal calls
        calls+=1;return original(self,*a,**kw)
    with patch.object(Evaluator,'evaluate',counted):
        if method=='compatible':r=run_subproblem_injection(instance,seed)
        elif method in ('passive','maxmin'):r=run_blmr_injection(instance,seed,method=='maxmin')
        elif method=='explorer_solo':r=run_individual(instance,seed,'random')
        else:r=native_individual(instance,seed,method)
    assert calls==r['evaluations_used']==3000
    norm=ObjectiveNormalizer(compute_instance_bounds(instance))
    assert abs(independent_hv([norm.normalize_tuple(p) for p in r['pareto_front']])-r['hypervolume'])<1e-10
    r.update(case=case,master_seed=seed,method=method,origin='new',
        actual_evaluator_calls=calls,auc_hv=auc(r['checkpoints'],3000))
    write_json(out/'runs'/f'{case}__{seed}__{method}.json',r)
    return case,seed,method,r['hypervolume'],r.get('migration_uses',0)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=['development','fresh'],required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--development-dir',type=Path)
    parser.add_argument('--workers',type=int,choices=range(1,9),default=4)
    args=parser.parse_args();out=args.output_dir.resolve()
    if out.exists() or not out.is_relative_to(ROOT/'results/experiments'):parser.error('Choose a new experiment folder')
    prior=ROOT/'results/experiments/blmr_to_moead_dynamic_injection_20261024'
    previous=json.loads((prior/'config.json').read_text())
    assert all(digest(ROOT/p)==sha for p,sha in previous['source_sha256'].items() if p.startswith('src/'))
    if args.stage=='fresh':
        if args.development_dir is None:parser.error('Fresh stage requires gated development results')
        dev=args.development_dir.resolve()
        assert json.loads((dev/'decision.json').read_text())['advance_to_fresh']
        devconfig=json.loads((dev/'config.json').read_text())
        assert all(digest(ROOT/p)==sha for p,sha in devconfig['source_sha256'].items())
    out.mkdir(parents=True)
    files=sorted((ROOT/'src/mojssp').glob('*.py'))+sorted((ROOT/'scripts').glob('*.py'))
    hashes={str(p.relative_to(ROOT)).replace('\\','/'):digest(p) for p in files}
    for p in files:
        target=out/'code'/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
    references=[];tasks=[];cases=[]
    (out/'instances').mkdir()
    if args.stage=='development':
        manifest={p.replace('\\','/'):sha for p,sha in json.loads((prior/'artifact_manifest.json').read_text()).items()}
        seeds=[100,200,300]
        for c in previous['cases']:
            if c['group']!='development':continue
            name=c['name'];source=prior/'instances'/f'{name}.dzn'
            assert digest(source)==c['sha256']
            shutil.copy2(source,out/'instances'/source.name)
            cases.append(dict(name=name,sha256=digest(source),seeds=seeds))
            for seed in seeds:
                for method in CONTROLS:
                    oldmethod='active' if method=='maxmin' else method
                    source=prior/'development/runs'/f'{name}__{seed}__{oldmethod}.json'
                    sha=digest(source);assert sha==manifest[str(source.relative_to(prior)).replace('\\','/')]
                    r=json.loads(source.read_text())
                    assert r['actual_evaluator_calls']==r['evaluations_used']==3000
                    r.update(method=method,origin='reused',source_path=str(source.relative_to(ROOT)).replace('\\','/'),source_file_sha256=sha)
                    write_json(out/'runs'/f'{name}__{seed}__{method}.json',r)
                    references.append(dict(case=name,seed=seed,method=method,path=r['source_path'],sha256=sha))
                tasks.append((out,name,seed,'compatible'))
        assert len(tasks)==18 and len(references)==144
    else:
        seeds=FRESH_SEEDS
        templates=[c for c in INSTANCES_CONFIG if c.group in ('base','interactions')]
        assert len(templates)==13
        known={digest(p) for p in (ROOT/'data').rglob('*.dzn')}
        known.update(digest(p) for p in (ROOT/'results/experiments').glob('*/instances/*.dzn'))
        for index,template in enumerate(templates):
            cfg=replace(template,name='fresh_compatible_'+template.name,seed=template.seed+240000)
            content,metadata=generate_single_instance(cfg)
            path=out/'instances'/f'{cfg.name}.dzn';path.write_text(content,encoding='utf-8')
            assert digest(path) not in known
            cases.append(dict(name=cfg.name,sha256=digest(path),seeds=seeds,template=asdict(template),generator_config=asdict(cfg)))
            write_json(out/'instance_metadata'/f'{cfg.name}.json',metadata)
            for si,seed in enumerate(seeds):
                shift=(index*3+si)%len(METHODS)
                tasks.extend((out,cfg.name,seed,m) for m in METHODS[shift:]+METHODS[:shift])
        assert len(tasks)==351
    write_json(out/'config.json',dict(stage=args.stage,cases=cases,seeds=seeds,methods=METHODS,controls=CONTROLS,
        budget=3000,population_size=30,block_size=50,policy='dynamic',round_size=300,minimum_share=.1,
        expected_new_runs=len(tasks),expected_new_search_fe=len(tasks)*3000,reused_runs=len(references),
        source_sha256=hashes,migration=dict(source='RegionExplorer',recipient='MOEA/D',every=10,max_uses_per_block=5,
            eligibility='First observed source, global archive, not observed in recipient archive or population at block start',
            donor_pool='All eligible source entries at block start; distinct donor uses per block',
            selection='Minimum native Tchebycheff score for live target weight and ideal point; genotype ID tie break',
            quality_gate='None; this experiment selects donor compatibility without imposing an extra improvement threshold'),
        development_gate='Mean compatible exceeds passive, maxmin and BLMR; wins against passive on at least four of six instance means',
        fresh_plan=dict(cases=13,seeds=FRESH_SEEDS,generator_seed_offset=240000,methods=METHODS),
        scope='Exploratory development' if args.stage=='development' else 'Candidate frozen after development; fresh synthetic instances from same generator',
        accounting='All FE include initialization; reused data not new runs; extra audit and tests separate',
        timings='Concurrent timings descriptive; not fixed wall-time comparison'))
    if references:write_csv(out/'reused_inputs.csv',references)
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for i,f in enumerate(as_completed([pool.submit(execute,t) for t in tasks]),1):
            case,seed,method,hv,uses=f.result()
            print(f'{i}/{len(tasks)} {case} {seed} {method} HV={hv:.6f} uses={uses}',flush=True)
    assert all(digest(ROOT/p)==sha for p,sha in hashes.items())
    records=[json.loads(p.read_text()) for p in (out/'runs').glob('*.json')]
    assert len(records)==len(cases)*len(seeds)*len(METHODS)
    analyze(out,records,['compatible'],CONTROLS)
    cells=defaultdict(list)
    for r in records:cells[r['case'],r['method']].append(r['hypervolume'])
    matrix=[dict(case=c['name'],**{m:float(np.mean(cells[c['name'],m])) for m in METHODS}) for c in cases]
    means={m:float(np.mean([row[m] for row in matrix])) for m in METHODS}
    wins=sum(row['compatible']>row['passive'] for row in matrix)
    advance=means['compatible']>max(means[m] for m in ['passive','maxmin','explorer_solo']) and wins>=4
    write_csv(out/'hv_matrix.csv',matrix)
    write_json(out/'decision.json',dict(means=means,wins_vs_passive=int(wins),instances=len(cases),
        advance_to_fresh=bool(advance) if args.stage=='development' else None,
        decision_rule='Predeclared development gate; no post-hoc parameter changes',
        primary_reference='BLMR alone remains mandatory'))
    write_json(out/'execution_validation.json',dict(new_runs=len(tasks),new_search_fe=3000*len(tasks),reused_runs=len(references),
        all_actual_fe_exact=True,all_final_hv_independent=True))
    write_json(out/'artifact_manifest.json',{str(p.relative_to(out)):digest(p) for p in out.rglob('*') if p.is_file() and p.name!='artifact_manifest.json'})

if __name__=='__main__':main()

