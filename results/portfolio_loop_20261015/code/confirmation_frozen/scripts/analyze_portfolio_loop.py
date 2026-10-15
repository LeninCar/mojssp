"""Recompute paired, base-level evidence from immutable experiment JSON files."""
import argparse
from collections import defaultdict
import itertools
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from run_portfolio_loop import OUT, write_new


def measure(run, key):
    if key == 'genetic_diversity':
        return float(np.mean(list(run['genetic_diversity_final'].values())))
    return run[key]


def allocation_diagnostics(run):
    zeros=defaultdict(int)
    last={n:-1 for n in run['allocation']}
    stale_fe=0
    recoveries=0
    gaps=[]
    deltas=defaultdict(float)
    for i,b in enumerate(run['blocks']):
        n=b['arm_name']
        gaps.append(i-last[n]-1)
        last[n]=i
        if zeros[n]>=2:
            stale_fe+=b['evaluations_used']
            recoveries+=b['reward']>1e-14
        zeros[n]=zeros[n]+1 if b['reward']<=1e-14 else 0
        deltas[n]+=b['reward']
    gaps.extend(len(run['blocks'])-v-1 for v in last.values())
    return {'fe_after_two_global_zero_gains':stale_fe,
            'positive_recoveries_after_two_zero_gains':recoveries,
            'max_idle_blocks':max(gaps),
            'path_dependent_hv_gains':dict(deltas)}


def paired(runs, treatment, control, key):
    by = {(r['case'],r['seed'],r['method']):r for r in runs}
    bases = defaultdict(list)
    for (case,seed,method),r in by.items():
        if method == treatment and (case,seed,control) in by:
            bases[case].append(measure(r,key)-measure(by[(case,seed,control)],key))
    values = np.array([np.mean(v) for _,v in sorted(bases.items())])
    if not len(values):
        return {}
    rng = np.random.default_rng(20261015)
    bootstrap = rng.choice(values, (20000, len(values))).mean(axis=1)
    permutations = np.array([np.mean(values*np.array(signs))
                             for signs in itertools.product([-1,1],repeat=len(values))])
    p = np.mean(np.abs(permutations) >= abs(values.mean())-1e-14)
    return {'n_bases': len(values), 'n_paired_runs': sum(map(len,bases.values())),
            'mean_delta': float(values.mean()),
            'bootstrap95': np.quantile(bootstrap,[.025,.975]).tolist(),
            'permutation_p_two_sided': float(p),
            'base_wtl': [int(sum(values>1e-12)),int(sum(abs(values)<=1e-12)),int(sum(values < -1e-12))],
            'by_base': {c: float(np.mean(v)) for c,v in sorted(bases.items())}}


def analyze(split):
    paths = sorted((OUT/'runs'/split).glob('*.json'))
    runs = [json.loads(p.read_text(encoding='utf-8')) for p in paths if not p.name.endswith('.failed.json')]
    methods = sorted(set(r['method'] for r in runs))
    summary = {}
    keys = ['hv','auc_hv','seconds','unique_vectors','mean_nn_distance','genetic_diversity']
    for method in methods:
        rs = [r for r in runs if r['method']==method]
        summary[method] = {k: float(np.mean([measure(r,k) for r in rs])) for k in keys}
        summary[method].update(n_runs=len(rs), search_fe=sum(r['search_fe'] for r in rs),
            total_search_seconds=sum(r['seconds'] for r in rs),
            total_analysis_seconds=sum(r['analysis_seconds'] for r in rs),
            mean_allocation={n: float(np.mean([r['allocation'].get(n,0)/r['search_fe'] for r in rs]))
                             for n in ['MOEA/D','NSGA-II','SPEA2']},
            mean_marginal_hv={n: float(np.mean([r['marginal_hv'].get(n,0) for r in rs]))
                              for n in ['MOEA/D','NSGA-II','SPEA2']},
            zero_gain_block_fraction=float(np.mean([r['zero_gain_blocks']/len(r['blocks']) for r in rs])),
            guided_crossovers=sum(len(r['guidance_events']) for r in rs))
        diagnostics=[allocation_diagnostics(r) for r in rs]
        summary[method]['stagnation']={k:float(np.mean([d[k] for d in diagnostics]))
                                      for k in ['fe_after_two_global_zero_gains',
                                                'positive_recoveries_after_two_zero_gains',
                                                'max_idle_blocks']}
    comparisons = {f'{t} vs {c}':{k:paired(runs,t,c,k) for k in keys}
                   for t in methods for c in ['adaptive','uniform','moead','nsga2','spea2','scaled','guidance']
                   if t!=c and c in methods}
    # Holm correction over prospective treatment HV tests against original policy.
    tests = sorted((comparisons[f'{m} vs adaptive']['hv']['permutation_p_two_sided'],m)
                   for m in methods if m not in ['adaptive','uniform','moead','nsga2','spea2'])
    running = 0.
    for i,(p,m) in enumerate(tests):
        running = max(running, min(1.,p*(len(tests)-i)))
        comparisons[f'{m} vs adaptive']['hv']['holm_p'] = running
    # An oracle is descriptive, not a feasible policy: per-base mean best individual.
    bybase = defaultdict(lambda:defaultdict(list))
    for r in runs:
        bybase[r['case']][r['method']].append(r['hv'])
    sizes = {}
    for base,ms in sorted(bybase.items()):
        means={m:float(np.mean(v)) for m,v in ms.items()}
        individuals={m:v for m,v in means.items() if m in ['moead','nsga2','spea2']}
        sizes[base]={'mean_hv':means,'oracle_best_individual': max(individuals,key=individuals.get) if individuals else None}
    return {'split':split,'summary':summary,'comparisons':comparisons,'by_base':sizes,
            'search_fe':sum(r['search_fe'] for r in runs),
            'search_seconds':sum(r['seconds'] for r in runs),
            'analysis_seconds':sum(r['analysis_seconds'] for r in runs)}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--split',default='development',choices=['development','confirmation'])
    p.add_argument('--tag',required=True)
    args=p.parse_args()
    result=analyze(args.split)
    write_new(OUT/f'analysis_{args.tag}.json',result)
    print(json.dumps(result['summary'],indent=2))
    for k,v in result['comparisons'].items():
        if k.endswith('vs adaptive'):
            print(k,json.dumps(v['hv']))


if __name__=='__main__':
    main()
