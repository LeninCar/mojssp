"""Complete the development table of BLMR pairs and policies (post-holdout, descriptive only).

The development bank (six bases, seeds 100-300, 3000 FE) never ran SW-UCB and Page-Hinkley with
MOEA/D + BLMR or NSGA-II + BLMR, nor uniform, SW-UCB and Page-Hinkley with the quartet. This runs those
seven configurations with the same code path as the original campaigns
(regional_policy_integration, regional_five_policies_mopso, regional_compositions_two_banks), after
checking that it reproduces saved runs of those campaigns exactly.

Run from the project root:
    $env:PYTHONPATH = "src"
    .venv\\Scripts\\python.exe scripts\\campaigns\\run_policy_completion.py --workers 6
"""

import argparse
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd

from mojssp.experiments.common import ROOT, write_json
from mojssp.model.io import load_dzn
from mojssp.portfolio.regional_portfolio import run_regional_policy_experiment

EXP = ROOT / "results/experiments"
INSTANCES = EXP / "weighted_pilot_development_20261023/instances"
CASES = [
    "development_00_5x5",
    "development_01_10x10",
    "development_02_20x10",
    "development_03_10x20",
    "development_04_20x20",
    "development_05_30x20",
]
SEEDS = [100, 200, 300]
QUARTET = ["MOEA/D", "NSGA-II", "SPEA2", "RegionExplorer"]
CONFIGS = {
    "moead_regional_sw_ucb": (["MOEA/D", "RegionExplorer"], "sw_ucb"),
    "moead_regional_ph": (["MOEA/D", "RegionExplorer"], "ph"),
    "nsga2_regional_sw_ucb": (["NSGA-II", "RegionExplorer"], "sw_ucb"),
    "nsga2_regional_ph": (["NSGA-II", "RegionExplorer"], "ph"),
    "quartet_regional_uniform": (QUARTET, "uniform"),
    "quartet_regional_sw_ucb": (QUARTET, "sw_ucb"),
    "quartet_regional_ph": (QUARTET, "ph"),
}
# Saved runs the current code must reproduce before anything new is trusted
REPRODUCE = [
    ("regional_five_policies_mopso_20261024/runs", "spea2_regional_sw_ucb", ["SPEA2", "RegionExplorer"], "sw_ucb"),
    ("regional_five_policies_mopso_20261024/runs", "spea2_regional_ph", ["SPEA2", "RegionExplorer"], "ph"),
    ("regional_policy_integration_development_20261023/assignment/runs", "moead_regional_uniform",
     ["MOEA/D", "RegionExplorer"], "uniform"),
    ("regional_compositions_two_banks_20261024/development/runs", "quartet_regional_scaled", QUARTET, "scaled"),
]


def run_one(task):
    case, seed, method, out = task
    path = Path(out) / "runs" / f"{case}__{seed}__{method}.json"
    if path.exists():
        r = json.loads(path.read_text())
    else:
        arms, policy = CONFIGS[method]
        r = run_regional_policy_experiment(load_dzn(INSTANCES / f"{case}.dzn"), seed, arms, policy, False, 3000)
        r.update(case=case, master_seed=seed, method=method)
        write_json(path, r)
    return dict(case=case, master_seed=seed, method=method, hypervolume=r["hypervolume"],
                evaluations_used=r["evaluations_used"], runtime_seconds=r["runtime_seconds"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=str(EXP / "policy_completion_development_20261103"))
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    out = Path(args.output_dir)
    (out / "runs").mkdir(parents=True, exist_ok=True)

    for folder, method, arms, policy in REPRODUCE:
        saved = json.loads((EXP / folder / f"development_00_5x5__100__{method}.json").read_text())
        new = run_regional_policy_experiment(load_dzn(INSTANCES / "development_00_5x5.dzn"), 100, arms, policy, False, 3000)
        assert abs(new["hypervolume"] - saved["hypervolume"]) < 1e-12, method
        assert sorted(map(tuple, new["pareto_front"])) == sorted(map(tuple, saved["pareto_front"])), method

    config_path = out / "config.json"
    if not config_path.exists():
        write_json(config_path, dict(
            cases=CASES, seeds=SEEDS, budget=3000, block_size=50, population_size=30,
            configurations={m: dict(arms=a, policy=p) for m, (a, p) in CONFIGS.items()},
            reproduced_before_running=[m for _, m, _, _ in REPRODUCE],
            scope="Run on 2026-11-03, after the holdout evaluation (2026-10-24), only to complete the "
                  "development table of BLMR pairs and policies; it played no part in selecting PS-MB.",
        ))
    tasks = [(c, s, m, str(out)) for m in CONFIGS for c in CASES for s in SEEDS]
    with ProcessPoolExecutor(args.workers) as pool:
        rows = list(pool.map(run_one, tasks))
    runs = pd.DataFrame(rows)
    assert (runs.evaluations_used == 3000).all() and len(runs) == len(tasks)
    runs.to_csv(out / "runs.csv", index=False)
    by_instance = runs.groupby(["case", "method"]).hypervolume.mean().rename("mean_hypervolume").reset_index()
    by_instance.to_csv(out / "by_instance.csv", index=False)
    summary = by_instance.groupby("method").mean_hypervolume.mean().rename("mean_hypervolume")
    summary.to_csv(out / "summary.csv")
    print(summary.round(4).to_string())


if __name__ == "__main__":
    main()
