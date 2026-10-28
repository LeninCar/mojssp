"""Expert validation of the final holdout experiment (reproduction, leakage, seeds and statistics).

Run from the project root:
    .venv\\Scripts\\python.exe scripts\\validation\\validate_experiments.py

It reads the saved holdout runs, re-runs a small sample, and writes
results/experiments/holdout_early_moead_600_20261024/expert_validation.json.
No search is run except the reproduction sample (about 5 minutes).
"""
import csv, glob, hashlib, json, statistics as st, sys
from collections import defaultdict
from pathlib import Path
import numpy as np
from scipy.stats import wilcoxon

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
from mojssp.io import load_dzn
from mojssp.hypervolume import compute_hypervolume
from mojssp.normalization import ObjectiveNormalizer, compute_instance_bounds

HOLD = ROOT / "results/experiments/holdout_early_moead_600_20261024"
SPLIT = ROOT / "data/generated/expanded_200/experimental_split.csv"
PSMB, METHODS = "early_moead_600", ["explorer_solo", "moead", "passive", "nsga2_individual",
                                     "spea2_individual", "nsga2_ls_individual", "mopso_individual"]
SEEDS = [100, 200, 300, 400, 500]
report, problems = {}, []

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def say(msg): print(msg, flush=True)

rows = [r for r in csv.DictReader(open(SPLIT, encoding="utf-8-sig")) if r["assigned_split"] == "holdout_test"]
meta = {r["instance_name"]: r for r in rows}

# 1. Frozen code: current src must match the hashes recorded when the holdout ran
say("1. Codigo congelado")
cfg = json.loads((HOLD / "config.json").read_text())
changed = [p for p, h in cfg["source_sha256"].items() if p.startswith("src/") and sha(ROOT / p) != h]
report["src_matches_frozen"] = not changed
say(f"   src identico al congelado: {not changed}" + (f" (cambiados: {changed})" if changed else ""))
if changed: problems.append(f"src difiere del congelado: {changed}")

# 2. Reproduction of a sample of holdout runs
say("2. Reproduccion de una muestra del holdout")
import run_multiea_pilot as runner
sample = ["base_c01_5x5_b01", "base_c02_10x10_b01_tard_high", "base_c03_20x10_b01_nrg_strong",
          "base_c04_10x20_b02_btnk_high"]
repro = []
for case in sample:
    inst = load_dzn(ROOT / f"data/generated/expanded_200/{case}.dzn")
    for method in [PSMB, "explorer_solo", "moead"]:
        saved = json.loads((HOLD / "runs" / f"{case}__100__{method}.json").read_text())
        new = runner.run_method(inst, 100, method)
        same = abs(new["hypervolume"] - saved["hypervolume"]) < 1e-12 and \
            sorted(map(tuple, new["pareto_front"])) == sorted(map(tuple, saved["pareto_front"]))
        repro.append(dict(case=case, method=method, saved=saved["hypervolume"], new=new["hypervolume"], identical=same))
        say(f"   {case:32s} {method:16s} guardado={saved['hypervolume']:.6f} nuevo={new['hypervolume']:.6f} {'OK' if same else 'DIFIERE'}")
        if not same: problems.append(f"reproduccion difiere: {case} {method}")
report["reproduction"] = repro

# 3. Leakage: no holdout instance (by name or by file content) used before the holdout run
say("3. Fugas de instancias del holdout")
hold_hashes = {r["file_sha256"]: r["instance_name"] for r in rows}
excluded = {HOLD, ROOT / "results/experiments/holdout_policy_comparison_20261025"}
content_hits, name_hits = [], []
for f in glob.glob(str(ROOT / "results/**/*.dzn"), recursive=True):
    if any(Path(f).is_relative_to(e) for e in excluded): continue
    if sha(f) in hold_hashes: content_hits.append((f, hold_hashes[sha(f)]))
names = set(meta)
for f in glob.glob(str(ROOT / "results/**/runs.csv"), recursive=True) + glob.glob(str(ROOT / "results/**/config.json"), recursive=True):
    if any(Path(f).is_relative_to(e) for e in excluded): continue
    text = Path(f).read_text(encoding="utf-8", errors="ignore")
    hit = [n for n in names if n in text]
    if hit: name_hits.append((str(Path(f).relative_to(ROOT)), len(hit)))
report["leak_content_hits"], report["leak_name_hits"] = content_hits, name_hits
say(f"   copias del holdout en campanas previas: {len(content_hits)}; archivos de corridas/config que lo nombran: {len(name_hits)}")
for f, k in name_hits: say(f"     nombra {k} instancias: {f}")
if content_hits or name_hits: problems.append("posible fuga de instancias del holdout (revisar lista)")

# Load saved holdout results
say("   cargando las 3200 corridas guardadas...")
hv = defaultdict(dict)
for f in (HOLD / "runs").glob("*.json"):
    case, seed, method = f.stem.split("__")
    hv[case][(method, int(seed))] = json.loads(f.read_text())["hypervolume"]
cases = sorted(hv)
inst_mean = {c: {m: st.mean(hv[c][(m, s)] for s in SEEDS) for m in [PSMB] + METHODS} for c in cases}

# 4. Seeds: same five seeds for every method; result per seed
say("4. Semillas")
complete = all(len(hv[c]) == 40 for c in cases)
report["all_methods_all_seeds"] = complete
per_seed = {}
for ref in ["explorer_solo", "moead", "passive"]:
    diffs = [st.mean(hv[c][(PSMB, s)] - hv[c][(ref, s)] for c in cases) for s in SEEDS]
    per_seed[ref] = diffs
    say(f"   PS-MB - {ref:14s} por semilla: " + ", ".join(f"{d:+.4f}" for d in diffs) + f"  (gana en {sum(d > 0 for d in diffs)}/5)")
report["per_seed_difference"] = per_seed

# 5. Tables recomputed from raw runs and compared with decision.json
say("5. Tablas recalculadas desde las corridas")
dec = json.loads((HOLD / "decision.json").read_text())
rng = np.random.default_rng(20261024)
table, pvals = {}, {}
for ref in METHODS:
    d = np.array([inst_mean[c][PSMB] - inst_mean[c][ref] for c in cases])
    lo, hi = np.quantile(rng.choice(d, size=(20000, len(d))).mean(axis=1), [.025, .975])
    p = float(wilcoxon(d).pvalue); pvals[ref] = p
    # Paired A12: per instance over the five seeds (P[PS-MB HV > control HV]), then averaged
    a12 = float(np.mean([np.mean([(hv[c][(PSMB, s)] > hv[c][(ref, t)]) + 0.5 * (hv[c][(PSMB, s)] == hv[c][(ref, t)])
                                  for s in SEEDS for t in SEEDS]) for c in cases]))
    table[ref] = dict(mean_difference=float(d.mean()), ci=[float(lo), float(hi)], wins=int((d > 0).sum()),
                      wilcoxon_p=p, vargha_delaney_A=a12)
    stored = dec["versus"][ref]["mean_difference"]
    if abs(stored - d.mean()) > 1e-12: problems.append(f"diferencia guardada no coincide: {ref}")
    say(f"   vs {ref:20s} dif={d.mean():+.4f} IC=[{lo:+.4f}; {hi:+.4f}] gana={int((d > 0).sum())}/80 p={p:.2g} A12={a12:.3f} "
        f"{'coincide' if abs(stored - d.mean()) < 1e-12 else 'NO COINCIDE'}")

# Holm correction over the seven comparisons
order = sorted(pvals, key=pvals.get); holm, running = {}, 0.0
for i, ref in enumerate(order):
    running = max(running, min(1.0, (len(order) - i) * pvals[ref])); holm[ref] = running
for ref in METHODS: table[ref]["holm_p"] = holm[ref]
say("   Holm: " + ", ".join(f"{r}={holm[r]:.2g}" for r in order))

# Cluster bootstrap by base instance (profiles of one base share structure)
base = defaultdict(list)
for c in cases: base[meta[c]["base_id"]].append(c)
groups = list(base.values())
for ref in ["explorer_solo", "moead", "passive"]:
    gd = [np.mean([inst_mean[c][PSMB] - inst_mean[c][ref] for c in g]) for g in groups]
    w = [len(g) for g in groups]
    idx = rng.integers(0, len(groups), size=(20000, len(groups)))
    boots = (np.array(gd)[idx] * np.array(w)[idx]).sum(axis=1) / np.array(w)[idx].sum(axis=1)
    lo, hi = np.quantile(boots, [.025, .975])
    table[ref]["cluster_ci"] = [float(lo), float(hi)]
    say(f"   IC por instancia base ({len(groups)} grupos) vs {ref:14s}: [{lo:+.4f}; {hi:+.4f}]")
report["comparisons"] = table

# 6. Means match decision.json
for m in [PSMB] + METHODS:
    mine = st.mean(inst_mean[c][m] for c in cases)
    if abs(mine - dec["means"][m]) > 1e-12: problems.append(f"media no coincide: {m}")
report["problems"] = problems
(HOLD / "expert_validation.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
say("\nRESUMEN: " + ("todo coincide, sin problemas" if not problems else f"{len(problems)} problema(s):"))
for p in problems: say(f"  - {p}")
say(f"Detalle guardado en {HOLD / 'expert_validation.json'}")
