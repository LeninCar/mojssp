"""Run a configured portfolio campaign with compatible saved controls."""
import argparse
from collections import defaultdict
from dataclasses import asdict
from fractions import Fraction
import json
import math
from pathlib import Path
import shutil
import time
from unittest.mock import patch

import numpy as np
from run_weighted_pilot import ROOT, auc, digest, write_csv, write_json
from run_dynamic_pilot import compatible_controls
from mojssp.evaluator import Evaluator
from mojssp.fixed_budget import evaluation_quotas
from mojssp.hypervolume import compute_hypervolume
from mojssp.io import load_dzn
from mojssp.normalization import ObjectiveNormalizer, compute_instance_bounds
from mojssp.project_paths import HISTORICAL_ROOT
from mojssp.runner import run_phase2_portfolio_experiment


def validate_design(design):
    names = []
    for treatment in design['treatments']:
        name, policy, arms = treatment['name'],treatment['policy'],treatment['arms']
        if not name or any(character not in 'abcdefghijklmnopqrstuvwxyz0123456789_' for character in name):
            raise ValueError('Treatment names must be safe lowercase identifiers')
        names.append(name)
        if len(arms)<2 or len(set(arms))!=len(arms) or not set(arms)<= {'MOEA/D','NSGA-II','SPEA2'}:
            raise ValueError('Invalid portfolio composition')
        if policy not in ['scaled','uniform','weighted','dynamic','ph','sw_ucb']:
            raise ValueError('Invalid portfolio policy')
        if policy=='weighted':
            shares = {arm:Fraction(value) for arm,value in treatment['shares'].items()}
            if set(shares)!=set(arms): raise ValueError('Shares must match selected arms')
            quotas = evaluation_quotas(design['budget'],shares)
            if min(quotas.values())<design['population_size']: raise ValueError('Insufficient initialization budget')
    if len(names)!=len(set(names)) or not names: raise ValueError('Treatment names must be unique')


def analyze(output,records,candidates,controls):
    fields=['case','master_seed','method','hypervolume','auc_hv','runtime_seconds']
    rows=[{key:record[key] for key in fields} for record in records]
    write_csv(output/'runs.csv',rows)
    cells=defaultdict(list)
    for row in rows: cells[row['case'],row['method']].append(row)
    by_instance=[dict(case=case,method=method,seeds=len(group),
        **{f'mean_{key}':float(np.mean([row[key] for row in group])) for key in fields[3:]})
        for (case,method),group in sorted(cells.items())]
    write_csv(output/'by_instance.csv',by_instance)
    summary=[dict(method=method,**{key:float(np.mean([row[key] for row in by_instance if row['method']==method]))
        for key in ['mean_hypervolume','mean_auc_hv','mean_runtime_seconds']}) for method in controls+candidates]
    write_csv(output/'summary.csv',summary)
    index={(row['case'],row['method']):row for row in by_instance}
    cases=sorted({row['case'] for row in by_instance});rng=np.random.default_rng(20261023)
    comparisons=[]
    for candidate in candidates:
        for control in controls:
            for metric in ['hypervolume','auc_hv']:
                delta=np.array([index[case,candidate][f'mean_{metric}']-index[case,control][f'mean_{metric}'] for case in cases])
                lo,hi=np.quantile(rng.choice(delta,size=(20000,len(cases))).mean(axis=1),[.025,.975])
                comparisons.append(dict(candidate=candidate,control=control,metric=metric,
                    mean_difference=float(delta.mean()),bootstrap95_low=float(lo),bootstrap95_high=float(hi),
                    positive_bases=int(sum(delta>1e-12)),tied_bases=int(sum(abs(delta)<=1e-12)),negative_bases=int(sum(delta<-1e-12))))
    write_csv(output/'comparisons.csv',comparisons)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--design',type=Path,required=True)
    parser.add_argument('--controls',type=Path,required=True)
    parser.add_argument('--reference',type=Path,required=True,help='Latest validated dynamic pilot, with the current core code')
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    design=json.loads(args.design.read_text(encoding='utf-8'));validate_design(design)
    source,reference,output=args.controls.resolve(),args.reference.resolve(),args.output_dir.resolve()
    if output.exists() or output.is_relative_to(HISTORICAL_ROOT): parser.error('Choose a new output outside historical results')
    previous=json.loads((source/'config.json').read_text(encoding='utf-8'))
    latest=json.loads((reference/'config.json').read_text(encoding='utf-8'))
    assert previous['split']==latest['split']=='development'
    assert previous['cases']==latest['cases'] and previous['master_seeds']==latest['master_seeds']
    assert all(digest(ROOT/name)==sha for name,sha in latest['source_sha256'].items() if name.startswith('src/'))
    provenance=compatible_controls(source,previous)
    assert (design['budget'],design['block_size'],design['population_size'])==(3000,50,30)
    controls=[];inputs={};control_methods=list(previous['methods'])+['dynamic']
    for location,methods in [(source,previous['methods']),(reference,['dynamic'])]:
        manifest=json.loads((location/'artifact_manifest.json').read_text(encoding='utf-8'))
        for case in previous['cases']:
            for seed in previous['master_seeds']:
                for method in methods:
                    path=location/'runs'/f"{case['name']}__{seed}__{method}.json"
                    sha=digest(path);assert sha==manifest[str(path.relative_to(location)).replace('\\','/')]
                    record=json.loads(path.read_text(encoding='utf-8'))
                    assert (record['case'],record['master_seed'],record['method'],record['actual_evaluator_calls'])==(case['name'],seed,method,3000)
                    controls.append(record);inputs[str(path.relative_to(ROOT))]=sha
    assert len(controls)==126
    for case in previous['cases']:
        path=source/'instances'/f"{case['name']}.dzn"
        assert digest(path)==case['sha256'];inputs[str(path.relative_to(ROOT))]=case['sha256']
    files=[*sorted((ROOT/'src/mojssp').glob('*.py')),Path(__file__).resolve(),ROOT/'scripts/run_weighted_pilot.py',
           ROOT/'scripts/run_dynamic_pilot.py',ROOT/'scripts/pilot_analysis.py']
    hashes={str(path.relative_to(ROOT)).replace('\\','/'):digest(path) for path in files}
    candidates=[treatment['name'] for treatment in design['treatments']]
    expected_runs=len(previous['cases'])*len(previous['master_seeds'])*len(candidates)
    output.mkdir(parents=True)
    for path in files:
        destination=output/'code'/path.relative_to(ROOT);destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,destination)
    write_json(output/'design.json',design)
    write_json(output/'config.json',dict(split='development',cases=previous['cases'],master_seeds=previous['master_seeds'],
        candidates=candidates,control_methods=control_methods,design_sha256=digest(args.design),
        expected_new_runs=expected_runs,expected_new_search_fe=expected_runs*design['budget'],reused_controls=len(controls),
        source_sha256=hashes,input_sha256=inputs,control_provenance=provenance,
        seed_derivation=previous['seed_derivation'],primary_comparison='Each candidate minus MOEA/D final HV',
        statistical_unit='Six development bases; mean of three seeds first; exploratory comparisons without confirmatory claims',
        timing='Candidate order rotated; saved-control timings are not contemporaneous'))
    original_evaluate=Evaluator.evaluate;started=time.perf_counter();runs=[];allocation_rows=[]
    for case_index,case in enumerate(previous['cases']):
        instance=load_dzn(source/'instances'/f"{case['name']}.dzn")
        normalizer=ObjectiveNormalizer(compute_instance_bounds(instance))
        for seed_index,seed in enumerate(previous['master_seeds']):
            shift=(case_index*len(previous['master_seeds'])+seed_index)%len(candidates)
            order=design['treatments'][shift:]+design['treatments'][:shift]
            for treatment in order:
                assert all(digest(ROOT/name)==sha for name,sha in hashes.items()),'Code changed during campaign'
                shares={name:Fraction(value) for name,value in treatment['shares'].items()} if treatment['policy']=='weighted' else None
                calls=0
                def counted(evaluator,*a,**kw):
                    nonlocal calls
                    calls+=1
                    return original_evaluate(evaluator,*a,**kw)
                try:
                    with patch.object(Evaluator,'evaluate',counted):
                        result,history=run_phase2_portfolio_experiment(instance,seed,total_budget=design['budget'],
                            block_size=design['block_size'],population_size=design['population_size'],policy=treatment['policy'],
                            selected_arms=treatment['arms'],budget_shares=shares,window_size=design['window_size'],
                            exploration_factor=design['exploration_factor'])
                    assert calls==result.evaluations_used==3000 and result.completed
                    allocations={name:value.evaluations_assigned for name,value in result.arm_allocations.items()}
                    assert set(allocations)==set(treatment['arms']) and sum(allocations.values())==3000
                    if shares is not None: assert allocations==evaluation_quotas(3000,shares)
                    hv=compute_hypervolume([normalizer.normalize_tuple(point) for point in result.pareto_front])
                    assert math.isclose(hv,result.hypervolume,abs_tol=1e-12,rel_tol=0)
                    record=asdict(result)
                    record.update(case=case['name'],master_seed=seed,method=treatment['name'],actual_evaluator_calls=calls,
                                  auc_hv=auc(result.checkpoints,3000),blocks=[])
                    for block in history:
                        row=asdict(block)
                        if row['ucb_indices'] is not None:
                            row['ucb_indices']={name:value if math.isfinite(value) else None for name,value in row['ucb_indices'].items()}
                        record['blocks'].append(row)
                    json.dumps(record,allow_nan=False)
                    write_json(output/'runs'/f"{case['name']}__{seed}__{treatment['name']}.json",record)
                except Exception as error:
                    write_json(output/'failure.json',dict(case=case['name'],master_seed=seed,method=treatment['name'],
                        search_fe_in_failed_attempt=calls,error=repr(error),completed_valid_runs=len(runs)))
                    raise
                runs.append(record)
                for name,value in allocations.items(): allocation_rows.append(dict(case=case['name'],master_seed=seed,
                    method=treatment['name'],arm=name,evaluations=value,percent=value/30))
                print(f"{len(runs)}/{expected_runs} {case['name']} seed={seed} {treatment['name']}: HV={hv:.6f} time={result.runtime_seconds:.2f}s elapsed={time.perf_counter()-started:.1f}s",flush=True)
    assert len(runs)==expected_runs and sum(r['actual_evaluator_calls'] for r in runs)==expected_runs*3000
    analyze(output,controls+runs,candidates,control_methods)
    write_csv(output/'allocations.csv',allocation_rows)
    write_json(output/'validation.json',dict(passed=True,new_runs=len(runs),new_search_fe=expected_runs*3000,
        reused_controls=len(controls),all_hv_recomputed=True,all_fixed_quotas_verified=True,
        source_code_unchanged_during_campaign=True,search_wall_seconds=time.perf_counter()-started))
    print('Portfolio campaign complete and validated.',flush=True)


if __name__=='__main__': main()
