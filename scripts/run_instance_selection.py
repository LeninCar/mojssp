"""Train and evaluate a small instance-based NSGA-II/SPEA2 portfolio."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import shutil
import time
from unittest.mock import patch

import numpy as np
import sklearn
from sklearn.tree import DecisionTreeRegressor, export_text

from run_weighted_pilot import ROOT, auc, digest, write_csv, write_json
from run_dynamic_pilot import compatible_controls
from mojssp.evaluator import Evaluator
from mojssp.hypervolume import compute_hypervolume
from mojssp.io import load_dzn
from mojssp.normalization import ObjectiveNormalizer, compute_instance_bounds
from mojssp.runner import run_standalone_experiment

METHODS = {'nsga2':('NSGA-II',29),'spea2':('SPEA2',43)}
FEATURE_NAMES = ['jobs','machines','operations','jobs_per_machine','duration_cv',
                 'machine_load_cv','due_date_ratio','release_ratio','energy_mode_ratio']
MODELS = ['constant_best','tree_depth1','tree_depth2']


def instance_features(instance):
    durations = [op.modes[len(op.modes)//2].duration for op in instance.all_operations]
    loads = [sum(op.modes[len(op.modes)//2].duration for op in instance.get_operations_for_machine(i))
             for i in range(instance.num_machines)]
    job_ratios = [job.due_date/sum(op.modes[len(op.modes)//2].duration for op in job.operations)
                  for job in instance.jobs]
    values = [instance.num_jobs,instance.num_machines,instance.total_operations,
              instance.num_jobs/instance.num_machines,float(np.std(durations)/np.mean(durations)),
              float(np.std(loads)/np.mean(loads)),float(np.mean(job_ratios)),
              max(op.release_date for op in instance.all_operations)/sum(durations),
              float(np.mean([max(m.energy for m in op.modes)/max(1,min(m.energy for m in op.modes))
                             for op in instance.all_operations]))]
    assert np.isfinite(values).all()
    return values


def fit_model(name, x, performances):
    if name=='constant_best':
        return 'nsga2' if performances[:,0].mean()>=performances[:,1].mean() else 'spea2'
    model = DecisionTreeRegressor(max_depth=int(name[-1]),min_samples_leaf=3,random_state=20261023)
    model.fit(x,performances[:,0]-performances[:,1])
    return model


def predict_model(model, x):
    if isinstance(model,str):
        return [model]*len(x)
    return ['nsga2' if value>=0 else 'spea2' for value in model.predict(x)]


def freeze_selection(training, x_train, performances, evaluation, x_test):
    scores = []
    for name in MODELS:
        values = []
        for held in range(len(training)):
            indices = [i for i in range(len(training)) if i!=held]
            model = fit_model(name,x_train[indices],performances[indices])
            method = predict_model(model,x_train[held:held+1])[0]
            values.append(float(performances[held,0 if method=='nsga2' else 1]))
        scores.append(dict(model=name,loo_mean_hv=float(np.mean(values))))
    primary = max(scores,key=lambda row:row['loo_mean_hv'])['model']
    models = {name:fit_model(name,x_train,performances) for name in MODELS}
    plans = {name:dict(zip(evaluation,predict_model(model,x_test))) for name,model in models.items()}
    rules = {name:(model if isinstance(model,str) else export_text(model,feature_names=FEATURE_NAMES,decimals=8))
             for name,model in models.items()}
    return dict(primary_model=primary,cross_validation=scores,plans=plans,rules=rules,
                training_cases=training,evaluation_cases=evaluation,
                rule='Tree leaf predicts NSGA-II minus SPEA2 mean HV; choose NSGA-II if nonnegative, SPEA2 otherwise',
                fitting='Leave-one-instance-out model selection on training instances only; one algorithm per instance for all seeds')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if output.exists() or not output.is_relative_to(ROOT/'results/experiments'):
        parser.error('Choose a new output inside results/experiments')
    source = ROOT/'results/experiments/weighted_pilot_development_20261023'
    previous = json.loads((source/'config.json').read_text(encoding='utf-8'))
    provenance = compatible_controls(source,previous)
    manifest = json.loads((source/'artifact_manifest.json').read_text(encoding='utf-8'))
    cases,records,inputs = [],[],{}
    for case in previous['cases']:
        path = source/'instances'/f"{case['name']}.dzn"
        assert digest(path)==case['sha256']
        cases.append(dict(name=case['name'],split='training',path=path,reused=True))
        inputs[str(path.relative_to(ROOT))] = digest(path)
        for seed in previous['master_seeds']:
            for method in METHODS:
                path = source/'runs'/f"{case['name']}__{seed}__{method}.json"
                assert digest(path)==manifest[str(path.relative_to(source)).replace('\\','/')]
                records.append(json.loads(path.read_text(encoding='utf-8')))
                inputs[str(path.relative_to(ROOT))] = digest(path)
    for split,folders in [('training',['factors']),('evaluation',['base','interactions'])]:
        for folder in folders:
            for path in sorted((ROOT/'data/generated/f86_3'/folder).glob('*.dzn')):
                cases.append(dict(name=path.stem,split=split,path=path,reused=False))
                inputs[str(path.relative_to(ROOT))] = digest(path)
    assert len(cases)==31 and len({c['name'] for c in cases})==31
    assert len({digest(c['path']) for c in cases})==31,'Duplicate instance bytes across splits'
    files = [*sorted((ROOT/'src/mojssp').glob('*.py')),Path(__file__).resolve(),
             ROOT/'scripts/run_weighted_pilot.py',ROOT/'scripts/run_dynamic_pilot.py']
    hashes = {str(path.relative_to(ROOT)):digest(path) for path in files}
    output.mkdir(parents=True)
    for path in files:
        destination = output/'code'/path.relative_to(ROOT)
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,destination)
    features,feature_rows = {},[]
    for case in cases:
        destination = output/'instances'/f"{case['name']}.dzn"
        destination.parent.mkdir(exist_ok=True)
        shutil.copy2(case['path'],destination)
        features[case['name']] = instance_features(load_dzn(destination))
        feature_rows.append(dict(case=case['name'],split=case['split'],**dict(zip(FEATURE_NAMES,features[case['name']]))))
    write_csv(output/'features.csv',feature_rows)
    write_json(output/'config.json',dict(cases=[dict(name=c['name'],split=c['split'],sha256=digest(c['path']),reused=c['reused']) for c in cases],
        seeds=previous['master_seeds'],budget=3000,block_size=50,population_size=30,methods=METHODS,
        feature_names=FEATURE_NAMES,candidate_models=MODELS,tree_min_samples_leaf=3,
        primary_rule='Highest leave-one-instance-out mean HV on training cases; stable model order breaks ties',
        evaluation_rule='Freeze all routes before evaluation solver runs; compare primary against both individuals',
        expected_new_runs=150,expected_search_fe=450000,reused_individual_runs=36,
        source_sha256=hashes,input_sha256=inputs,control_provenance=provenance,
        sklearn_version=sklearn.__version__,numpy_version=np.__version__,
        deployment_budget='3000 FE of one selected solver; training and counterfactual control costs reported separately',
        confirmation='Campaign evaluation split uses existing benchmark instances; not a new project-wide untouched confirmation set'))
    for r in records:
        write_json(output/'runs'/f"{r['case']}__{r['master_seed']}__{r['method']}.json",r)
    original = Evaluator.evaluate
    completed = 0
    plan = None
    started = time.perf_counter()
    for split in ['training','evaluation']:
        if split=='evaluation':
            training = [c['name'] for c in cases if c['split']=='training']
            evaluation = [c['name'] for c in cases if c['split']=='evaluation']
            performances = np.array([[np.mean([r['hypervolume'] for r in records if r['case']==name and r['method']==method])
                                      for method in METHODS] for name in training])
            plan = freeze_selection(training,np.array([features[c] for c in training]),performances,
                                    evaluation,np.array([features[c] for c in evaluation]))
            write_json(output/'frozen_selection.json',plan)
            plan_sha = digest(output/'frozen_selection.json')
            print('FROZEN SELECTION: '+json.dumps(dict(primary=plan['primary_model'],cross_validation=plan['cross_validation'],routes=plan['plans'][plan['primary_model']])),flush=True)
        for ci,case in enumerate(c for c in cases if c['split']==split and not c['reused']):
            instance = load_dzn(output/'instances'/f"{case['name']}.dzn")
            normalizer = ObjectiveNormalizer(compute_instance_bounds(instance))
            for si,seed in enumerate(previous['master_seeds']):
                order = list(METHODS)
                if split=='evaluation':
                    chosen = plan['plans'][plan['primary_model']][case['name']]
                    order = [chosen]+[name for name in METHODS if name!=chosen]
                    assert digest(output/'frozen_selection.json')==plan_sha
                elif (ci+si)%2:
                    order.reverse()
                for method in order:
                    assert all(digest(ROOT/path)==sha for path,sha in hashes.items())
                    calls = 0
                    def counted(self,*a,**kw):
                        nonlocal calls
                        calls += 1
                        return original(self,*a,**kw)
                    try:
                        name,offset = METHODS[method]
                        with patch.object(Evaluator,'evaluate',counted):
                            result = run_standalone_experiment(instance,name,(seed*10007+offset)%(2**31-1),3000,50,30)
                        assert calls==result.evaluations_used==3000 and result.completed
                        hv = compute_hypervolume([normalizer.normalize_tuple(p) for p in result.pareto_front])
                        assert abs(hv-result.hypervolume)<1e-12
                        record = asdict(result)
                        record.update(case=case['name'],split=split,master_seed=seed,method=method,
                                      actual_evaluator_calls=calls,auc_hv=auc(result.checkpoints,3000))
                        write_json(output/'runs'/f"{case['name']}__{seed}__{method}.json",record)
                    except Exception as error:
                        write_json(output/'failure.json',dict(case=case['name'],seed=seed,method=method,
                            actual_evaluator_calls=calls,error=repr(error),completed_new_runs=completed))
                        raise
                    records.append(record)
                    completed += 1
                    print(f"{completed}/150 {split} {case['name']} seed={seed} {method} HV={hv:.6f} elapsed={time.perf_counter()-started:.1f}s",flush=True)
    finish(output,cases,records,plan,completed)


def finish(output,cases,records,plan,completed):
    by_case = []
    for case in cases:
        means = {method:float(np.mean([r['hypervolume'] for r in records if r['case']==case['name'] and r['method']==method])) for method in METHODS}
        delta = means['nsga2']-means['spea2']
        by_case.append(dict(case=case['name'],split=case['split'],nsga2=means['nsga2'],spea2=means['spea2'],
                            delta_nsga2_minus_spea2=delta,winner='tie' if abs(delta)<=1e-12 else ('nsga2' if delta>0 else 'spea2')))
    write_csv(output/'by_instance.csv',by_case)
    write_csv(output/'runs.csv',[{k:r[k] for k in ['case','master_seed','method','hypervolume','auc_hv','runtime_seconds']} for r in records])
    evaluation = [r for r in by_case if r['split']=='evaluation']
    selected,summary = [],[]
    performances = {method:np.array([r[method] for r in evaluation]) for method in METHODS}
    for name in MODELS:
        values = []
        for r in evaluation:
            chosen = plan['plans'][name][r['case']]
            values.append(r[chosen])
            selected.append(dict(case=r['case'],model=name,selected_method=chosen,mean_hv=r[chosen],
                                 delta_vs_nsga2=r[chosen]-r['nsga2'],delta_vs_spea2=r[chosen]-r['spea2']))
        performances[name] = np.array(values)
    performances['oracle_per_instance'] = np.maximum(performances['nsga2'],performances['spea2'])
    for name,values in performances.items():
        summary.append(dict(method=name,mean_hv=float(values.mean()),primary=name==plan['primary_model']))
    write_csv(output/'evaluation_routes.csv',selected)
    write_csv(output/'evaluation_summary.csv',summary)
    rng = np.random.default_rng(20261023)
    comparisons = []
    for model in MODELS:
        for control in METHODS:
            delta = performances[model]-performances[control]
            lo,hi = np.quantile(rng.choice(delta,size=(20000,len(delta))).mean(axis=1),[.025,.975])
            comparisons.append(dict(model=model,control=control,mean_difference=float(delta.mean()),
                bootstrap95_low=float(lo),bootstrap95_high=float(hi),positive_cases=int(sum(delta>1e-12)),
                tied_cases=int(sum(abs(delta)<=1e-12)),negative_cases=int(sum(delta<-1e-12))))
    write_csv(output/'evaluation_comparisons.csv',comparisons)
    best_control = max(METHODS,key=lambda name:float(performances[name].mean()))
    primary = plan['primary_model']
    write_json(output/'conclusion.json',dict(primary_model=primary,best_individual=best_control,
        primary_mean_hv=float(performances[primary].mean()),best_individual_mean_hv=float(performances[best_control].mean()),
        primary_delta_vs_best_individual=float((performances[primary]-performances[best_control]).mean()),
        primary_exceeds_both_individual_means=all(performances[primary].mean()>performances[name].mean()+1e-12 for name in METHODS),
        evaluation_cases=13,training_cases=18,new_runs=completed,new_search_fe=completed*3000,
        oracle_note='Retrospective best algorithm per case; diagnostic ceiling among these two saved individual performances, not a deployable result',
        moead_search_evaluations=0))
    assert completed==150 and len(records)==186
    write_json(output/'validation.json',dict(passed=True,new_runs=150,new_search_fe=450000,reused_runs=36,
        frozen_selection_sha256=digest(output/'frozen_selection.json'),evaluation_cases=13,training_cases=18,
        all_budgets_exact=True,all_new_hv_recomputed=True,source_code_unchanged=True,moead_search_fe=0))
    write_json(output/'artifact_manifest.json',{str(p.relative_to(output)):digest(p)
        for p in sorted(output.rglob('*')) if p.is_file() and p.name!='artifact_manifest.json'})


if __name__=='__main__':
    main()
