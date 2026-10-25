"""Compare dynamic reserve floors while preserving regional operators and rounds."""
import argparse
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor,as_completed
import json
from pathlib import Path
import shutil
from unittest.mock import patch

import numpy as np
from run_weighted_pilot import ROOT,digest,write_csv,write_json,auc
from validate_regional_expansion import independent_hv
from mojssp.evaluator import Evaluator
from mojssp.decoder import Decoder
from mojssp.solution import Solution
from mojssp.schedule_validator import validate_schedule
from mojssp.io import load_dzn
from mojssp.normalization import ObjectiveNormalizer,compute_instance_bounds
from mojssp.dynamic_budget import round_shares
from mojssp.fixed_budget import evaluation_quotas
from mojssp.regional_portfolio import run_regional_policy_experiment


def execute(task):
    output,phase,case,seed,reserve=task
    instance=load_dzn(output/'instances'/f'{case}.dzn')
    evaluator=Evaluator.evaluate
    calls=0
    def counted(self,*a,**kw):
        nonlocal calls
        calls+=1
        return evaluator(self,*a,**kw)
    with patch.object(Evaluator,'evaluate',counted):
        r=run_regional_policy_experiment(instance,seed,['SPEA2','RegionExplorer'],'dynamic',minimum_share=reserve)
    norm=ObjectiveNormalizer(compute_instance_bounds(instance))
    assert calls==r['evaluations_used']==3000
    assert abs(independent_hv([norm.normalize_tuple(p) for p in r['pareto_front']])-r['hypervolume'])<1e-10
    method=f'reserve_{round(100*reserve):02d}'
    r.update(case=case,master_seed=seed,phase=phase,method=method,actual_evaluator_calls=calls,
        auc_hv=auc(r['checkpoints'],3000),minimum_share=reserve)
    write_json(output/phase/'runs'/f'{case}__{seed}__{method}.json',r)
    return case,seed,method,r['hypervolume']


def run_tasks(tasks,workers):
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for index,future in enumerate(as_completed([pool.submit(execute,t) for t in tasks]),1):
            print(f'{index}/{len(tasks)} {future.result()}',flush=True)


def summarize(folder,records,cases,methods):
    cells=defaultdict(list)
    for r in records: cells[r['case'],r['method']].append(r['hypervolume'])
    rows=[dict(case=c,**{m:float(np.mean(cells[c,m])) for m in methods}) for c in cases]
    write_csv(folder/'by_instance.csv',rows)
    means={m:float(np.mean([r[m] for r in rows])) for m in methods}
    write_csv(folder/'summary.csv',[dict(method=m,mean_hv=v) for m,v in means.items()])
    rng=np.random.default_rng(20261023)
    comparisons=[]
    for candidate in [m for m in methods if m.startswith('reserve_')]:
        for control in [m for m in methods if not m.startswith('reserve_') or m=='reserve_10']:
            if candidate==control: continue
            delta=np.asarray([r[candidate]-r[control] for r in rows])
            bootstrap=rng.choice(delta,(20000,len(rows)),replace=True).mean(axis=1)
            comparisons.append(dict(candidate=candidate,control=control,mean_difference=float(delta.mean()),
                bootstrap95_low=float(np.quantile(bootstrap,.025)),bootstrap95_high=float(np.quantile(bootstrap,.975)),
                wins=int(sum(delta>1e-12)),ties=int(sum(abs(delta)<=1e-12)),losses=int(sum(delta< -1e-12))))
    write_csv(folder/'comparisons.csv',comparisons)
    return means


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--workers',type=int,default=4,choices=range(1,9))
    args=parser.parse_args()
    output=args.output_dir.resolve()
    if output.exists() or not output.is_relative_to(ROOT/'results/experiments'):
        parser.error('Choose a new experiment directory')
    bank=ROOT/'results/experiments/regional_validation_expanded_20261023'
    dev=ROOT/'results/experiments/regional_policy_integration_development_20261023'
    transfer=ROOT/'results/experiments/regional_policy_transfer_20261023'
    old=json.loads((dev/'config.json').read_text())
    changed={name.replace('\\','/') for name,sha in old['source_sha256'].items() if digest(ROOT/name)!=sha}
    assert changed=={'src/mojssp/regional_portfolio.py','scripts/run_regional_experiment.py'},changed
    cases=json.loads((bank/'config.json').read_text())['cases']
    development=[c for c in cases if c['group']=='fresh_seeds']
    additional=[c for c in cases if c['group']=='transfer']
    output.mkdir(parents=True)
    files=sorted((ROOT/'src/mojssp').glob('*.py'))+sorted((ROOT/'scripts').glob('*.py'))
    hashes={str(p.relative_to(ROOT)):digest(p) for p in files}
    for p in files:
        target=output/'code'/p.relative_to(ROOT)
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(p,target)
    references={'development':[],'transfer':[]}
    baselines={}
    provenance={}
    manifests={folder:json.loads((folder/'artifact_manifest.json').read_text()) for folder in [bank,dev,transfer]}
    for c in cases:
        phase='development' if c['group']=='fresh_seeds' else 'transfer'
        target=output/'instances'/f"{c['name']}.dzn"
        target.parent.mkdir(exist_ok=True)
        assert digest(bank/'instances'/target.name)==c['sha256']
        shutil.copy2(bank/'instances'/target.name,target)
        for seed in [100,200,300]:
            paths=[(bank/'runs'/f"{c['name']}__{seed}__{m}.json",m,bank) for m in ['moead','explorer_solo']]
            if phase=='development':
                paths += [(dev/'individuals/runs'/f"{c['name']}__{seed}__spea2_individual.json",'spea2_solo',dev),
                          (dev/'assignment/runs'/f"{c['name']}__{seed}__spea2_regional_dynamic.json",'reserve_10',dev)]
            else:
                paths += [(transfer/'runs'/f"{c['name']}__{seed}__native_individual.json",'spea2_solo',transfer),
                          (transfer/'runs'/f"{c['name']}__{seed}__spea2_regional_dynamic.json",'reserve_10',transfer)]
            for path,method,folder in paths:
                assert digest(path)==manifests[folder][str(path.relative_to(folder))]
                r=json.loads(path.read_text())
                assert r['actual_evaluator_calls']==3000
                r['method']=method
                destination=output/'reference'/phase/f"{c['name']}__{seed}__{method}.json"
                write_json(destination,r)
                provenance[str(path.relative_to(ROOT))]=digest(path)
                if method=='reserve_10' and phase=='development':
                    baselines[c['name'],seed]=r
                else: references[phase].append(r)
    write_json(output/'config.json',dict(arms=['SPEA2','RegionExplorer'],budget=3000,block_size=50,population_size=30,
        minimum_shares=[.1,.05,.01],round_size=300,initial_round='300 FE uniformly, unchanged',
        cases=cases,seeds=[100,200,300],source_sha256=hashes,reference_sha256=provenance,
        changed_legacy_files=sorted(changed),expected_development_runs=54,
        selection='Highest development mean HV among reserve floors 10%, 5%, 1%; freeze before additional bank',
        scope='Exploratory reuse of previously observed cases, not an untouched validation set',
        timing='Concurrent wall times are not an equal-time comparison'))
    run_tasks([(output,'development',c['name'],s,r) for c in development for s in [100,200,300] for r in [.1,.05,.01]],args.workers)
    records=[json.loads(p.read_text()) for p in (output/'development/runs').glob('*.json')]
    for r in [r for r in records if r['method']=='reserve_10']:
        prior=baselines[r['case'],r['master_seed']]
        for key in ['pareto_front','checkpoints','allocations','region_trace','blocks']:
            assert r[key]==prior[key],(r['case'],r['master_seed'],key)
    means=summarize(output/'development',records+references['development'],[c['name'] for c in development],
                    ['moead','spea2_solo','explorer_solo','reserve_10','reserve_05','reserve_01'])
    chosen=max(['reserve_10','reserve_05','reserve_01'],key=lambda m:means[m])
    share=int(chosen.rsplit('_',1)[1])/100
    write_json(output/'selection.json',dict(method=chosen,minimum_share=share,development_means=means,
        original_profile_reproduced_exactly_in_18_runs=True))
    print('Frozen choice:',chosen,means,flush=True)
    additional_records=[]
    if chosen!='reserve_10':
        run_tasks([(output,'transfer',c['name'],s,share) for c in additional for s in [100,200,300]],args.workers)
        additional_records=[json.loads(p.read_text()) for p in (output/'transfer/runs').glob('*.json')]
    else:
        (output/'transfer').mkdir(exist_ok=True)
    transfer_means=summarize(output/'transfer',additional_records+references['transfer'],[c['name'] for c in additional],
        ['moead','spea2_solo','explorer_solo','reserve_10']+([chosen] if chosen!='reserve_10' else []))
    checked=set()
    allocations=[]
    for c in cases:
        instance=load_dzn(output/'instances'/f"{c['name']}.dzn")
        for r in [r for r in records+additional_records if r['case']==c['name']]:
            groups=defaultdict(list)
            for b in r['blocks']: groups[b['round_index']].append(b)
            shares=dict.fromkeys(r['arms'],.5)
            for index,blocks in sorted(groups.items()):
                names=r['arms'];order=names[index%2:]+names[:index%2]
                quotas=evaluation_quotas(300,{n:shares[n] for n in order})
                assert quotas=={n:sum(b['evaluations_used'] for b in blocks if b['arm_name']==n) for n in names}
                rates={}
                for n in names:
                    scored=[b for b in blocks if b['arm_name']==n and b['phase']!='warmup']
                    fe=sum(b['evaluations_used'] for b in scored)
                    rates[n]=sum(b['reward'] for b in scored)/fe if fe else 0.
                shares=round_shares(rates,r['minimum_share'])
            for arm,fe in r['allocations'].items():
                allocations.append(dict(phase=r['phase'],case=r['case'],seed=r['master_seed'],method=r['method'],arm=arm,percentage=100*fe/3000))
            for entry in r['front_entries']:
                key=c['name'],tuple(entry['sequence']),tuple(entry['modes'])
                if key in checked: continue
                solution=Solution(key[1],key[2]);solution.validate_with_instance(instance)
                schedule=Decoder().decode(instance,solution)
                assert not validate_schedule(instance,schedule)
                assert np.allclose(tuple(Evaluator().evaluate(instance,schedule)),entry['objectives'],rtol=0,atol=1e-9)
                checked.add(key)
    write_csv(output/'allocations.csv',allocations)
    by=defaultdict(list)
    for r in allocations: by[r['phase'],r['method'],r['arm']].append(r['percentage'])
    write_csv(output/'allocation_summary.csv',[dict(phase=p,method=m,arm=a,mean_percentage=float(np.mean(v)),minimum_percentage=min(v),maximum_percentage=max(v))
        for (p,m,a),v in sorted(by.items())])
    assert all(digest(ROOT/p)==sha for p,sha in hashes.items())
    write_json(output/'validation.json',dict(new_runs=len(records)+len(additional_records),new_search_fe=3000*(len(records)+len(additional_records)),
        exact_evaluator_calls=True,independent_hv=True,all_round_quotas_recomputed=True,
        original_10_percent_profile_reproduced_in_18_runs=True,validated_saved_genotypes=len(checked),extra_audit_fe=len(checked)))
    write_json(output/'decision.json',dict(selected_method=chosen,development_means=means,transfer_means=transfer_means,
        better_than_regional_solo_on_transfer=transfer_means[chosen]>transfer_means['explorer_solo'],
        scope='Previously observed development and transfer banks; experimental comparison, no untouched holdout'))
    write_json(output/'artifact_manifest.json',{str(p.relative_to(output)):digest(p) for p in sorted(output.rglob('*')) if p.is_file() and p.name!='artifact_manifest.json'})
    print((output/'transfer/summary.csv').read_text(encoding='utf-8-sig'))
    print((output/'transfer/comparisons.csv').read_text(encoding='utf-8-sig'))


if __name__=='__main__': main()
