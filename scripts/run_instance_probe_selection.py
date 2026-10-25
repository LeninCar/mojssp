"""Select NSGA-II or SPEA2 after short probes, with training-only grouped calibration."""
import argparse
import json
from pathlib import Path
import shutil
import time
from unittest.mock import patch

import numpy as np
from sklearn.tree import DecisionTreeRegressor, export_text
from run_weighted_pilot import ROOT, auc, digest, write_csv, write_json
from run_instance_selection import instance_features, FEATURE_NAMES
from mojssp.arms import NSGA2Arm
from mojssp.evaluator import Evaluator
from mojssp.hypervolume import compute_archive_hypervolume, compute_hypervolume
from mojssp.io import load_dzn
from mojssp.normalization import ObjectiveNormalizer, compute_instance_bounds
from mojssp.portfolio import Portfolio
from mojssp.reward import HypervolumeRewardTracker
from mojssp.spea2 import SPEA2Arm


def probe_features(features,hv_nsga2,hv_spea2):
    return list(features)+[hv_nsga2,hv_spea2,hv_nsga2-hv_spea2]


def choose(rule,model,features):
    value = features[-1] if rule=='greedy' else float(model.predict([features])[0])
    return 'nsga2' if value>=0 else 'spea2'


def calibrate(training,records,features,design):
    models,rows = {},[]
    for probe in design['candidate_probe_fe_per_arm']:
        x,y,groups,values = [],[],[],[]
        for case in training:
            for seed in [42,43,44]:
                a,b = records[case,seed,'nsga2'],records[case,seed,'spea2']
                ca,cb = dict(a['checkpoints']),dict(b['checkpoints'])
                x.append(probe_features(features[case],ca[probe],cb[probe]))
                y.append(ca[3000-probe]-cb[3000-probe])
                values.append([ca[3000-probe],cb[3000-probe]])
                groups.append(case)
        x,y,values = np.array(x),np.array(y),np.array(values)
        for rule in design['candidate_rules']:
            scores = []
            for case in training:
                held = np.array([c==case for c in groups])
                model = None
                if rule!='greedy':
                    model = DecisionTreeRegressor(max_depth=2,min_samples_leaf=6,random_state=20261023)
                    model.fit(x[~held],y[~held])
                case_scores = []
                for i in np.flatnonzero(held):
                    method = choose(rule,model,x[i])
                    case_scores.append(values[i,0 if method=='nsga2' else 1])
                scores.append(float(np.mean(case_scores)))
            rows.append(dict(rule=rule,probe_fe=probe,loo_lower_bound_mean_hv=float(np.mean(scores))))
            if rule!='greedy':
                fitted = DecisionTreeRegressor(max_depth=2,min_samples_leaf=6,random_state=20261023).fit(x,y)
                models[rule,probe] = fitted
    best = max(rows,key=lambda r:r['loo_lower_bound_mean_hv'])
    return best,models.get((best['rule'],best['probe_fe'])),rows


def run_probe(instance,seed,probe,rule,model,budget=3000,population_size=30,block_size=50):
    if probe % block_size or probe<population_size or 2*probe>=budget:
        raise ValueError('Probe must use full blocks and leave a continuation budget')
    arms = {'nsga2':NSGA2Arm(instance,population_size,max_generations=None,seed=(seed*10007+29)%(2**31-1)),
            'spea2':SPEA2Arm(instance,population_size,archive_size=population_size,seed=(seed*10007+43)%(2**31-1))}
    portfolio = Portfolio({arm.arm_name:arm for arm in arms.values()})
    norm = ObjectiveNormalizer(compute_instance_bounds(instance))
    tracker = HypervolumeRewardTracker(norm)
    allocations = dict.fromkeys(arms,0)
    blocks,checkpoints = [],[]
    started = time.perf_counter()
    def execute(method,phase):
        before,hv_before = portfolio.total_evaluations,tracker.current_hv
        result = portfolio.run_arm(arms[method].arm_name,block_size)
        assert result.evaluations_used==block_size
        allocations[method] += result.evaluations_used
        gain = tracker.compute_reward(portfolio.global_archive)
        blocks.append(dict(method=method,phase=phase,fe_before=before,fe_after=portfolio.total_evaluations,
                           hv_before=hv_before,hv_after=tracker.current_hv,gain=gain))
        checkpoints.append([portfolio.total_evaluations,tracker.current_hv])
    for _ in range(probe//block_size):
        for method in arms:
            execute(method,'probe')
    probe_hv = {method:compute_archive_hypervolume(arm.current_archive,norm) for method,arm in arms.items()}
    x = probe_features(instance_features(instance),probe_hv['nsga2'],probe_hv['spea2'])
    selected = choose(rule,model,x)
    while portfolio.total_evaluations<budget:
        execute(selected,'continuation')
    assert allocations[selected]==budget-probe
    assert sum(allocations.values())==budget
    front = [list(entry.objectives) for entry in portfolio.global_archive.entries]
    assert abs(compute_hypervolume([norm.normalize_tuple(p) for p in front])-tracker.current_hv)<1e-12
    return dict(budget=budget,evaluations_used=budget,hypervolume=tracker.current_hv,
                pareto_front=front,blocks=blocks,checkpoints=checkpoints,allocations=allocations,
                selected_method=selected,probe_individual_hv=probe_hv,probe_features=x,
                auc_hv=auc(checkpoints,budget),runtime_seconds=time.perf_counter()-started,completed=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    args = parser.parse_args()
    source,output = args.source.resolve(),args.output_dir.resolve()
    if output.exists() or not output.is_relative_to(ROOT/'results/experiments'):
        parser.error('Choose a new output inside results/experiments')
    config = json.loads((source/'config.json').read_text(encoding='utf-8'))
    design_path = ROOT/'configs/experiments/instance_probe_selection.json'
    design = json.loads(design_path.read_text())
    training = [c['name'] for c in config['cases'] if c['split']=='training']
    evaluation = [c['name'] for c in config['cases'] if c['split']=='evaluation']
    assert len(training)==18 and len(evaluation)==13
    records,features,inputs = {},{},{}
    for case in config['cases']:
        path = source/'instances'/f"{case['name']}.dzn"
        assert digest(path)==case['sha256']
        features[case['name']] = instance_features(load_dzn(path))
        inputs[str(path.relative_to(ROOT))] = digest(path)
    for case in training:
        for seed in config['seeds']:
            for method in ['nsga2','spea2']:
                path = source/'runs'/f'{case}__{seed}__{method}.json'
                records[case,seed,method] = json.loads(path.read_text(encoding='utf-8'))
                inputs[str(path.relative_to(ROOT))] = digest(path)
    best,model,cv = calibrate(training,records,features,design)
    output.mkdir(parents=True)
    files = [*sorted((ROOT/'src/mojssp').glob('*.py')),Path(__file__).resolve(),ROOT/'scripts/run_instance_selection.py',
             ROOT/'scripts/run_weighted_pilot.py',ROOT/'scripts/run_dynamic_pilot.py',design_path]
    hashes = {str(path.relative_to(ROOT)):digest(path) for path in files}
    for path in files:
        target = output/'code'/path.relative_to(ROOT)
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,target)
    for case in evaluation:
        target = output/'instances'/f'{case}.dzn'
        target.parent.mkdir(exist_ok=True)
        shutil.copy2(source/'instances'/target.name,target)
    rules = best['rule'] if model is None else export_text(model,feature_names=FEATURE_NAMES+['probe_hv_nsga2','probe_hv_spea2','probe_hv_delta'],decimals=8)
    write_json(output/'frozen_policy.json',dict(selected=best,cross_validation=cv,rules=rules,
        training_cases=training,evaluation_cases=evaluation,design=design,source_sha256=hashes,input_sha256=inputs,
        selection_criterion='Training-only lower bound: selected solver archive HV at B-probe; evaluation global archive can add probe solutions'))
    policy_sha = digest(output/'frozen_policy.json')
    print('FROZEN PROBE POLICY: '+json.dumps(best),flush=True)
    runs = []
    original = Evaluator.evaluate
    for case in evaluation:
        instance = load_dzn(output/'instances'/f'{case}.dzn')
        for seed in config['seeds']:
            assert digest(output/'frozen_policy.json')==policy_sha
            assert all(digest(ROOT/path)==sha for path,sha in hashes.items())
            calls = 0
            def counted(self,*a,**kw):
                nonlocal calls
                calls += 1
                return original(self,*a,**kw)
            try:
                with patch.object(Evaluator,'evaluate',counted):
                    r = run_probe(instance,seed,best['probe_fe'],best['rule'],model)
                assert calls==r['evaluations_used']==3000
                r.update(case=case,master_seed=seed,method='probe_selection',actual_evaluator_calls=calls)
                write_json(output/'runs'/f'{case}__{seed}__probe_selection.json',r)
            except Exception as error:
                write_json(output/'failure.json',dict(case=case,seed=seed,error=repr(error),actual_evaluator_calls=calls))
                raise
            runs.append(r)
            print(f"{len(runs)}/39 {case} seed={seed} selected={r['selected_method']} HV={r['hypervolume']:.6f}",flush=True)
    write_csv(output/'runs.csv',[dict(case=r['case'],seed=r['master_seed'],selected=r['selected_method'],
                                    hypervolume=r['hypervolume'],auc_hv=r['auc_hv']) for r in runs])
    write_json(output/'search_validation.json',dict(new_runs=39,new_search_fe=sum(r['actual_evaluator_calls'] for r in runs),
        frozen_policy_sha256=policy_sha,all_budgets_exact=True,moead_search_fe=0))
    write_json(output/'artifact_manifest.json',{str(p.relative_to(output)):digest(p)
        for p in sorted(output.rglob('*')) if p.is_file() and p.name!='artifact_manifest.json'})


if __name__=='__main__':
    main()
