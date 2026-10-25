"""Development pilot of explicit round-wise budget redistribution."""
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
from pilot_analysis import analyze_candidate
from mojssp.dynamic_budget import round_shares
from mojssp.evaluator import Evaluator
from mojssp.fixed_budget import evaluation_quotas
from mojssp.hypervolume import compute_hypervolume
from mojssp.io import load_dzn
from mojssp.normalization import ObjectiveNormalizer, compute_instance_bounds
from mojssp.project_paths import HISTORICAL_ROOT
from mojssp.runner import run_phase2_portfolio_experiment


def compatible_controls(source, config):
    changed = [name for name,sha in config['source_sha256'].items() if digest(ROOT/name)!=sha]
    assert set(changed)=={'src/mojssp/runner.py','src/mojssp/orchestrator.py'}, changed
    old = ast.parse((source/'code/src/mojssp/runner.py').read_text(encoding='utf-8'))
    new = ast.parse((ROOT/'src/mojssp/runner.py').read_text(encoding='utf-8'))
    for name in ['run_standalone_experiment','RunResult','ArmAllocation']:
        a = next(n for n in old.body if getattr(n,'name',None)==name)
        b = next(n for n in new.body if getattr(n,'name',None)==name)
        assert ast.dump(a)==ast.dump(b),name
    old = ast.parse((source/'code/src/mojssp/orchestrator.py').read_text(encoding='utf-8'))
    new = ast.parse((ROOT/'src/mojssp/orchestrator.py').read_text(encoding='utf-8'))
    a = next(n for n in old.body if getattr(n,'name',None)=='AdaptivePortfolioOrchestrator')
    b = next(n for n in new.body if getattr(n,'name',None)=='AdaptivePortfolioOrchestrator')
    methods = {n.name:n for n in b.body if isinstance(n,ast.FunctionDef)}
    for method in a.body:
        if isinstance(method,ast.FunctionDef): assert ast.dump(method)==ast.dump(methods[method.name]),method.name
    return dict(changed_modules=changed,individual_execution_and_contract_unchanged=True,
                existing_orchestrator_methods_unchanged=True,other_original_modules_identical=True,
                new_telemetry='Optional round_index field; existing policies unchanged')


def round_table(record):
    groups = defaultdict(list)
    for block in record['blocks']: groups[block['round_index']].append(block)
    names = ['MOEA/D','NSGA-II','SPEA2']
    shares = dict.fromkeys(names,1/3)
    rows = []
    assert len(groups)==10
    for index,blocks in sorted(groups.items()):
        order = names[index%3:]+names[:index%3]
        expected = evaluation_quotas(300,{name:shares[name] for name in order})
        scores = {}
        for name in names:
            own = [b for b in blocks if b['arm_name']==name]
            scored = [b for b in own if b['phase']!='warmup']
            used = sum(b['evaluations_used'] for b in own)
            fe = sum(b['evaluations_used'] for b in scored)
            gain = sum(b['reward'] for b in scored)
            assert used==expected[name]
            scores[name] = gain/fe if fe else 0.
            rows.append(dict(case=record['case'],master_seed=record['master_seed'],round_index=index,
                arm=name,prior_share=shares[name],evaluations=used,scored_fe=fe,gain=gain,gain_per_fe=scores[name]))
        shares = round_shares(scores,.1)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--controls',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    args = parser.parse_args()
    source,output = args.controls.resolve(),args.output_dir.resolve()
    if output.exists() or output.is_relative_to(HISTORICAL_ROOT): parser.error('Choose a new output outside historical results')
    previous = json.loads((source/'config.json').read_text(encoding='utf-8'))
    assert previous['split']=='development' and previous['budget']==3000
    provenance = compatible_controls(source,previous)
    original_hashes = json.loads((source/'artifact_manifest.json').read_text(encoding='utf-8'))
    control_methods = previous['methods']
    controls,inputs = [],{}
    for case in previous['cases']:
        instance_file = source/'instances'/f"{case['name']}.dzn"
        assert digest(instance_file)==case['sha256']
        inputs[str(instance_file.relative_to(ROOT))]=case['sha256']
        for seed in previous['master_seeds']:
            for method in control_methods:
                path = source/'runs'/f"{case['name']}__{seed}__{method}.json"
                sha = digest(path)
                assert sha==original_hashes[str(path.relative_to(source)).replace('\\','/')]
                controls.append(json.loads(path.read_text(encoding='utf-8')))
                inputs[str(path.relative_to(ROOT))]=sha
    assert len(controls)==108
    files = [*sorted((ROOT/'src/mojssp').glob('*.py')),Path(__file__).resolve(),
             ROOT/'scripts/pilot_analysis.py',ROOT/'scripts/run_weighted_pilot.py']
    hashes = {str(path.relative_to(ROOT)).replace('\\','/'):digest(path) for path in files}
    output.mkdir(parents=True)
    for path in files:
        target = output/'code'/path.relative_to(ROOT)
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,target)
    write_json(output/'config.json',dict(split='development',cases=previous['cases'],master_seeds=previous['master_seeds'],
        methods=control_methods+['dynamic'],budget=3000,round_size=300,block_size=50,population_size=30,
        minimum_share=.1,initial_round='Uniform, 100 evaluations per algorithm',
        scoring='Previous-round global delta HV per scored evaluation; first 50 FE per arm excluded from scoring but counted in budget',
        redistribution='10% reserved per arm; remaining 70% proportional to gain per FE; all-zero scores use uniform shares',
        rounding='Largest remainders; stable rotated arm order breaks ties',
        scheduling='Rotate arm order each round; serve least completed quota proportion in blocks of at most 50 FE',
        expected_new_runs=18,expected_new_search_fe=54000,reused_controls=108,
        control_provenance=provenance,source_sha256=hashes,input_sha256=inputs,
        seed_derivation=previous['seed_derivation'],primary_comparison='Dynamic minus MOEA/D final HV',
        statistical_unit='Six development bases; average three seeds first',
        timing='Saved controls were measured earlier; runtime comparison is descriptive'))
    runs,rounds = [],[]
    original_evaluate = Evaluator.evaluate
    started = time.perf_counter()
    for case in previous['cases']:
        instance = load_dzn(source/'instances'/f"{case['name']}.dzn")
        normalizer = ObjectiveNormalizer(compute_instance_bounds(instance))
        for seed in previous['master_seeds']:
            assert all(digest(ROOT/name)==sha for name,sha in hashes.items())
            calls = 0
            def counted(evaluator,*a,**kw):
                nonlocal calls
                calls+=1
                return original_evaluate(evaluator,*a,**kw)
            with patch.object(Evaluator,'evaluate',counted):
                result,history = run_phase2_portfolio_experiment(instance,seed,total_budget=3000,
                    block_size=50,population_size=30,policy='dynamic',round_size=300,minimum_share=.1)
            assert calls==result.evaluations_used==3000 and result.completed
            hv = compute_hypervolume([normalizer.normalize_tuple(p) for p in result.pareto_front])
            assert math.isclose(hv,result.hypervolume,abs_tol=1e-12,rel_tol=0)
            record = asdict(result)
            record.update(case=case['name'],master_seed=seed,method='dynamic',actual_evaluator_calls=calls,
                          auc_hv=auc(result.checkpoints,3000),blocks=[asdict(block) for block in history])
            rounds.extend(round_table(record))
            write_json(output/'runs'/f"{case['name']}__{seed}__dynamic.json",record)
            runs.append(record)
            print(f"{len(runs)}/18 {case['name']} seed={seed}: HV={hv:.6f} time={result.runtime_seconds:.2f}s elapsed={time.perf_counter()-started:.1f}s",flush=True)
    assert len(runs)==18 and sum(r['actual_evaluator_calls'] for r in runs)==54000
    analyze_candidate(output,controls+runs,'dynamic',control_methods)
    write_csv(output/'rounds.csv',rounds)
    write_json(output/'validation.json',dict(passed=True,new_runs=18,new_search_fe=54000,
        reused_controls=108,all_new_hv_recomputed=True,all_round_quotas_recomputed=True,
        initialization_excluded_from_scoring=True,control_compatibility=provenance,
        search_wall_seconds=time.perf_counter()-started))
    print('Dynamic pilot complete and validated.',flush=True)


if __name__=='__main__': main()
