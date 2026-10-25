"""Test an NSGA-II + SPEA2 policy against verified saved controls."""
import argparse
import ast
from collections import defaultdict
from dataclasses import asdict
import json
import math
from pathlib import Path
import shutil
import time
from unittest.mock import patch

from run_weighted_pilot import ROOT, auc, digest, write_csv, write_json
import numpy as np
from mojssp.evaluator import Evaluator
from mojssp.hypervolume import compute_hypervolume
from mojssp.io import load_dzn
from mojssp.normalization import ObjectiveNormalizer, compute_instance_bounds
from mojssp.project_paths import HISTORICAL_ROOT
from mojssp.runner import run_phase2_portfolio_experiment

CONTROLS = ['moead', 'nsga2', 'spea2']


def verify_control_compatibility(source, config):
    changed = [name for name,sha in config['source_sha256'].items() if digest(ROOT/name) != sha]
    if changed != ['src/mojssp/runner.py']:
        raise ValueError(f'Unexpected implementation differences: {changed}')
    old = ast.parse((source/'code/src/mojssp/runner.py').read_text(encoding='utf-8'))
    new = ast.parse((ROOT/'src/mojssp/runner.py').read_text(encoding='utf-8'))
    for name in ['run_standalone_experiment', 'RunResult', 'ArmAllocation']:
        a = next(node for node in old.body if getattr(node, 'name', None) == name)
        b = next(node for node in new.body if getattr(node, 'name', None) == name)
        assert ast.dump(a) == ast.dump(b), f'Individual control changed: {name}'
    return dict(changed_module=changed, standalone_function_and_result_contract_unchanged=True,
                all_other_original_modules_identical=True,
                timing_limitation='Individual timings were measured in the earlier pilot; quality comparisons reuse identical inputs and implementation')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--controls', type=Path, required=True)
    parser.add_argument('--policy', choices=['uniform','scaled'], default='uniform')
    parser.add_argument('--pair-control', type=Path, help='Optional saved uniform-pair pilot')
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    source, output = args.controls.resolve(), args.output_dir.resolve()
    pair_method = 'nsga2_spea2_' + args.policy
    control_methods = list(CONTROLS)
    if output.exists() or output.is_relative_to(HISTORICAL_ROOT):
        parser.error('Choose a new output directory outside historical results')
    original_config = json.loads((source/'config.json').read_text(encoding='utf-8'))
    assert original_config['split'] == 'development' and original_config['budget'] == 3000
    assert original_config['population_size'] == 30 and original_config['block_size'] == 50
    provenance = verify_control_compatibility(source, original_config)
    original_hashes = json.loads((source/'artifact_manifest.json').read_text(encoding='utf-8'))
    controls, input_hashes = [], {}
    for case in original_config['cases']:
        instance_file = source/'instances'/f"{case['name']}.dzn"
        assert digest(instance_file) == case['sha256']
        input_hashes[str(instance_file.relative_to(ROOT))] = case['sha256']
        for seed in original_config['master_seeds']:
            for method in CONTROLS:
                path = source/'runs'/f"{case['name']}__{seed}__{method}.json"
                assert digest(path) == original_hashes[str(path.relative_to(source)).replace('\\','/')]
                record = json.loads(path.read_text(encoding='utf-8'))
                assert (record['case'], record['master_seed'], record['method'], record['actual_evaluator_calls']) == (case['name'], seed, method, 3000)
                controls.append(record)
                input_hashes[str(path.relative_to(ROOT))] = digest(path)
    assert len(controls) == 54
    if args.pair_control is not None:
        pair_source = args.pair_control.resolve()
        prior = json.loads((pair_source/'config.json').read_text(encoding='utf-8'))
        assert prior['policy'] == 'uniform' and prior['selected_arms'] == ['NSGA-II','SPEA2']
        assert prior['budget'] == 3000 and prior['population_size'] == 30 and prior['block_size'] == 50
        assert prior['cases'] == original_config['cases'] and prior['master_seeds'] == original_config['master_seeds']
        assert all(digest(ROOT/name) == sha for name,sha in prior['source_sha256'].items()
                   if name.startswith('src/'))
        prior_manifest = json.loads((pair_source/'artifact_manifest.json').read_text(encoding='utf-8'))
        uniform_method = 'nsga2_spea2_uniform'
        assert pair_method != uniform_method
        for path in sorted((pair_source/'runs').glob('*.json')):
            assert digest(path) == prior_manifest[str(path.relative_to(pair_source)).replace('\\','/')]
            record = json.loads(path.read_text(encoding='utf-8'))
            assert record['method'] == uniform_method and record['actual_evaluator_calls'] == 3000
            controls.append(record)
            input_hashes[str(path.relative_to(ROOT))] = digest(path)
        assert len(controls) == 72
        control_methods.append(uniform_method)
    source_files = [*sorted((ROOT/'src/mojssp').glob('*.py')), Path(__file__).resolve(), ROOT/'scripts/run_weighted_pilot.py']
    hashes = {str(path.relative_to(ROOT)).replace('\\','/'):digest(path) for path in source_files}
    output.mkdir(parents=True)
    for path in source_files:
        target = output/'code'/path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    write_json(output/'config.json', dict(split='development', cases=original_config['cases'],
        master_seeds=original_config['master_seeds'], methods=control_methods+[pair_method], selected_arms=['NSGA-II','SPEA2'],
        policy=args.policy, budget=3000, quotas={'NSGA-II':1500,'SPEA2':1500} if args.policy=='uniform' else None, population_size=30,
        block_size=50, expected_new_runs=18, expected_new_search_fe=54000, reused_controls=len(controls),
        control_provenance=provenance, input_sha256=input_hashes, source_sha256=hashes,
        seed_derivation=original_config['seed_derivation'],
        primary_comparison='Pair minus MOEA/D final HV; comparisons with NSGA-II and SPEA2 secondary',
        timing='Reused control timings are descriptive, not a contemporaneous runtime comparison'))
    original_evaluate = Evaluator.evaluate
    runs = []
    started = time.perf_counter()
    for case in original_config['cases']:
        instance = load_dzn(source/'instances'/f"{case['name']}.dzn")
        normalizer = ObjectiveNormalizer(compute_instance_bounds(instance))
        for seed in original_config['master_seeds']:
            assert all(digest(ROOT/name) == sha for name,sha in hashes.items())
            calls = 0
            def counted(evaluator, *a, **kw):
                nonlocal calls
                calls += 1
                return original_evaluate(evaluator, *a, **kw)
            with patch.object(Evaluator, 'evaluate', counted):
                result, history = run_phase2_portfolio_experiment(instance, seed,
                    total_budget=3000, block_size=50, population_size=30, policy=args.policy,
                    selected_arms=['NSGA-II','SPEA2'])
            assert calls == result.evaluations_used == 3000 and result.completed
            actual = {name:value.evaluations_assigned for name,value in result.arm_allocations.items()}
            assert set(actual) == {'NSGA-II','SPEA2'} and sum(actual.values()) == 3000
            if args.policy == 'uniform':
                assert actual == {'NSGA-II':1500,'SPEA2':1500}
            hv = compute_hypervolume([normalizer.normalize_tuple(point) for point in result.pareto_front])
            assert math.isclose(hv, result.hypervolume, abs_tol=1e-12, rel_tol=0)
            record = asdict(result)
            record.update(case=case['name'], master_seed=seed, method=pair_method,
                          actual_evaluator_calls=calls, auc_hv=auc(result.checkpoints,3000),
                          blocks=[])
            for block in history:
                row = asdict(block)
                if row['ucb_indices'] is not None:
                    row['ucb_indices'] = {name:value if math.isfinite(value) else None
                                          for name,value in row['ucb_indices'].items()}
                record['blocks'].append(row)
            write_json(output/'runs'/f"{case['name']}__{seed}__{pair_method}.json",record)
            runs.append(record)
            print(f"{len(runs)}/18 {case['name']} seed={seed}: HV={hv:.6f} time={result.runtime_seconds:.2f}s elapsed={time.perf_counter()-started:.1f}s",flush=True)
    rows = [{key:record[key] for key in ['case','master_seed','method','hypervolume','auc_hv','runtime_seconds']}
            for record in controls+runs]
    write_csv(output/'runs.csv',rows)
    cells = defaultdict(list)
    for row in rows:
        cells[row['case'],row['method']].append(row)
    by_instance = [dict(case=case,method=method,
        **{f'mean_{key}':float(np.mean([r[key] for r in records])) for key in ['hypervolume','auc_hv','runtime_seconds']})
        for (case,method),records in sorted(cells.items())]
    write_csv(output/'by_instance.csv',by_instance)
    summary = [dict(method=method,**{key:float(np.mean([r[key] for r in by_instance if r['method']==method]))
        for key in ['mean_hypervolume','mean_auc_hv','mean_runtime_seconds']}) for method in control_methods+[pair_method]]
    write_csv(output/'summary.csv',summary)
    index = {(r['case'],r['method']):r for r in by_instance}
    rng = np.random.default_rng(20261023)
    comparisons = []
    for control in control_methods:
        for metric in ['hypervolume','auc_hv']:
            delta = np.array([index[case['name'],pair_method][f'mean_{metric}']-index[case['name'],control][f'mean_{metric}']
                              for case in original_config['cases']])
            lo,hi = np.quantile(rng.choice(delta,size=(20000,6)).mean(axis=1),[.025,.975])
            comparisons.append(dict(control=control,metric=metric,mean_difference=float(delta.mean()),
                bootstrap95_low=float(lo),bootstrap95_high=float(hi),positive_bases=int(sum(delta>1e-12)),
                tied_bases=int(sum(abs(delta)<=1e-12)),negative_bases=int(sum(delta<-1e-12))))
    write_csv(output/'comparisons.csv',comparisons)
    assert len(runs)==18 and sum(r['actual_evaluator_calls'] for r in runs)==54000
    write_json(output/'validation.json',dict(passed=True,new_runs=18,new_search_fe=54000,
        reused_controls=len(controls),all_allocations_verified=True,all_new_hv_recomputed=True,
        control_compatibility=provenance,statistical_unit='Six development bases; mean of three seeds first',
        search_wall_seconds=time.perf_counter()-started))
    print('Pair pilot complete and validated.',flush=True)


if __name__ == '__main__':
    main()
