"""Evaluate MOEA/D with short, stateful SPEA2 interventions on development cases."""
import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import shutil
import time
from unittest.mock import patch

import numpy as np
from run_weighted_pilot import ROOT, auc, digest, write_csv, write_json
from run_portfolio_campaign import analyze
from run_dynamic_pilot import compatible_controls
from mojssp.evaluator import Evaluator
from mojssp.hypervolume import compute_hypervolume
from mojssp.io import load_dzn
from mojssp.moead import MOEADArm
from mojssp.normalization import ObjectiveNormalizer, compute_instance_bounds
from mojssp.portfolio import Portfolio
from mojssp.reward import HypervolumeRewardTracker
from mojssp.spea2 import SPEA2Arm


def run_intervention(instance, seed, epsilon, budget=3000, block_size=50, population_size=30, k=2):
    if not math.isfinite(epsilon) or epsilon < 0 or k < 1:
        raise ValueError('Expected finite nonnegative epsilon and positive k')
    if budget < population_size or block_size < population_size or budget % block_size:
        raise ValueError('Use full blocks sufficient to initialize a population')
    norm = ObjectiveNormalizer(compute_instance_bounds(instance))
    portfolio = Portfolio({
        'MOEA/D': MOEADArm(instance, population_size, seed=(seed * 10007 + 17) % (2**31 - 1)),
        'SPEA2': SPEA2Arm(instance, population_size, archive_size=population_size,
                          seed=(seed * 10007 + 43) % (2**31 - 1))})
    tracker = HypervolumeRewardTracker(norm)
    blocks, checkpoints = [], []
    allocations = {'MOEA/D': 0, 'SPEA2': 0}
    streak, rescue, interventions = 0, False, 0
    started = time.perf_counter()
    while portfolio.total_evaluations < budget:
        name = 'SPEA2' if rescue else 'MOEA/D'
        before, hv_before, streak_before = portfolio.total_evaluations, tracker.current_hv, streak
        result = portfolio.run_arm(name, block_size)
        assert result.evaluations_used == block_size
        gain = tracker.compute_reward(portfolio.global_archive)
        allocations[name] += result.evaluations_used
        if rescue:
            interventions += 1
            streak, rescue = 0, False
        else:
            streak = streak + 1 if gain < epsilon else 0
            rescue = streak >= k
        blocks.append(dict(arm=name,fe_before=before,fe_after=portfolio.total_evaluations,
                           hv_before=hv_before,hv_after=tracker.current_hv,gain=gain,
                           streak_before=streak_before,streak_after=streak,
                           rescue_next=rescue and portfolio.total_evaluations < budget))
        checkpoints.append([portfolio.total_evaluations,tracker.current_hv])
    front = [list(entry.objectives) for entry in portfolio.global_archive.entries]
    assert abs(compute_hypervolume([norm.normalize_tuple(p) for p in front])-tracker.current_hv) < 1e-12
    return dict(seed=seed,budget=budget,evaluations_used=portfolio.total_evaluations,
                hypervolume=tracker.current_hv,pareto_front=front,checkpoints=checkpoints,
                blocks=blocks,allocations=allocations,interventions=interventions,
                epsilon=epsilon,k=k,runtime_seconds=time.perf_counter()-started,
                auc_hv=auc(checkpoints,budget),completed=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if output.exists() or not output.is_relative_to(ROOT/'results/experiments'):
        parser.error('Choose a new directory inside results/experiments')
    source = ROOT/'results/experiments/weighted_pilot_development_20261023'
    reference = ROOT/'results/experiments/dynamic_rounds_development_20261023'
    previous = json.loads((source/'config.json').read_text(encoding='utf-8'))
    latest = json.loads((reference/'config.json').read_text(encoding='utf-8'))
    assert all(digest(ROOT/name)==sha for name,sha in latest['source_sha256'].items() if name.startswith('src/'))
    provenance = compatible_controls(source,previous)
    manifest = json.loads((source/'artifact_manifest.json').read_text(encoding='utf-8'))
    controls,inputs = [],{}
    for case in previous['cases']:
        path = source/'instances'/f"{case['name']}.dzn"
        assert digest(path)==case['sha256']
        inputs[str(path.relative_to(ROOT))] = digest(path)
        for seed in previous['master_seeds']:
            path = source/'runs'/f"{case['name']}__{seed}__moead.json"
            assert digest(path)==manifest[str(path.relative_to(source)).replace('\\','/')]
            controls.append(json.loads(path.read_text(encoding='utf-8')))
            inputs[str(path.relative_to(ROOT))] = digest(path)
    files = [*sorted((ROOT/'src/mojssp').glob('*.py')),Path(__file__).resolve(),
             ROOT/'scripts/run_weighted_pilot.py',ROOT/'scripts/run_portfolio_campaign.py',ROOT/'scripts/run_dynamic_pilot.py']
    hashes = {str(p.relative_to(ROOT)):digest(p) for p in files}
    treatments = [('stagnation_e0001',.0001),('stagnation_e0002',.0002),('stagnation_e0005',.0005)]
    output.mkdir(parents=True)
    for path in files:
        destination = output/'code'/path.relative_to(ROOT)
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,destination)
    for case in previous['cases']:
        destination = output/'instances'/f"{case['name']}.dzn"
        destination.parent.mkdir(exist_ok=True)
        shutil.copy2(source/'instances'/destination.name,destination)
    write_json(output/'config.json',dict(cases=previous['cases'],seeds=previous['master_seeds'],
        treatments=treatments,budget=3000,block_size=50,population_size=30,k=2,
        detection='Absolute normalized global HV gain strictly below epsilon on two consecutive MOEA/D blocks',
        rescue='One SPEA2 block, reset streak, return to MOEA/D; preserve both solver states',
        initialization='SPEA2 initializes only on first rescue; its full 50 FE count against total budget',
        cooperation='Passive archive union; no external parents or injection',
        source_sha256=hashes,input_sha256=inputs,control_provenance=provenance,
        scope='Six development cases, three seeds; no confirmation instances',
        timing='Saved controls are not contemporaneous; timing is descriptive'))
    records,allocation_rows = [],[]
    original = Evaluator.evaluate
    for ci,case in enumerate(previous['cases']):
        instance = load_dzn(output/'instances'/f"{case['name']}.dzn")
        for si,seed in enumerate(previous['master_seeds']):
            shift = (ci*3+si)%3
            for method,epsilon in treatments[shift:]+treatments[:shift]:
                assert all(digest(ROOT/p)==sha for p,sha in hashes.items())
                calls = 0
                def counted(self,*a,**kw):
                    nonlocal calls
                    calls += 1
                    return original(self,*a,**kw)
                try:
                    with patch.object(Evaluator,'evaluate',counted):
                        record = run_intervention(instance,seed,epsilon)
                    assert calls==record['evaluations_used']==3000
                    record.update(case=case['name'],instance=case['name'],master_seed=seed,
                                  method=method,actual_evaluator_calls=calls)
                    write_json(output/'runs'/f"{case['name']}__{seed}__{method}.json",record)
                except Exception as error:
                    write_json(output/'failure.json',dict(case=case['name'],seed=seed,method=method,
                        actual_evaluator_calls=calls,error=repr(error)))
                    raise
                records.append(record)
                allocation_rows.append(dict(case=case['name'],seed=seed,method=method,
                    interventions=record['interventions'],moead_fe=record['allocations']['MOEA/D'],
                    spea2_fe=record['allocations']['SPEA2'],moead_percent=record['allocations']['MOEA/D']/30))
                print(f"{len(records)}/54 {case['name']} seed={seed} {method} HV={record['hypervolume']:.6f} rescues={record['interventions']} MOEA={record['allocations']['MOEA/D']/30:.2f}%",flush=True)
    analyze(output,controls+records,[name for name,_ in treatments],['moead'])
    write_csv(output/'allocations.csv',allocation_rows)
    totals = []
    for method,epsilon in treatments:
        group = [r for r in allocation_rows if r['method']==method]
        totals.append(dict(method=method,epsilon=epsilon,
            mean_interventions=float(np.mean([r['interventions'] for r in group])),
            mean_moead_percent=float(np.mean([r['moead_percent'] for r in group]))))
    write_csv(output/'allocation_summary.csv',totals)
    write_json(output/'validation.json',dict(new_runs=len(records),new_search_fe=sum(r['actual_evaluator_calls'] for r in records),
        all_budgets_exact=True,all_final_hv_recomputed=True,reused_moead_controls=len(controls)))
    write_json(output/'artifact_manifest.json',{str(p.relative_to(output)):digest(p)
        for p in sorted(output.rglob('*')) if p.is_file() and p.name!='artifact_manifest.json'})


if __name__=='__main__':
    main()
