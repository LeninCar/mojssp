"""Derive fixed budget shares from saved individual development trajectories."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from mojssp.project_paths import HISTORICAL_ROOT, campaign_path

METHODS = {'moead': 'MOEA/D', 'nsga2': 'NSGA-II', 'spea2': 'SPEA2'}


def budget_shares(gains, minimum=0.1):
    if set(gains) != set(METHODS):
        raise ValueError('Expected all three individual algorithms')
    if not math.isfinite(minimum) or not 0 <= minimum <= 1 / 3:
        raise ValueError('Minimum share must be between zero and one third')
    if any(not math.isfinite(value) or value < 0 for value in gains.values()):
        raise ValueError('Gains must be finite and nonnegative')
    total = sum(gains.values())
    proportions = {method: value / total if total else 1 / 3 for method, value in gains.items()}
    return {method: minimum + (1 - 3 * minimum) * value for method, value in proportions.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--minimum-share', type=float, default=0.1)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    budget_shares(dict.fromkeys(METHODS, 0), args.minimum_share)
    output = args.output_dir.resolve()
    if output.exists() or output.is_relative_to(HISTORICAL_ROOT):
        parser.error('Choose a new output directory outside historical results')
    source = campaign_path('portfolio')
    manifest_path = source / 'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    cases = [case for case in manifest['cases'] if case['split'] == 'development']
    seeds = manifest['seeds']['development']
    start, end = 50, 3000
    inputs = {str(manifest_path.relative_to(ROOT)): hashlib.sha256(manifest_path.read_bytes()).hexdigest()}
    runs, instances = [], []
    for case in cases:
        rates = {method: [] for method in METHODS}
        for seed in seeds:
            for method in METHODS:
                path = source / 'runs/development' / f"{case['name']}__{seed}__{method}.json"
                data = json.loads(path.read_text(encoding='utf-8'))
                if (data['case'], data['seed'], data['method'], data['split'], data['search_fe']) != (case['name'], seed, method, 'development', end):
                    raise ValueError(f'Unexpected run identity: {path}')
                blocks = data['blocks']
                if sum(block['evaluations_used'] for block in blocks) != end:
                    raise ValueError('Incorrect evaluation accounting')
                initial = next(block for block in blocks if block['fe'] == start)
                if initial['phase'] != 'warmup' or blocks[-1]['fe'] != end:
                    raise ValueError('Expected first 50 FE to be the saved warmup')
                gain = data['hv'] - initial['hv_after']
                if gain < -1e-12:
                    raise ValueError('Negative hypervolume improvement')
                rate = max(0., gain) / (end - start)
                rates[method].append(rate)
                inputs[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
                runs.append(dict(instance=case['name'], seed=seed, method=method,
                                 start_fe=start, end_fe=end, initial_hv=initial['hv_after'],
                                 final_hv=data['hv'], gain=gain, gain_per_fe=rate))
        means = {method: sum(values) / len(values) for method, values in rates.items()}
        proportions = budget_shares(means, minimum=0)
        for method in METHODS:
            instances.append(dict(instance=case['name'], method=method,
                                  mean_gain_per_fe=means[method], relative_gain=proportions[method]))
    if not cases or not seeds:
        raise ValueError('Empty development cohort')
    aggregate = {method: sum(row['relative_gain'] for row in instances if row['method'] == method) / len(cases)
                 for method in METHODS}
    shares = budget_shares(aggregate, args.minimum_share)
    output.mkdir(parents=True)
    for name, rows in [('individual_gains.csv', runs), ('relative_gains_by_instance.csv', instances)]:
        with (output / name).open('x', encoding='utf-8-sig', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    summary = dict(split='development', bases=len(cases), seeds_per_base=len(seeds), runs=len(runs),
                   start_fe=start, end_fe=end, minimum_share=args.minimum_share,
                   average_relative_gain=aggregate, budget_shares=shares, new_search_fe=0,
                   method='Average seeds within instance, normalize gains within instance, average instances equally, apply minimum shares',
                   limitation='Individual full-horizon productivity does not establish marginal portfolio benefit or optimal quotas',
                   input_sha256=inputs,
                   analysis_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    with (output / 'weights.json').open('x', encoding='utf-8') as stream:
        json.dump(summary, stream, indent=2, allow_nan=False)
    print(json.dumps({METHODS[method]: round(100 * share, 4) for method, share in shares.items()}))


if __name__ == '__main__':
    main()
