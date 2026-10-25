"""Paired, base-level summaries for a candidate and compatible saved controls."""
from collections import defaultdict
import numpy as np
from run_weighted_pilot import write_csv


def analyze_candidate(output, records, candidate, controls):
    rows = [{key:r[key] for key in ['case','master_seed','method','hypervolume','auc_hv','runtime_seconds']}
            for r in records]
    write_csv(output/'runs.csv',rows)
    cells = defaultdict(list)
    for row in rows: cells[row['case'],row['method']].append(row)
    by_instance = [dict(case=case,method=method,seeds=len(group),
        **{f'mean_{key}':float(np.mean([r[key] for r in group]))
           for key in ['hypervolume','auc_hv','runtime_seconds']}) for (case,method),group in sorted(cells.items())]
    write_csv(output/'by_instance.csv',by_instance)
    summary = [dict(method=method,**{key:float(np.mean([r[key] for r in by_instance if r['method']==method]))
        for key in ['mean_hypervolume','mean_auc_hv','mean_runtime_seconds']}) for method in controls+[candidate]]
    write_csv(output/'summary.csv',summary)
    index = {(r['case'],r['method']):r for r in by_instance}
    cases = sorted({r['case'] for r in by_instance})
    rng = np.random.default_rng(20261023)
    comparisons = []
    for control in controls:
        for metric in ['hypervolume','auc_hv']:
            delta = np.array([index[case,candidate][f'mean_{metric}']-index[case,control][f'mean_{metric}'] for case in cases])
            lo,hi = np.quantile(rng.choice(delta,size=(20000,len(cases))).mean(axis=1),[.025,.975])
            comparisons.append(dict(control=control,metric=metric,mean_difference=float(delta.mean()),
                bootstrap95_low=float(lo),bootstrap95_high=float(hi),positive_bases=int(sum(delta>1e-12)),
                tied_bases=int(sum(abs(delta)<=1e-12)),negative_bases=int(sum(delta<-1e-12))))
    write_csv(output/'comparisons.csv',comparisons)
