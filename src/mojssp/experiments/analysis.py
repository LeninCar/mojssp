"""Summary tables written by every campaign: runs, means by instance, means by method and paired comparisons."""

from collections import defaultdict

import numpy as np

from .common import write_csv


def analyze(output, records, candidates, controls):
    """Writes runs.csv, by_instance.csv, summary.csv and comparisons.csv (instance bootstrap 95 %)."""
    fields = ["case", "master_seed", "method", "hypervolume", "auc_hv", "runtime_seconds"]
    rows = [{key: record[key] for key in fields} for record in records]
    write_csv(output / "runs.csv", rows)
    cells = defaultdict(list)
    for row in rows:
        cells[row["case"], row["method"]].append(row)
    by_instance = [
        dict(
            case=case,
            method=method,
            seeds=len(group),
            **{f"mean_{key}": float(np.mean([row[key] for row in group])) for key in fields[3:]},
        )
        for (case, method), group in sorted(cells.items())
    ]
    write_csv(output / "by_instance.csv", by_instance)
    summary = [
        dict(
            method=method,
            **{
                key: float(np.mean([row[key] for row in by_instance if row["method"] == method]))
                for key in ["mean_hypervolume", "mean_auc_hv", "mean_runtime_seconds"]
            },
        )
        for method in controls + candidates
    ]
    write_csv(output / "summary.csv", summary)
    index = {(row["case"], row["method"]): row for row in by_instance}
    cases = sorted({row["case"] for row in by_instance})
    rng = np.random.default_rng(20261023)
    comparisons = []
    for candidate in candidates:
        for control in controls:
            for metric in ["hypervolume", "auc_hv"]:
                delta = np.array(
                    [
                        index[case, candidate][f"mean_{metric}"] - index[case, control][f"mean_{metric}"]
                        for case in cases
                    ]
                )
                lo, hi = np.quantile(rng.choice(delta, size=(20000, len(cases))).mean(axis=1), [0.025, 0.975])
                comparisons.append(
                    dict(
                        candidate=candidate,
                        control=control,
                        metric=metric,
                        mean_difference=float(delta.mean()),
                        bootstrap95_low=float(lo),
                        bootstrap95_high=float(hi),
                        positive_bases=int(sum(delta > 1e-12)),
                        tied_bases=int(sum(abs(delta) <= 1e-12)),
                        negative_bases=int(sum(delta < -1e-12)),
                    )
                )
    write_csv(output / "comparisons.csv", comparisons)
