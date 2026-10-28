"""Final holdout evaluation of the frozen early_moead_600 portfolio on the 80 reserved expanded_200 instances."""

import argparse, csv, json, subprocess
from pathlib import Path
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from unittest.mock import patch
import numpy as np
from scipy.stats import wilcoxon
from mojssp.experiments.analysis import analyze
from mojssp.experiments.common import ROOT, auc, digest, independent_hv, write_csv, write_json
from mojssp.experiments.methods import run_method
from mojssp.model.io import load_dzn
from mojssp.model.evaluator import Evaluator
from mojssp.metrics.normalization import ObjectiveNormalizer, compute_instance_bounds

SPLIT = ROOT / "data/generated/expanded_200/experimental_split.csv"
SEEDS = [100, 200, 300, 400, 500]
CANDIDATE = "early_moead_600"
CONTROLS = [
    "explorer_solo",
    "passive",
    "moead",
    "nsga2_individual",
    "spea2_individual",
    "nsga2_ls_individual",
    "mopso_individual",
]
RULE = (
    "Fixed before the holdout: early_moead_600 is declared better than the best individual only if its mean HV "
    "(five-seed instance means, then equal instance weights) exceeds explorer_solo and the current dynamic pair "
    "(passive). Superiority is called statistically supported only if the instance-level bootstrap 95% interval "
    "of the difference against explorer_solo excludes zero. Size and profile breakdowns and the Wilcoxon test are "
    "descriptive and do not change the decision."
)


def execute(task):
    out, case, seed, method = task
    path = out / "runs" / f"{case}__{seed}__{method}.json"
    if path.exists():
        r = json.loads(path.read_text())
        return case, seed, method, r["hypervolume"], True
    instance = load_dzn(ROOT / "data/generated/expanded_200" / f"{case}.dzn")
    original = Evaluator.evaluate
    calls = 0

    def counted(self, *a, **kw):
        nonlocal calls
        calls += 1
        return original(self, *a, **kw)

    with patch.object(Evaluator, "evaluate", counted):
        r = run_method(instance, seed, method)
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
        actual_evaluator_calls=calls,
        auc_hv=auc(r["checkpoints"], 3000),
        origin="new",
    )
    r.pop("front_entries", None)
    write_json(path, r)
    return case, seed, method, r["hypervolume"], False


def bootstrap(delta, seed=20261024):
    rng = np.random.default_rng(seed)
    lo, hi = np.quantile(rng.choice(delta, size=(20000, len(delta))).mean(axis=1), [0.025, 0.975])
    return float(lo), float(hi)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--workers", type=int, choices=range(1, 15), default=14)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    out = args.output_dir.resolve()
    if not out.is_relative_to(ROOT / "results/experiments"):
        parser.error("Choose a folder inside results/experiments")
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
        parser.error("Commit the frozen code and instances before the holdout run")
    rows = [
        r for r in csv.DictReader(open(SPLIT, encoding="utf-8-sig")) if r["assigned_split"] == "holdout_test"
    ]
    assert len(rows) == 80
    for r in rows:
        assert digest(ROOT / r["file_path"]) == r["file_sha256"]
    files = sorted((ROOT / "src/mojssp").rglob("*.py")) + sorted((ROOT / "scripts").rglob("*.py"))
    hashes = {str(p.relative_to(ROOT)).replace("\\", "/"): digest(p) for p in files}
    config = dict(
        frozen_commit=head,
        split=str(SPLIT.relative_to(ROOT)).replace("\\", "/"),
        split_sha256=digest(SPLIT),
        instances=[
            dict(
                name=r["instance_name"],
                dimensions=r["dimensions"],
                profile=r["profile"],
                sha256=r["file_sha256"],
            )
            for r in rows
        ],
        seeds=SEEDS,
        budget=3000,
        population_size=30,
        block_size=50,
        candidate=CANDIDATE,
        candidate_definition="MOEA/D + BLMR v1, dynamic rounds of 300 FE with 10% floor for the "
        "first 600 FE, then every round to BLMR (exclusive_arm=RegionExplorer, exclusive_after=600)",
        controls=CONTROLS,
        decision_rule=RULE,
        source_sha256=hashes,
        selection_history=[
            "allocation_variants_moead_blmr_20261024",
            "multiea_selection_moead_blmr_20261024",
        ],
        scope="First and only use of the 80 holdout_test instances; nothing is tuned after this run",
    )
    if out.exists():
        if not args.resume:
            parser.error("Output exists; pass --resume to continue the same frozen run")
        previous = json.loads((out / "config.json").read_text())
        assert previous["frozen_commit"] == head and previous["source_sha256"] == hashes
    else:
        (out / "runs").mkdir(parents=True)
        write_json(out / "config.json", config)
    size = lambda r: int(r["total_operations"])
    tasks = [
        (out, r["instance_name"], s, m)
        for r in sorted(rows, key=size, reverse=True)
        for s in SEEDS
        for m in [CANDIDATE] + CONTROLS
    ]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for i, f in enumerate(as_completed([pool.submit(execute, t) for t in tasks]), 1):
            case, seed, method, hv, cached = f.result()
            print(
                f"{i}/{len(tasks)} {case} {seed} {method} HV={hv:.6f}{' cached' if cached else ''}",
                flush=True,
            )
    assert all(digest(ROOT / p) == sha for p, sha in hashes.items())
    records = [json.loads(p.read_text()) for p in (out / "runs").glob("*.json")]
    assert len(records) == len(tasks)
    analyze(out, records, [CANDIDATE], CONTROLS)
    cell = defaultdict(list)
    for r in records:
        cell[r["case"], r["method"]].append(r["hypervolume"])
    meta = {r["instance_name"]: r for r in rows}
    cases = sorted(meta)
    inst = {(c, m): float(np.mean(cell[c, m])) for c in cases for m in [CANDIDATE] + CONTROLS}
    means = {m: float(np.mean([inst[c, m] for c in cases])) for m in [CANDIDATE] + CONTROLS}
    versus = {}
    for m in CONTROLS:
        delta = np.array([inst[c, CANDIDATE] - inst[c, m] for c in cases])
        lo, hi = bootstrap(delta)
        versus[m] = dict(
            mean_difference=float(delta.mean()),
            bootstrap95=[lo, hi],
            wins=int((delta > 1e-12).sum()),
            losses=int((delta < -1e-12).sum()),
            wilcoxon_p=float(wilcoxon(delta).pvalue),
        )
    breakdown = []
    for key in ["dimensions", "profile"]:
        for value in sorted({meta[c][key] for c in cases}):
            group = [c for c in cases if meta[c][key] == value]
            for m in ["explorer_solo", "passive", "moead"]:
                delta = np.array([inst[c, CANDIDATE] - inst[c, m] for c in group])
                breakdown.append(
                    dict(
                        by=key,
                        value=value,
                        control=m,
                        instances=len(group),
                        mean_difference=float(delta.mean()),
                        wins=int((delta > 1e-12).sum()),
                        losses=int((delta < -1e-12).sum()),
                    )
                )
    write_csv(out / "breakdown.csv", breakdown)
    better = means[CANDIDATE] > means["explorer_solo"] and means[CANDIDATE] > means["passive"]
    write_json(
        out / "decision.json",
        dict(
            means=means,
            decision_rule=RULE,
            candidate_better_than_best_individual=better,
            statistically_supported=better and versus["explorer_solo"]["bootstrap95"][0] > 0,
            beats_every_control=all(means[CANDIDATE] > means[m] for m in CONTROLS),
            versus=versus,
            frozen_commit=head,
        ),
    )
    write_json(
        out / "artifact_manifest.json",
        {
            str(p.relative_to(out)).replace("\\", "/"): digest(p)
            for p in out.rglob("*")
            if p.is_file() and p.name != "artifact_manifest.json"
        },
    )


if __name__ == "__main__":
    main()
