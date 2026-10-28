"""Sweep of the PS-MB exclusive cut on development instances, then a one-time confirmation on a new holdout.

Phase 1, develop: runs the MOEA/D + BLMR dynamic-round portfolio with the exclusive BLMR phase starting at
300, 600, 900, 1200 or 1800 FE, the pair without cut (passive), the scaled-UCB pair, BLMR alone and MOEA/D
alone on the 120 development instances of expanded_200 (never used before), and picks the configuration with
the rule below, fixed before running. The 80 holdout_test instances are not touched.

Phase 2, confirm: runs the selected configuration, the frozen PS-MB (cut 600), the scaled-UCB pair, the pair
without cut, BLMR alone and MOEA/D alone once on a new set of instances that shares no file with expanded_200.

From the project root (PowerShell):
    $env:PYTHONPATH = "src"
    .venv\\Scripts\\python.exe scripts\\campaigns\\run_cut_sweep.py develop --output-dir results\\experiments\\cut_sweep_development_20261028
    .venv\\Scripts\\python.exe scripts\\campaigns\\run_cut_sweep.py confirm --development-dir results\\experiments\\cut_sweep_development_20261028 --instances-dir <new instances> --output-dir results\\experiments\\cut_sweep_confirmation_<date>
Add --resume to continue an interrupted run. --max-instances and --seeds make a reduced smoke run that writes
no decision.
"""

import argparse, csv, json, subprocess
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from unittest.mock import patch
import numpy as np
from scipy.stats import wilcoxon
from mojssp.experiments.analysis import analyze
from mojssp.experiments.common import ROOT, auc, digest, independent_hv, write_csv, write_json
from mojssp.experiments import methods
from mojssp.model.io import load_dzn
from mojssp.model.evaluator import Evaluator
from mojssp.metrics.normalization import ObjectiveNormalizer, compute_instance_bounds

SPLIT = ROOT / "data/generated/expanded_200/experimental_split.csv"
CUTS = [300, 600, 900, 1200, 1800]
CUT_METHODS = [f"cut_{c}" for c in CUTS]
SCALED, PASSIVE, FROZEN = "moead_blmr_scaled", "passive", "cut_600"
INDIVIDUALS = ["explorer_solo", "moead"]
DEVELOPMENT_METHODS = CUT_METHODS + [PASSIVE, SCALED] + INDIVIDUALS
DEVELOPMENT_SEEDS = [100, 200, 300]
CONFIRMATION_SEEDS = [100, 200, 300, 400, 500]
DEVELOPMENT_RULE = (
    "Fixed before running. Scores are mean HV over seeds per instance, then equal instance weights. "
    "(1) The best fixed cut is the cut_X with the highest development mean. "
    "(2) A size-adaptive rule picks, for each instance dimension, the cut with the highest mean on that dimension. "
    "Both rules are scored out of sample by leave-one-base-out: the cut(s) are chosen without the held-out base "
    "instance and its profiles, then scored on them. The size-adaptive rule is adopted only if its leave-one-base-out "
    "advantage over the fixed rule has a base-clustered bootstrap 95% interval above zero; otherwise the best fixed "
    "cut is selected. (3) The 600 FE cut is called justified if cut_600 is the best fixed cut or the clustered "
    "interval of best fixed cut minus cut_600 includes zero. Comparisons with the scaled-UCB pair, the pair without "
    "cut and the individuals are descriptive here; they are decided in the confirmation phase."
)
CONFIRMATION_RULE = (
    "Fixed before running, once, on instances never used before. The selected configuration is confirmed if its "
    "mean HV exceeds the frozen PS-MB (cut_600, unless it is the selection), the scaled-UCB pair and BLMR alone, "
    "and its instance bootstrap 95% interval against BLMR alone excludes zero. Against the scaled-UCB pair, an "
    "interval that includes zero is reported as a tie."
)


def run_method(instance, seed, method, mapping=None):
    if not method.startswith("cut_") and method != "selected":
        return methods.run_method(instance, seed, method)
    cut = mapping[dimension(instance)] if method == "selected" else int(method.split("_")[1])
    r = methods.run_psmb(instance, seed, cut=cut)
    r["exclusive_after"] = cut
    return r


def dimension(instance):
    return f"{len(instance.jobs)}x{instance.num_machines}"


def execute(task):
    out, path, case, seed, method, mapping = task
    target = out / "runs" / f"{case}__{seed}__{method}.json"
    if target.exists():
        r = json.loads(target.read_text())
        return case, seed, method, r["hypervolume"], True
    instance = load_dzn(path)
    original = Evaluator.evaluate
    calls = 0

    def counted(self, *a, **kw):
        nonlocal calls
        calls += 1
        return original(self, *a, **kw)

    with patch.object(Evaluator, "evaluate", counted):
        r = run_method(instance, seed, method, mapping)
    assert calls == r["evaluations_used"] == 3000
    norm = ObjectiveNormalizer(compute_instance_bounds(instance))
    assert (
        abs(independent_hv([norm.normalize_tuple(p) for p in r["pareto_front"]]) - r["hypervolume"]) < 1e-10
    )
    r.update(
        case=case,
        master_seed=seed,
        method=method,
        dimension=dimension(instance),
        actual_evaluator_calls=calls,
        auc_hv=auc(r["checkpoints"], 3000),
        origin="new",
    )
    for key in ["front_entries", "region_trace"]:
        r.pop(key, None)
    write_json(target, r)
    return case, seed, method, r["hypervolume"], False


def bootstrap(delta, seed):
    rng = np.random.default_rng(seed)
    lo, hi = np.quantile(rng.choice(delta, size=(20000, len(delta))).mean(axis=1), [0.025, 0.975])
    return [float(lo), float(hi)]


def cluster_bootstrap(delta_by_case, groups, seed):
    """Bootstrap over base instances; each resampled base keeps all its profiles."""
    rng = np.random.default_rng(seed)
    means = np.array([np.mean([delta_by_case[c] for c in g]) for g in groups])
    w = np.array([len(g) for g in groups])
    idx = rng.integers(0, len(groups), size=(20000, len(groups)))
    lo, hi = np.quantile((means[idx] * w[idx]).sum(axis=1) / w[idx].sum(axis=1), [0.025, 0.975])
    return [float(lo), float(hi)]


def frozen_state(parser, full):
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--", "src", "scripts", "data/generated/expanded_200"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    if dirty and full:
        parser.error("Commit src, scripts and the instances before running")
    files = sorted((ROOT / "src/mojssp").rglob("*.py")) + sorted((ROOT / "scripts").rglob("*.py"))
    return head, {str(p.relative_to(ROOT)).replace("\\", "/"): digest(p) for p in files}


def prepare(parser, args, config):
    out = args.output_dir.resolve()
    if not out.is_relative_to(ROOT / "results/experiments"):
        parser.error("Choose a folder inside results/experiments")
    if out.exists():
        if not args.resume:
            parser.error("Output exists; pass --resume to continue the same frozen run")
        previous = json.loads((out / "config.json").read_text())
        for key in ["frozen_commit", "source_sha256", "instances", "seeds", "methods"]:
            if previous[key] != config[key]:
                parser.error(f"--resume with a different {key}")
        for name in [
            "runs.csv",
            "by_instance.csv",
            "summary.csv",
            "comparisons.csv",
            "breakdown.csv",
            "decision.json",
            "artifact_manifest.json",
        ]:
            (out / name).unlink(missing_ok=True)
    else:
        (out / "runs").mkdir(parents=True)
        write_json(out / "config.json", config)
    return out


def run_all(out, tasks, workers):
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for i, f in enumerate(as_completed([pool.submit(execute, t) for t in tasks]), 1):
            case, seed, method, hv, cached = f.result()
            print(
                f"{i}/{len(tasks)} {case} {seed} {method} HV={hv:.6f}{' cached' if cached else ''}",
                flush=True,
            )
    records = [json.loads(p.read_text()) for p in (out / "runs").glob("*.json")]
    assert len(records) == len(tasks)
    return records


def instance_means(records, methods):
    cell = defaultdict(list)
    for r in records:
        cell[r["case"], r["method"]].append(r["hypervolume"])
    cases = sorted({r["case"] for r in records})
    return cases, {(c, m): float(np.mean(cell[c, m])) for c in cases for m in methods}


def manifest(out):
    write_json(
        out / "artifact_manifest.json",
        {
            str(p.relative_to(out)).replace("\\", "/"): digest(p)
            for p in out.rglob("*")
            if p.is_file() and p.name != "artifact_manifest.json"
        },
    )


def develop(parser, args):
    rows = [
        r for r in csv.DictReader(open(SPLIT, encoding="utf-8-sig")) if r["assigned_split"] == "development"
    ]
    assert len(rows) == 120
    for r in rows:
        assert digest(ROOT / r["file_path"]) == r["file_sha256"]
    rows = sorted(rows, key=lambda r: (int(r["total_operations"]), r["instance_name"]))
    full = args.max_instances is None and args.seeds is None
    if args.max_instances:
        rows = rows[: args.max_instances]
    seeds = args.seeds or DEVELOPMENT_SEEDS
    head, hashes = frozen_state(parser, full)
    config = dict(
        phase="develop",
        frozen_commit=head,
        split=str(SPLIT.relative_to(ROOT)).replace("\\", "/"),
        split_sha256=digest(SPLIT),
        instances=[
            dict(
                name=r["instance_name"],
                base_id=r["base_id"],
                dimensions=r["dimensions"],
                profile=r["profile"],
                sha256=r["file_sha256"],
            )
            for r in rows
        ],
        seeds=seeds,
        methods=DEVELOPMENT_METHODS,
        budget=3000,
        population_size=30,
        block_size=50,
        cuts=CUTS,
        full_design=full,
        decision_rule=DEVELOPMENT_RULE,
        source_sha256=hashes,
        scope="Development instances only; the 80 holdout_test instances are not used",
    )
    out = prepare(parser, args, config)
    tasks = [
        (out, ROOT / r["file_path"], r["instance_name"], s, m, None)
        for r in reversed(rows)
        for s in seeds
        for m in DEVELOPMENT_METHODS
    ]
    records = run_all(out, tasks, args.workers)
    for r in records:
        assert r["dimension"] == next(x["dimensions"] for x in rows if x["instance_name"] == r["case"])
    analyze(out, records, CUT_METHODS + [PASSIVE, SCALED], INDIVIDUALS)
    meta = {r["instance_name"]: r for r in rows}
    cases, inst = instance_means(records, DEVELOPMENT_METHODS)
    means = {m: float(np.mean([inst[c, m] for c in cases])) for m in DEVELOPMENT_METHODS}
    bases = defaultdict(list)
    for c in cases:
        bases[meta[c]["base_id"]].append(c)
    groups = list(bases.values())
    dims = sorted(
        {meta[c]["dimensions"] for c in cases}, key=lambda d: int(d.split("x")[0]) * int(d.split("x")[1])
    )

    def best_cut(subset):
        return max(
            CUT_METHODS, key=lambda m: (np.mean([inst[c, m] for c in subset]), -CUTS[CUT_METHODS.index(m)])
        )

    best_fixed = best_cut(cases)
    adaptive = {d: best_cut([c for c in cases if meta[c]["dimensions"] == d]) for d in dims}

    breakdown = [
        dict(
            dimension=d,
            method=m,
            instances=sum(meta[c]["dimensions"] == d for c in cases),
            mean_hypervolume=float(np.mean([inst[c, m] for c in cases if meta[c]["dimensions"] == d])),
        )
        for d in dims
        for m in DEVELOPMENT_METHODS
    ]
    write_csv(out / "breakdown.csv", breakdown)

    # Leave-one-base-out scores of both selection rules
    lobo_fixed, lobo_adaptive = {}, {}
    for base, held in bases.items():
        rest = [c for c in cases if meta[c]["base_id"] != base]
        fixed = best_cut(rest)
        for c in held:
            same = [x for x in rest if meta[x]["dimensions"] == meta[c]["dimensions"]]
            lobo_fixed[c] = inst[c, fixed]
            lobo_adaptive[c] = inst[c, best_cut(same)] if same else inst[c, fixed]
    lobo_delta = {c: lobo_adaptive[c] - lobo_fixed[c] for c in cases}
    adaptive_ci = cluster_bootstrap(lobo_delta, groups, 20261028) if len(groups) > 1 else [0.0, 0.0]
    adopt_adaptive = adaptive_ci[0] > 0

    versus = {}
    for m in [x for x in DEVELOPMENT_METHODS if x != best_fixed]:
        delta = np.array([inst[c, best_fixed] - inst[c, m] for c in cases])
        versus[m] = dict(
            mean_difference=float(delta.mean()),
            bootstrap95=bootstrap(delta, 20261028),
            cluster_bootstrap95=cluster_bootstrap(dict(zip(cases, delta)), groups, 20261029)
            if len(groups) > 1
            else None,
            wins=int((delta > 1e-12).sum()),
            losses=int((delta < -1e-12).sum()),
            wilcoxon_p=float(wilcoxon(delta).pvalue) if np.any(delta != 0) else 1.0,
        )
    justified = best_fixed == FROZEN or (versus[FROZEN]["cluster_bootstrap95"] or [0, 0])[0] <= 0
    selected = (
        dict(
            kind="size_adaptive",
            cut_by_dimension={d: CUTS[CUT_METHODS.index(m)] for d, m in adaptive.items()},
        )
        if adopt_adaptive
        else dict(kind="fixed", cut=CUTS[CUT_METHODS.index(best_fixed)])
    )
    decision = dict(
        full_design=full,
        decision_rule=DEVELOPMENT_RULE,
        means=means,
        best_fixed_cut=best_fixed,
        size_adaptive_cuts={d: CUTS[CUT_METHODS.index(m)] for d, m in adaptive.items()},
        leave_one_base_out=dict(
            fixed_mean=float(np.mean(list(lobo_fixed.values()))),
            adaptive_mean=float(np.mean(list(lobo_adaptive.values()))),
            adaptive_minus_fixed_cluster95=adaptive_ci,
        ),
        adaptive_adopted=adopt_adaptive,
        cut_600_justified=justified,
        versus_best_fixed=versus,
        selected=selected if full else None,
        frozen_commit=head,
    )
    write_json(out / "decision.json", decision)
    manifest(out)
    print("\nHV medio en desarrollo:")
    for m in sorted(means, key=means.get, reverse=True):
        print(f"   {m:20s} {means[m]:.4f}")
    print(f"Mejor corte fijo: {best_fixed}; cortes por tamaño: {decision['size_adaptive_cuts']}")
    print(
        f"Adaptativo menos fijo (fuera de muestra, IC agrupado): [{adaptive_ci[0]:+.4f}; {adaptive_ci[1]:+.4f}] "
        f"-> {'se adopta el adaptativo' if adopt_adaptive else 'se queda el corte fijo'}"
    )
    print(f"Corte de 600 justificado: {'si' if justified else 'no'}")
    print(f"Seleccion: {selected if full else 'ninguna (corrida reducida)'}")


def confirm(parser, args):
    dev = args.development_dir.resolve()
    decision = json.loads((dev / "decision.json").read_text())
    if not decision.get("full_design") or not decision.get("selected"):
        parser.error("The development run is not a full design")
    selected = decision["selected"]
    files = sorted(args.instances_dir.resolve().glob("*.dzn"))
    if not files:
        parser.error("No .dzn files in --instances-dir")
    if args.max_instances:
        files = files[: args.max_instances]
    used = {r["file_sha256"] for r in csv.DictReader(open(SPLIT, encoding="utf-8-sig"))}
    leaks = [f.name for f in files if digest(f) in used]
    if leaks:
        parser.error(f"Instances already in expanded_200: {leaks}")
    seeds = args.seeds or CONFIRMATION_SEEDS
    full = args.max_instances is None and args.seeds is None
    is_frozen = selected["kind"] == "fixed" and selected["cut"] == 600
    candidate = FROZEN if is_frozen else "selected"
    methods = [candidate] + ([] if is_frozen else [FROZEN]) + [SCALED, PASSIVE] + INDIVIDUALS
    mapping = selected["cut_by_dimension"] if selected["kind"] == "size_adaptive" else None
    if selected["kind"] == "fixed" and not is_frozen:
        methods[0] = candidate = f"cut_{selected['cut']}"
    head, hashes = frozen_state(parser, full)
    config = dict(
        phase="confirm",
        frozen_commit=head,
        development_decision=str(dev.relative_to(ROOT) if dev.is_relative_to(ROOT) else dev).replace(
            "\\", "/"
        ),
        development_decision_sha256=digest(dev / "decision.json"),
        selected=selected,
        instances=[dict(name=f.stem, sha256=digest(f)) for f in files],
        seeds=seeds,
        methods=methods,
        budget=3000,
        population_size=30,
        block_size=50,
        full_design=full,
        decision_rule=CONFIRMATION_RULE,
        source_sha256=hashes,
        scope="First and only use of these instances",
    )
    out = prepare(parser, args, config)
    if mapping:
        for f in files:
            d = dimension(load_dzn(f))
            if d not in mapping:
                parser.error(f"{f.name}: dimension {d} has no selected cut")
    tasks = [(out, f, f.stem, s, m, mapping) for f in files for s in seeds for m in methods]
    records = run_all(out, tasks, args.workers)
    analyze(out, records, [candidate], [m for m in methods if m != candidate])
    cases, inst = instance_means(records, methods)
    means = {m: float(np.mean([inst[c, m] for c in cases])) for m in methods}
    versus = {}
    for m in methods[1:]:
        delta = np.array([inst[c, candidate] - inst[c, m] for c in cases])
        versus[m] = dict(
            mean_difference=float(delta.mean()),
            bootstrap95=bootstrap(delta, 20261030),
            wins=int((delta > 1e-12).sum()),
            losses=int((delta < -1e-12).sum()),
            wilcoxon_p=float(wilcoxon(delta).pvalue) if np.any(delta != 0) else 1.0,
        )
    beats = [m for m in [FROZEN, SCALED, "explorer_solo"] if m != candidate]
    confirmed = (
        all(means[candidate] > means[m] for m in beats) and versus["explorer_solo"]["bootstrap95"][0] > 0
    )
    scaled_ci = versus[SCALED]["bootstrap95"]
    write_json(
        out / "decision.json",
        dict(
            full_design=full,
            decision_rule=CONFIRMATION_RULE,
            candidate=candidate,
            selected=selected,
            means=means,
            versus=versus,
            confirmed=confirmed if full else None,
            versus_scaled="tie"
            if scaled_ci[0] <= 0 <= scaled_ci[1]
            else "candidate better"
            if scaled_ci[0] > 0
            else "scaled better",
            frozen_commit=head,
        ),
    )
    manifest(out)
    print("\nHV medio en el holdout nuevo:")
    for m in sorted(means, key=means.get, reverse=True):
        print(f"   {m:20s} {means[m]:.4f}")
    print(f"Confirmado: {confirmed if full else 'sin decision (corrida reducida)'}")


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="phase", required=True)
    for name in ["develop", "confirm"]:
        p = sub.add_parser(name)
        p.add_argument("--output-dir", required=True, type=Path)
        p.add_argument("--workers", type=int, choices=range(1, 15), default=12)
        p.add_argument("--resume", action="store_true")
        p.add_argument(
            "--max-instances", type=int, help="Smoke run on the first N instances; writes no decision"
        )
        p.add_argument("--seeds", type=int, nargs="+", help="Smoke run with these seeds; writes no decision")
        if name == "confirm":
            p.add_argument("--development-dir", required=True, type=Path)
            p.add_argument("--instances-dir", required=True, type=Path)
    args = parser.parse_args()
    (develop if args.phase == "develop" else confirm)(sub.choices[args.phase], args)


if __name__ == "__main__":
    main()
