"""Complementary holdout comparison of selection policies and BLMR compositions.

Runs every composition with the uniform, SW-UCB, scaled UCB and Page-Hinkley policies (and dynamic
rounds where they are missing) on the 80 holdout_test instances, and compares them with the frozen
holdout evaluation, whose individual controls, dynamic pair and early_moead_600 runs are reused.
The decision on early_moead_600 was taken before this run; nothing here changes it.
"""

import argparse, csv, json, subprocess
from pathlib import Path
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from unittest.mock import patch
import numpy as np
from scipy.stats import wilcoxon
from mojssp.experiments.analysis import analyze
from mojssp.experiments.common import ROOT, auc, digest, independent_hv, write_csv, write_json
from mojssp.model.io import load_dzn
from mojssp.model.evaluator import Evaluator
from mojssp.metrics.normalization import ObjectiveNormalizer, compute_instance_bounds
from mojssp.portfolio.regional_portfolio import run_regional_policy_experiment

SPLIT = ROOT / "data/generated/expanded_200/experimental_split.csv"
FROZEN = ROOT / "results/experiments/holdout_early_moead_600_20261024"
SEEDS = [100, 200, 300, 400, 500]
COMPOSITIONS = {
    "moead_blmr": ["MOEA/D", "RegionExplorer"],
    "spea2_blmr": ["SPEA2", "RegionExplorer"],
    "nsga2_blmr": ["NSGA-II", "RegionExplorer"],
    "quartet_blmr": ["MOEA/D", "NSGA-II", "SPEA2", "RegionExplorer"],
}
POLICIES = ["uniform", "sw_ucb", "scaled", "ph", "dynamic"]
REUSED = {"moead_blmr_dynamic": "passive"}
INDIVIDUALS = [
    "explorer_solo",
    "moead",
    "nsga2_individual",
    "spea2_individual",
    "nsga2_ls_individual",
    "mopso_individual",
]
FROZEN_METHODS = ["early_moead_600", "passive"] + INDIVIDUALS
REFERENCES = ["early_moead_600", "explorer_solo", "moead", "passive"]


def design():
    return [f"{c}_{p}" for c in COMPOSITIONS for p in POLICIES if f"{c}_{p}" not in REUSED]


def split_method(method):
    for composition in COMPOSITIONS:
        if method.startswith(composition + "_"):
            return composition, method[len(composition) + 1 :]
    raise ValueError(method)


def execute(task):
    out, case, seed, method = task
    path = out / "runs" / f"{case}__{seed}__{method}.json"
    if path.exists():
        r = json.loads(path.read_text())
        return case, seed, method, r["hypervolume"], True
    composition, policy = split_method(method)
    instance = load_dzn(ROOT / "data/generated/expanded_200" / f"{case}.dzn")
    original = Evaluator.evaluate
    calls = 0

    def counted(self, *a, **kw):
        nonlocal calls
        calls += 1
        return original(self, *a, **kw)

    with patch.object(Evaluator, "evaluate", counted):
        r = run_regional_policy_experiment(instance, seed, COMPOSITIONS[composition], policy, False)
    assert calls == r["evaluations_used"] == 3000
    norm = ObjectiveNormalizer(compute_instance_bounds(instance))
    assert (
        abs(independent_hv([norm.normalize_tuple(p) for p in r["pareto_front"]]) - r["hypervolume"]) < 1e-10
    )
    r.update(
        group="holdout",
        case=case,
        master_seed=seed,
        method=method,
        composition=composition,
        actual_evaluator_calls=calls,
        auc_hv=auc(r["checkpoints"], 3000),
        origin="new",
    )
    for key in ["front_entries", "region_trace"]:
        r.pop(key, None)
    write_json(path, r)
    return case, seed, method, r["hypervolume"], False


def bootstrap(delta, seed=20261025):
    rng = np.random.default_rng(seed)
    lo, hi = np.quantile(rng.choice(delta, size=(20000, len(delta))).mean(axis=1), [0.025, 0.975])
    return float(lo), float(hi)


def summarize(out, rows, new_methods):
    records = [json.loads(p.read_text()) for p in (out / "runs").glob("*.json")]
    frozen = [json.loads(p.read_text()) for p in (FROZEN / "runs").glob("*.json")]
    assert len(frozen) == 80 * len(SEEDS) * len(FROZEN_METHODS)
    for r in frozen:
        r["origin"] = "reused_frozen_holdout"
    analyze(out, records + frozen, new_methods, FROZEN_METHODS)
    cell = defaultdict(list)
    for r in records + frozen:
        cell[r["case"], r["method"]].append(r["hypervolume"])
    meta = {r["instance_name"]: r for r in rows}
    cases = sorted(meta)
    methods = FROZEN_METHODS + new_methods
    inst = {(c, m): float(np.mean(cell[c, m])) for c in cases for m in methods}
    assert all(len(cell[c, m]) == len(SEEDS) for c in cases for m in methods)
    means = {m: float(np.mean([inst[c, m] for c in cases])) for m in methods}
    ranking = [
        dict(rank=i, method=m, mean_hypervolume=means[m])
        for i, m in enumerate(sorted(methods, key=means.get, reverse=True), 1)
    ]
    write_csv(out / "ranking.csv", ranking)
    versus = []
    for m in new_methods + ["passive"]:
        for ref in REFERENCES:
            if m == ref:
                continue
            delta = np.array([inst[c, m] - inst[c, ref] for c in cases])
            lo, hi = bootstrap(delta)
            versus.append(
                dict(
                    method=m,
                    reference=ref,
                    mean_difference=float(delta.mean()),
                    bootstrap95_low=lo,
                    bootstrap95_high=hi,
                    wins=int((delta > 1e-12).sum()),
                    losses=int((delta < -1e-12).sum()),
                    wilcoxon_p=float(wilcoxon(delta).pvalue) if np.any(delta) else 1.0,
                )
            )
    write_csv(out / "versus_references.csv", versus)
    policy_table = []
    for composition in COMPOSITIONS:
        row = dict(composition=composition)
        for policy in POLICIES:
            method = REUSED.get(f"{composition}_{policy}", f"{composition}_{policy}")
            row[policy] = means[method]
        policy_table.append(row)
    write_csv(out / "policy_by_composition.csv", policy_table)
    breakdown = []
    for key in ["dimensions", "profile"]:
        for value in sorted({meta[c][key] for c in cases}):
            group = [c for c in cases if meta[c][key] == value]
            for m in methods:
                breakdown.append(
                    dict(
                        by=key,
                        value=value,
                        method=m,
                        instances=len(group),
                        mean_hypervolume=float(np.mean([inst[c, m] for c in group])),
                    )
                )
    write_csv(out / "breakdown.csv", breakdown)
    best_new = max(new_methods, key=means.get)
    write_json(
        out / "summary.json",
        dict(
            means=means,
            best_new_method=best_new,
            early_moead_600_still_first=ranking[0]["method"] == "early_moead_600",
            new_methods_above_early_moead_600=[m for m in new_methods if means[m] > means["early_moead_600"]],
            new_methods_above_best_individual=[
                m for m in new_methods if means[m] > max(means[i] for i in INDIVIDUALS)
            ],
            note="Complementary analysis after the frozen decision; it does not change the holdout verdict.",
        ),
    )


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--output-dir", type=Path, default=ROOT / "results/experiments/holdout_policy_comparison_20261025"
    )
    parser.add_argument("--workers", type=int, choices=range(1, 15), default=14)
    parser.add_argument("--compositions", nargs="+", choices=list(COMPOSITIONS), default=list(COMPOSITIONS))
    parser.add_argument("--policies", nargs="+", choices=POLICIES, default=POLICIES)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="List pending runs and exit without searching")
    args = parser.parse_args()
    out = args.output_dir.resolve()
    if not out.is_relative_to(ROOT / "results/experiments"):
        parser.error("Choose a folder inside results/experiments")
    frozen_config = json.loads((FROZEN / "config.json").read_text())
    rows = [
        r for r in csv.DictReader(open(SPLIT, encoding="utf-8-sig")) if r["assigned_split"] == "holdout_test"
    ]
    assert len(rows) == 80 and digest(SPLIT) == frozen_config["split_sha256"]
    for r in rows:
        assert digest(ROOT / r["file_path"]) == r["file_sha256"]
    full = design()
    selected = [
        m for m in full if split_method(m)[0] in args.compositions and split_method(m)[1] in args.policies
    ]
    size = lambda r: int(r["total_operations"])
    tasks = [
        (out, r["instance_name"], s, m)
        for r in sorted(rows, key=size, reverse=True)
        for s in SEEDS
        for m in selected
    ]
    done = lambda t: (out / "runs" / f"{t[1]}__{t[2]}__{t[3]}.json").exists()
    pending = [t for t in tasks if not done(t)]
    print(
        f"Design: {len(full)} methods, {80 * len(SEEDS) * len(full)} runs; selected {len(selected)} methods, "
        f"{len(tasks)} runs; pending {len(pending)}",
        flush=True,
    )
    for m in selected:
        print("  ", m, sum(1 for t in pending if t[3] == m), "pending", flush=True)
    if args.dry_run:
        return
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
    if dirty:
        parser.error("Commit the code before running so the comparison is reproducible")
    files = sorted((ROOT / "src/mojssp").rglob("*.py")) + sorted((ROOT / "scripts").rglob("*.py"))
    hashes = {str(p.relative_to(ROOT)).replace("\\", "/"): digest(p) for p in files}
    config = dict(
        commit=head,
        frozen_holdout=str(FROZEN.relative_to(ROOT)).replace("\\", "/"),
        frozen_holdout_commit=frozen_config["frozen_commit"],
        split_sha256=digest(SPLIT),
        seeds=SEEDS,
        budget=3000,
        population_size=30,
        block_size=50,
        compositions=COMPOSITIONS,
        policies=POLICIES,
        reused=REUSED,
        new_methods=full,
        reused_methods=FROZEN_METHODS,
        source_sha256=hashes,
        scope="Complementary comparison after the frozen holdout decision; does not change it",
    )
    if out.exists():
        if not args.resume:
            parser.error("Output exists; pass --resume to continue")
        previous = json.loads((out / "config.json").read_text())
        assert previous["source_sha256"] == hashes, "Source code changed since this comparison started"
    else:
        (out / "runs").mkdir(parents=True)
        write_json(out / "config.json", config)
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for i, f in enumerate(as_completed([pool.submit(execute, t) for t in tasks]), 1):
            case, seed, method, hv, cached = f.result()
            print(
                f"{i}/{len(tasks)} {case} {seed} {method} HV={hv:.6f}{' cached' if cached else ''}",
                flush=True,
            )
    assert all(digest(ROOT / p) == sha for p, sha in hashes.items())
    missing = [
        m
        for m in full
        if any(
            not (out / "runs" / f"{r['instance_name']}__{s}__{m}.json").exists() for r in rows for s in SEEDS
        )
    ]
    if missing:
        print("Partial run saved. Methods still incomplete:", ", ".join(missing), flush=True)
        return
    summarize(out, rows, full)
    write_json(
        out / "artifact_manifest.json",
        {
            str(p.relative_to(out)).replace("\\", "/"): digest(p)
            for p in out.rglob("*")
            if p.is_file() and p.name != "artifact_manifest.json"
        },
    )
    print("Analysis written to", out, flush=True)


if __name__ == "__main__":
    main()
