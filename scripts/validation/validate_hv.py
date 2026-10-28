"""Independent validation of the 3-D hypervolume (expert review step 2)."""
import glob, json, random, sys, itertools
from pathlib import Path
import numpy as np

ROOT = Path(r"C:/Users/lenin/Documents/Ingeniería/2026-1/TG1/mojssp-loop-agent")
sys.path.insert(0, str(ROOT / "src"))
from mojssp.metrics.hypervolume import compute_hypervolume
from mojssp.model.io import load_dzn
from mojssp.metrics.normalization import ObjectiveNormalizer, compute_instance_bounds

REF = (1.1, 1.1, 1.1)

def hv_grid(points, ref=REF):
    """Exact HV by coordinate compression: sum the volume of every grid cell dominated by some point."""
    pts = np.array([p for p in points if all(p[i] <= ref[i] for i in range(3))], dtype=float)
    if len(pts) == 0: return 0.0
    axes = [np.unique(np.append(pts[:, i], ref[i])) for i in range(3)]
    widths = [np.diff(a) for a in axes]
    lo = [a[:-1] for a in axes]
    X, Y, Z = np.meshgrid(*lo, indexing="ij")
    dom = np.zeros(X.shape, dtype=bool)
    for p in pts:
        dom |= (X >= p[0]) & (Y >= p[1]) & (Z >= p[2])
    W = widths[0][:, None, None] * widths[1][None, :, None] * widths[2][None, None, :]
    return float((W * dom).sum())

def hv_incl_excl(points, ref=REF):
    pts = [p for p in points if all(p[i] <= ref[i] for i in range(3))]
    total = 0.0
    for r in range(1, len(pts) + 1):
        for sub in itertools.combinations(pts, r):
            corner = [max(q[i] for q in sub) for i in range(3)]
            total += (-1) ** (r + 1) * np.prod([ref[i] - corner[i] for i in range(3)])
    return total

rng = random.Random(7)
# 1) random small sets: three methods must agree (includes dominated, duplicate and out-of-box points)
worst = 0.0
for _ in range(400):
    k = rng.randint(1, 9)
    pts = [tuple(round(rng.uniform(0, 1.2), 3) for _ in range(3)) for _ in range(k)]
    if rng.random() < 0.3: pts.append(pts[0])
    a, b, c = compute_hypervolume(pts), hv_grid(pts), hv_incl_excl(pts)
    worst = max(worst, abs(a - b), abs(a - c))
print(f"random small sets (400): max |diff| = {worst:.2e}")

# 2) real fronts from the holdout: project HV vs exact grid HV, and vs the HV stored in each run
runs = glob.glob(str(ROOT / "results/experiments/holdout_early_moead_600_20261024/runs/*.json"))
rng.shuffle(runs)
cache, worst_real, worst_store, n, sizes = {}, 0.0, 0.0, 0, []
for f in runs[:160]:
    r = json.load(open(f, encoding="utf-8"))
    case = r["case"]
    if case not in cache:
        cache[case] = ObjectiveNormalizer(compute_instance_bounds(load_dzn(ROOT / f"data/generated/expanded_200/{case}.dzn")))
    pts = [cache[case].normalize_tuple(tuple(p)) for p in r["pareto_front"]]
    a, b = compute_hypervolume(pts), hv_grid(pts)
    worst_real = max(worst_real, abs(a - b)); worst_store = max(worst_store, abs(a - r["hypervolume"]))
    n += 1; sizes.append(len(pts))
print(f"holdout fronts ({n}, {min(sizes)}-{max(sizes)} points): max |project - exact| = {worst_real:.2e}; "
      f"max |recomputed - stored| = {worst_store:.2e}")
