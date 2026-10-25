"""Compare frozen regional compositions on development and additional instances."""
import argparse,ast,json,shutil,time
from pathlib import Path
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor,as_completed
from unittest.mock import patch
import numpy as np
from run_weighted_pilot import ROOT,auc,digest,write_csv,write_json
from run_regional_explorer_controls import run_individual
from run_portfolio_campaign import analyze
from validate_regional_expansion import independent_hv
from mojssp.arms import NSGA2Arm,NSGA2LSArm,MOPSOArm
from mojssp.moead import MOEADArm
from mojssp.spea2 import SPEA2Arm
from mojssp.io import load_dzn
from mojssp.evaluator import Evaluator
from mojssp.hypervolume import compute_archive_hypervolume
from mojssp.normalization import ObjectiveNormalizer,compute_instance_bounds
from mojssp.regional_portfolio import run_regional_policy_experiment,POLICY_PROFILES

COMPOSITIONS={
    'spea2_regional':['SPEA2','RegionExplorer'],
    'nsga2_regional':['NSGA-II','RegionExplorer'],
    'moead_regional':['MOEA/D','RegionExplorer'],
    'quartet_regional':['MOEA/D','NSGA-II','SPEA2','RegionExplorer']}
POLICIES=('scaled','dynamic')
INDIVIDUALS={
    'moead':('MOEA/D',MOEADArm,17),
    'nsga2_individual':('NSGA-II',NSGA2Arm,29),
    'spea2_individual':('SPEA2',SPEA2Arm,43),
    'nsga2_ls_individual':('NSGA-II+LS',NSGA2LSArm,59),
    'mopso_individual':('MOPSO',MOPSOArm,97)}
CONTROLS=tuple(INDIVIDUALS)+('explorer_solo',)
CANDIDATES=tuple(c+'_'+p for c in COMPOSITIONS for p in POLICIES)
METHODS=CONTROLS+CANDIDATES

def native_individual(instance,seed,method,budget=3000):
    _,cls,offset=INDIVIDUALS[method]
    kwargs=dict(population_size=30,seed=(seed*10007+offset)%(2**31-1),max_evaluations=budget)
    if cls in (NSGA2Arm,NSGA2LSArm):kwargs['max_generations']=None
    if cls is SPEA2Arm:kwargs['archive_size']=30
    if cls is NSGA2LSArm:kwargs.update(max_ls_iterations=10,max_ls_neighbors=10)
    arm=cls(instance,**kwargs)
    norm=ObjectiveNormalizer(compute_instance_bounds(instance))
    checkpoints=[];started=time.perf_counter()
    while arm.total_evaluations<budget:
        result=arm.run(min(50,budget-arm.total_evaluations))
        assert result.evaluations_used>0
        checkpoints.append([arm.total_evaluations,compute_archive_hypervolume(result.solutions,norm)])
    entries=list(result.solutions.entries)
    return dict(budget=budget,evaluations_used=arm.total_evaluations,checkpoints=checkpoints,
        hypervolume=checkpoints[-1][1],runtime_seconds=time.perf_counter()-started,
        front_entries=[dict(sequence=list(e.solution.sequence),modes=list(e.solution.modes),objectives=list(e.objectives)) for e in entries],
        pareto_front=[list(e.objectives) for e in entries],completed=True)

class RemoveInactiveReserveOverride(ast.NodeTransformer):
    def visit_FunctionDef(self,node):
        self.generic_visit(node)
        if node.name=='run_regional_policy_experiment':
            node.args.kwonlyargs=[];node.args.kw_defaults=[]
        return node
    def visit_If(self,node):
        if isinstance(node.test,ast.Compare):
            test=node.test
        elif isinstance(node.test,ast.BoolOp):
            test=node.test.values[0]
        else:test=None
        if isinstance(test,ast.Compare) and isinstance(test.left,ast.Name) and test.left.id=='minimum_share':
            return None
        return self.generic_visit(node)

def compatible_sources(folder):
    config=json.loads((folder/'config.json').read_text())
    differences=[]
    for rel,sha in config['source_sha256'].items():
        rel=rel.replace('\\','/')
        if not rel.startswith('src/'):continue
        if digest(ROOT/rel)==sha:continue
        assert rel=='src/mojssp/regional_portfolio.py',rel
        frozen=folder/'code'/rel
        assert digest(frozen)==sha
        old=ast.parse(frozen.read_text(encoding='utf-8'))
        current=RemoveInactiveReserveOverride().visit(ast.parse((ROOT/rel).read_text(encoding='utf-8')))
        assert ast.dump(old,include_attributes=False)==ast.dump(current,include_attributes=False)
        differences.append(dict(path=rel,compatibility='AST identical after removing inactive minimum_share=None override'))
    return differences

def execute(task):
    output,group,case,seed,method=task
    instance=load_dzn(output/'instances'/f'{case}.dzn')
    original=Evaluator.evaluate;calls=0
    def counted(self,*a,**kw):
        nonlocal calls
        calls+=1;return original(self,*a,**kw)
    with patch.object(Evaluator,'evaluate',counted):
        if method=='explorer_solo':r=run_individual(instance,seed,'random')
        elif method in INDIVIDUALS:r=native_individual(instance,seed,method)
        else:
            composition,policy=method.rsplit('_',1)
            r=run_regional_policy_experiment(instance,seed,COMPOSITIONS[composition],policy,False)
    assert calls==r['evaluations_used']==3000
    norm=ObjectiveNormalizer(compute_instance_bounds(instance))
    hv=independent_hv([norm.normalize_tuple(p) for p in r['pareto_front']])
    assert abs(hv-r['hypervolume'])<1e-10
    r.update(case=case,master_seed=seed,method=method,group=group,origin='new',
        actual_evaluator_calls=calls,auc_hv=auc(r['checkpoints'],3000))
    write_json(output/group/'runs'/f'{case}__{seed}__{method}.json',r)
    return group,case,seed,method,hv

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--workers',type=int,choices=range(1,9),default=4)
    args=parser.parse_args();out=args.output_dir.resolve()
    if out.exists() or not out.is_relative_to(ROOT/'results/experiments'):parser.error('Choose new experiment directory')
    base=ROOT/'results/experiments'
    expanded=base/'regional_validation_expanded_20261023'
    integration=base/'regional_policy_integration_development_20261023'
    transfer=base/'regional_policy_transfer_20261023'
    five=base/'regional_five_policies_mopso_20261024'
    compatibility={str(p.relative_to(ROOT)):compatible_sources(p) for p in [expanded,integration,transfer,five]}
    prior=json.loads((expanded/'config.json').read_text())
    cases=[dict(c,group='development' if c['group']=='fresh_seeds' else 'transfer',seeds=[100,200,300]) for c in prior['cases']]
    assert len(cases)==19 and len({c['name'] for c in cases})==19
    out.mkdir(parents=True)
    files=sorted((ROOT/'src/mojssp').glob('*.py'))+sorted((ROOT/'scripts').glob('*.py'))
    hashes={str(p.relative_to(ROOT)).replace('\\','/'):digest(p) for p in files}
    for p in files:
        dest=out/'code'/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
    manifests={p:json.loads((p/'artifact_manifest.json').read_text()) for p in [expanded,integration,transfer,five]}
    tasks=[];references=[]
    for c in cases:
        name,group=c['name'],c['group']
        src=expanded/'instances'/f'{name}.dzn';assert digest(src)==c['sha256']
        (out/'instances').mkdir(exist_ok=True);shutil.copy2(src,out/'instances'/src.name)
        for si,seed in enumerate(c['seeds']):
            # Rotate submission order without changing seeded search trajectories.
            shift=(cases.index(c)*3+si)%len(METHODS)
            for method in METHODS[shift:]+METHODS[:shift]:
                source=None
                if group=='development':
                    if method in ('spea2_individual','mopso_individual','explorer_solo') or method.startswith('spea2_regional_'):
                        folder=five;source=folder/'runs'/f'{name}__{seed}__{method}.json'
                    elif method=='moead':
                        folder=expanded;source=folder/'runs'/f'{name}__{seed}__moead.json'
                    elif method=='nsga2_individual':
                        folder=integration;source=folder/'individuals/runs'/f'{name}__{seed}__{method}.json'
                    elif method.startswith(('moead_regional_','nsga2_regional_')):
                        folder=integration;source=folder/'assignment/runs'/f'{name}__{seed}__{method}.json'
                else:
                    if method in ('moead','explorer_solo'):
                        folder=expanded;source=folder/'runs'/f'{name}__{seed}__{method}.json'
                    elif method in ('spea2_individual','spea2_regional_dynamic'):
                        folder=transfer
                        oldmethod='native_individual' if method=='spea2_individual' else method
                        source=folder/'runs'/f'{name}__{seed}__{oldmethod}.json'
                if source is None:
                    tasks.append((out,group,name,seed,method));continue
                relative=str(source.relative_to(folder)).replace('\\','/')
                source_sha=digest(source)
                expected={k.replace('\\','/'):v for k,v in manifests[folder].items()}[relative]
                assert source_sha==expected,source
                record=json.loads(source.read_text())
                assert record['case']==name and record['master_seed']==seed
                assert record['actual_evaluator_calls']==record['evaluations_used']==record['budget']==3000
                if method in CANDIDATES:
                    composition,policy=method.rsplit('_',1)
                    assert record['arms']==COMPOSITIONS[composition] and record['policy']==policy
                    assert record['policy_profile']==POLICY_PROFILES[policy] and not record['guidance']
                record.update(method=method,group=group,origin='reused',
                    source_path=str(source.relative_to(ROOT)).replace('\\','/'),source_file_sha256=source_sha)
                write_json(out/group/'runs'/f'{name}__{seed}__{method}.json',record)
                references.append(dict(group=group,case=name,seed=seed,method=method,path=record['source_path'],sha256=source_sha))
    assert len(tasks)==444 and len(references)==354
    write_json(out/'config.json',dict(cases=cases,seeds=[100,200,300],compositions=COMPOSITIONS,
        policies=POLICIES,methods=METHODS,controls=CONTROLS,candidates=CANDIDATES,budget=3000,
        population_size=30,block_size=50,policy_profiles={p:POLICY_PROFILES[p] for p in POLICIES},
        guidance=False,expected_new_runs=len(tasks),expected_new_search_fe=len(tasks)*3000,
        reused_runs=len(references),total_rows=798,source_sha256=hashes,source_compatibility=compatibility,
        scope='Both banks exploratory; the additional 13 cases have already informed earlier research. No final holdout claim.',
        statistical_unit='Mean seeds within instance first; paired instance bootstrap, no seed pseudoreplication',
        timing='Mixed reused and concurrent runs: timings descriptive only',
        quartet_order=COMPOSITIONS['quartet_regional'],quartet_dynamic_first_round='300 FE split 75 each; four 50 FE neutral blocks included',
        minimum_share='10 percent per arm per round, not 10 percent total; quartet leaves 60 percent adaptive residual',
        seed_offsets={m:v[2] for m,v in INDIVIDUALS.items()}))
    write_csv(out/'reused_runs.csv',references)
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for i,f in enumerate(as_completed([pool.submit(execute,t) for t in tasks]),1):
            group,case,seed,method,hv=f.result()
            print(f'{i}/{len(tasks)} {group} {case} {seed} {method} HV={hv:.6f}',flush=True)
    assert all(digest(ROOT/p)==sha for p,sha in hashes.items())
    for group in ('development','transfer'):
        records=[json.loads(p.read_text()) for p in (out/group/'runs').glob('*.json')]
        expected=(6 if group=='development' else 13)*3*len(METHODS)
        assert len(records)==expected
        analyze(out/group,records,list(CANDIDATES),list(CONTROLS))
        allocations=[dict(case=r['case'],seed=r['master_seed'],method=r['method'],arm=a,fe=fe,percentage=100*fe/3000)
            for r in records for a,fe in r.get('allocations',{}).items()]
        write_csv(out/group/'allocations.csv',allocations)
        cells=defaultdict(list)
        for a in allocations:cells[a['method'],a['arm']].append(a['percentage'])
        write_csv(out/group/'allocation_summary.csv',[dict(method=m,arm=a,mean_percentage=float(np.mean(v)),
            min_percentage=min(v),max_percentage=max(v)) for (m,a),v in sorted(cells.items())])
    write_json(out/'execution_validation.json',dict(new_runs=444,new_search_fe=1332000,reused_runs=354,
        total_records=798,source_hashes_unchanged=True))
    write_json(out/'artifact_manifest.json',{str(p.relative_to(out)):digest(p) for p in out.rglob('*')
        if p.is_file() and p.name!='artifact_manifest.json'})

if __name__=='__main__':main()

