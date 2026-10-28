"""Expert review step 3: where fronts sit in the normalized space and robustness to the normalization."""

import glob, json, sys, statistics as st
from collections import defaultdict
from pathlib import Path
import numpy as np

ROOT = Path(r"C:/Users/lenin/Documents/Ingeniería/2026-1/TG1/mojssp-loop-agent")
sys.path.insert(0, str(ROOT / "src"))
from mojssp.metrics.hypervolume import compute_hypervolume
from mojssp.model.io import load_dzn
from mojssp.metrics.normalization import ObjectiveNormalizer, compute_instance_bounds

RUNS = ROOT / "results/experiments/holdout_early_moead_600_20261024/runs"
METHODS = [
    "early_moead_600",
    "explorer_solo",
    "moead",
    "passive",
    "nsga2_individual",
    "spea2_individual",
    "nsga2_ls_individual",
    "mopso_individual",
]
fronts = defaultdict(dict)  # case -> (method, seed) -> raw points
for f in RUNS.glob("*.json"):
    case, seed, method = f.stem.split("__")
    fronts[case][(method, int(seed))] = [
        tuple(p) for p in json.load(open(f, encoding="utf-8"))["pareto_front"]
    ]

# 1) position of PS-MB fronts inside the instance-bound box
spans = defaultdict(list)
for case, runs in fronts.items():
    norm = ObjectiveNormalizer(
        compute_instance_bounds(load_dzn(ROOT / f"data/generated/expanded_200/{case}.dzn"))
    )
    for (m, s), pts in runs.items():
        if m != "early_moead_600":
            continue
        P = np.array([norm.normalize_tuple(p) for p in pts])
        for i, name in enumerate(["makespan", "tardanza", "energia"]):
            spans[name].append((P[:, i].min(), P[:, i].max()))
for name, v in spans.items():
    lo = st.mean(a for a, _ in v)
    hi = st.mean(b for _, b in v)
    print(
        f"{name:9s} normalized range of PS-MB fronts (mean over runs): {lo:.3f} - {hi:.3f} (width {hi - lo:.3f})"
    )

# 2) alternative normalization: ideal/nadir of the union of all 40 fronts of each instance
inst_mean = defaultdict(dict)
for case, runs in fronts.items():
    allp = np.array([p for pts in runs.values() for p in pts], dtype=float)
    lo, hi = allp.min(axis=0), allp.max(axis=0)
    span = np.where(hi - lo > 0, hi - lo, 1.0)
    for m in METHODS:
        vals = []
        for s in (100, 200, 300, 400, 500):
            P = (np.array(runs[(m, s)], dtype=float) - lo) / span
            vals.append(compute_hypervolume([tuple(p) for p in P]))
        inst_mean[case][m] = st.mean(vals)
cases = sorted(inst_mean)
mean = {m: st.mean(inst_mean[c][m] for c in cases) for m in METHODS}
print("\nHV with empirical ideal/nadir normalization (reference 1.1):")
for m in sorted(METHODS, key=mean.get, reverse=True):
    print(f"  {m:22s} {mean[m]:.4f}")
rng = np.random.default_rng(20261027)
for ref in ["explorer_solo", "moead", "passive"]:
    d = np.array([inst_mean[c]["early_moead_600"] - inst_mean[c][ref] for c in cases])
    lo, hi = np.quantile(rng.choice(d, size=(20000, len(d))).mean(axis=1), [0.025, 0.975])
    print(f"  PS-MB - {ref:14s} {d.mean():+.4f} [{lo:+.4f}; {hi:+.4f}] wins {int((d > 0).sum())}/80")
