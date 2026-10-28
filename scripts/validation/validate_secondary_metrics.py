"""Secondary metrics on the holdout: IGD+ and additive epsilon, to check the conclusion does not rest on HV alone.

Run from the project root:
    .venv\\Scripts\\python.exe scripts\\validation\\validate_secondary_metrics.py

Uses only the saved fronts (no search). For each instance the reference front is the
non-dominated union of the 45 runs (the 8 frozen holdout methods plus the scaled-UCB
MOEA/D+BLMR pair from the complementary policy comparison, 5 seeds each). The scaled pair
is reported apart from the seven frozen controls and stays out of the Holm family, because
it was added after the holdout decision. Both metrics are computed with
two normalizations: the reference front's ideal and nadir (standard for IGD+ and epsilon)
and the fixed instance bounds used by HV. Lower is better for both metrics.
Writes results/experiments/holdout_early_moead_600_20261024/secondary_metrics.json.
"""
import csv, json, statistics as st, sys
from collections import defaultdict
from pathlib import Path
import numpy as np
from scipy.stats import wilcoxon

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src")]
from mojssp.io import load_dzn
from mojssp.normalization import compute_instance_bounds

HOLD = ROOT / "results/experiments/holdout_early_moead_600_20261024"
SPLIT = ROOT / "data/generated/expanded_200/experimental_split.csv"
PSMB, METHODS = "early_moead_600", ["explorer_solo", "moead", "passive", "nsga2_individual",
                                     "spea2_individual", "nsga2_ls_individual", "mopso_individual"]
COMPLEMENTARY, SCALED = ROOT / "results/experiments/holdout_policy_comparison_20261025", "moead_blmr_scaled"
ALL = [PSMB] + METHODS + [SCALED]
SEEDS = [100, 200, 300, 400, 500]
METRICS = ["hv", "igd_plus_ref", "eps_ref", "igd_plus_fixed", "eps_fixed"]
LOWER_IS_BETTER = {"hv": False, "igd_plus_ref": True, "eps_ref": True, "igd_plus_fixed": True, "eps_fixed": True}
LABEL = {"hv": "HV", "igd_plus_ref": "IGD+ (norm. referencia)", "eps_ref": "epsilon (norm. referencia)",
         "igd_plus_fixed": "IGD+ (cotas fijas)", "eps_fixed": "epsilon (cotas fijas)"}

def say(msg): print(msg, flush=True)

def non_dominated(points):
    """Unique non-dominated rows of an (n, 3) array, minimization."""
    pts = np.unique(points, axis=0)
    keep = np.ones(len(pts), dtype=bool)
    for start in range(0, len(pts), 500):
        chunk = pts[start:start + 500]
        dominated = ((pts[None, :, :] <= chunk[:, None, :]).all(axis=2)
                     & (pts[None, :, :] < chunk[:, None, :]).any(axis=2)).any(axis=1)
        keep[start:start + 500] = ~dominated
    return pts[keep]

def igd_plus(front, ref):
    """Mean over reference points of the dominance-aware distance to the closest front point."""
    gap = np.maximum(front[None, :, :] - ref[:, None, :], 0.0)
    return float(np.sqrt((gap ** 2).sum(axis=2)).min(axis=1).mean())

def additive_epsilon(front, ref):
    """Smallest shift so that the front weakly dominates every reference point."""
    return float((front[None, :, :] - ref[:, None, :]).max(axis=2).min(axis=1).max())

def paired_a12(x, y, lower_is_better):
    """Per-instance Vargha-Delaney A12 over seeds (P[PS-MB better than control]), then averaged."""
    values = []
    for a, b in zip(x, y):
        a, b = np.asarray(a)[:, None], np.asarray(b)[None, :]
        better = (a < b) if lower_is_better else (a > b)
        values.append(float((better + 0.5 * (a == b)).mean()))
    return float(np.mean(values))

rows = [r for r in csv.DictReader(open(SPLIT, encoding="utf-8-sig")) if r["assigned_split"] == "holdout_test"]
meta = {r["instance_name"]: r for r in rows}

say("Cargando las 3200 corridas del holdout y las 400 del UCB escalado...")
fronts, hv = defaultdict(dict), defaultdict(dict)
files = list((HOLD / "runs").glob("*.json")) + list((COMPLEMENTARY / "runs").glob(f"*__{SCALED}.json"))
for f in files:
    case, seed, method = f.stem.split("__")
    run = json.loads(f.read_text())
    fronts[case][(method, int(seed))] = np.unique(np.array(run["pareto_front"], dtype=float), axis=0)
    hv[case][(method, int(seed))] = run["hypervolume"]
cases = sorted(fronts)
assert len(cases) == 80 and all(len(fronts[c]) == 45 for c in cases) and set(cases) == set(meta)

say("Calculando frentes de referencia, IGD+ y epsilon...")
values = {m: defaultdict(dict) for m in METRICS}   # metric -> case -> (method, seed) -> value
ref_sizes = {}
for i, case in enumerate(cases, 1):
    ref = non_dominated(np.vstack(list(fronts[case].values())))
    ref_sizes[case] = len(ref)
    ideal, nadir = ref.min(axis=0), ref.max(axis=0)
    span = np.where(nadir > ideal, nadir - ideal, 1.0)
    b = compute_instance_bounds(load_dzn(ROOT / meta[case]["file_path"]))
    lo = np.array([b.cmax_min, b.tardiness_min, b.energy_min], dtype=float)
    width = np.array([b.cmax_max - b.cmax_min, b.tardiness_max - b.tardiness_min, b.energy_max - b.energy_min], dtype=float)
    width = np.where(width > 0, width, 1.0)
    ref_r, ref_f = (ref - ideal) / span, (ref - lo) / width
    for key, front in fronts[case].items():
        fr, ff = (front - ideal) / span, (front - lo) / width
        values["hv"][case][key] = hv[case][key]
        values["igd_plus_ref"][case][key] = igd_plus(fr, ref_r)
        values["eps_ref"][case][key] = additive_epsilon(fr, ref_r)
        values["igd_plus_fixed"][case][key] = igd_plus(ff, ref_f)
        values["eps_fixed"][case][key] = additive_epsilon(ff, ref_f)
    if i % 20 == 0: say(f"   {i}/80 instancias")

base = defaultdict(list)
for c in cases: base[meta[c]["base_id"]].append(c)
groups = list(base.values())
rng = np.random.default_rng(20261028)
report = dict(reference_front_size=dict(min=min(ref_sizes.values()), median=int(np.median(list(ref_sizes.values()))),
                                        max=max(ref_sizes.values())), metrics={})

for metric in METRICS:
    low = LOWER_IS_BETTER[metric]
    inst_mean = {c: {m: st.mean(values[metric][c][(m, s)] for s in SEEDS) for m in ALL} for c in cases}
    means = {m: st.mean(inst_mean[c][m] for c in cases) for m in ALL}
    ranking = sorted(means, key=means.get, reverse=not low)
    say(f"\n{LABEL[metric]} ({'menor' if low else 'mayor'} es mejor)")
    say("   orden: " + ", ".join(f"{m}={means[m]:.4f}" for m in ranking))
    table, pvals = {}, {}
    for ref in METHODS + [SCALED]:
        # advantage of PS-MB, positive = PS-MB better, whatever the metric direction
        d = np.array([(inst_mean[c][ref] - inst_mean[c][PSMB]) if low else (inst_mean[c][PSMB] - inst_mean[c][ref])
                      for c in cases])
        lo_ci, hi_ci = np.quantile(rng.choice(d, size=(20000, len(d))).mean(axis=1), [.025, .975])
        p = float(wilcoxon(d).pvalue) if np.any(d != 0) else 1.0
        if ref != SCALED: pvals[ref] = p
        a12 = paired_a12([[values[metric][c][(PSMB, s)] for s in SEEDS] for c in cases],
                         [[values[metric][c][(ref, s)] for s in SEEDS] for c in cases], low)
        table[ref] = dict(control_mean=means[ref], advantage=float(d.mean()), ci=[float(lo_ci), float(hi_ci)],
                          wins=int((d > 0).sum()), losses=int((d < 0).sum()), wilcoxon_p=p, paired_A12=a12)
        if ref in ("explorer_solo", "moead", "passive", SCALED):
            gd = [np.mean([d[cases.index(c)] for c in g]) for g in groups]
            w = np.array([len(g) for g in groups])
            idx = rng.integers(0, len(groups), size=(20000, len(groups)))
            boots = (np.array(gd)[idx] * w[idx]).sum(axis=1) / w[idx].sum(axis=1)
            table[ref]["cluster_ci"] = [float(x) for x in np.quantile(boots, [.025, .975])]
    order = sorted(pvals, key=pvals.get); running = 0.0
    for i, ref in enumerate(order):
        running = max(running, min(1.0, (len(order) - i) * pvals[ref])); table[ref]["holm_p"] = running
    for ref in METHODS + [SCALED]:
        t = table[ref]
        cl = f" IC agrupado=[{t['cluster_ci'][0]:+.4f}; {t['cluster_ci'][1]:+.4f}]" if "cluster_ci" in t else ""
        p = f"Holm p={t['holm_p']:.2g}" if ref != SCALED else f"p sin corregir={t['wilcoxon_p']:.2g} (complementario)"
        say(f"   vs {ref:20s} ventaja={t['advantage']:+.4f} IC=[{t['ci'][0]:+.4f}; {t['ci'][1]:+.4f}]{cl} "
            f"gana/pierde={t['wins']}/{t['losses']} {p} A12={t['paired_A12']:.3f}")
    report["metrics"][metric] = dict(lower_is_better=low, means=means, ranking=ranking, versus=table)

# Does the HV verdict survive? PS-MB first and its advantage over each control significant after Holm
say("\nRESUMEN")
summary = {}
for metric in METRICS:
    r = report["metrics"][metric]
    sig = [ref for ref in METHODS if r["versus"][ref]["holm_p"] < 0.05 and r["versus"][ref]["advantage"] > 0]
    worse = [ref for ref in METHODS if r["versus"][ref]["advantage"] < 0]
    against = [ref for ref in worse if r["versus"][ref]["holm_p"] < 0.05]
    s = r["versus"][SCALED]
    scaled = ("PS-MB mejor" if s["cluster_ci"][0] > 0 else "UCB escalado mejor" if s["cluster_ci"][1] < 0 else "empate")
    summary[metric] = dict(psmb_first=r["ranking"][0] == PSMB, significant_after_holm=sig,
                           controls_better_on_average=worse, controls_significantly_better=against,
                           versus_scaled_ucb=scaled)
    say(f"   {LABEL[metric]:28s} primero: {r['ranking'][0]}; PS-MB significativo tras Holm vs {len(sig)}/7"
        + (f"; mejores en media: {worse}" if worse else "")
        + (f"; mejores con Holm p<0,05: {against}" if against else "")
        + f"; vs UCB escalado: {scaled}")
report["summary"] = summary
out = HOLD / "secondary_metrics.json"
out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
say(f"Detalle guardado en {out}")
