"""Frozen development pilot: three individuals and three portfolio policies."""
import argparse
from collections import defaultdict
from dataclasses import asdict
from fractions import Fraction
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import shutil
import sys
import time
from unittest.mock import patch
import csv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import numpy as np
from mojssp.evaluator import Evaluator
from mojssp.fixed_budget import evaluation_quotas
from mojssp.hypervolume import compute_hypervolume
from mojssp.io import load_dzn
from mojssp.normalization import ObjectiveNormalizer, compute_instance_bounds
from mojssp.project_paths import HISTORICAL_ROOT, campaign_path, input_path
from mojssp.runner import run_phase2_portfolio_experiment, run_standalone_experiment

METHODS = ['moead', 'nsga2', 'spea2', 'uniform', 'scaled', 'weighted']
INDIVIDUALS = {'moead': ('MOEA/D', 17), 'nsga2': ('NSGA-II', 29), 'spea2': ('SPEA2', 43)}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)


def write_csv(path, rows):
    with path.open('x', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def auc(checkpoints, budget):
    previous_fe, previous_hv, area = 0, 0., 0.
    for fe, hv in checkpoints:
        if fe <= previous_fe or hv < previous_hv - 1e-12:
            raise ValueError('Invalid hypervolume trajectory')
        area += (fe - previous_fe) * (hv + previous_hv) / 2
        previous_fe, previous_hv = fe, hv
    if previous_fe != budget:
        raise ValueError('Incomplete trajectory')
    return area / budget


def analyze(output, records):
    rows, blocks = [], []
    for record in records:
        rows.append({key: record[key] for key in ['case', 'master_seed', 'method', 'evaluations_used',
                                                  'hypervolume', 'auc_hv', 'runtime_seconds', 'archive_size']})
        for block in record['blocks']:
            blocks.append(dict(case=record['case'], master_seed=record['master_seed'], method=record['method'],
                               **{key: block[key] for key in ['block_index', 'arm_name', 'evaluations_used',
                                                              'phase', 'hv_before', 'hv_after', 'reward']}))
    write_csv(output/'runs.csv', rows)
    write_csv(output/'blocks.csv', blocks)
    cells = defaultdict(list)
    for row in rows:
        cells[row['case'], row['method']].append(row)
    per_instance = []
    for (case, method), group in sorted(cells.items()):
        per_instance.append(dict(case=case, method=method, seeds=len(group),
            **{f'mean_{metric}': float(np.mean([row[metric] for row in group]))
               for metric in ['hypervolume', 'auc_hv', 'runtime_seconds']},
            sd_hypervolume=float(np.std([row['hypervolume'] for row in group], ddof=1))))
    write_csv(output/'by_instance.csv', per_instance)
    summary = []
    for method in METHODS:
        group = [row for row in per_instance if row['method'] == method]
        summary.append(dict(method=method, bases=len(group),
            **{metric: float(np.mean([row[metric] for row in group]))
               for metric in ['mean_hypervolume', 'mean_auc_hv', 'mean_runtime_seconds']}))
    write_csv(output/'summary.csv', summary)
    index = {(row['case'], row['method']): row for row in per_instance}
    cases = sorted({row['case'] for row in per_instance})
    rng = np.random.default_rng(20261023)
    comparisons = []
    for control in METHODS[:-1]:
        for metric in ['hypervolume', 'auc_hv', 'runtime_seconds']:
            differences = np.array([index[case, 'weighted'][f'mean_{metric}'] -
                                    index[case, control][f'mean_{metric}'] for case in cases])
            samples = rng.choice(differences, size=(20000, len(cases)), replace=True).mean(axis=1)
            lo, hi = np.quantile(samples, [.025, .975])
            comparisons.append(dict(treatment='weighted', control=control, metric=metric, bases=len(cases),
                mean_difference=float(differences.mean()), bootstrap95_low=float(lo), bootstrap95_high=float(hi),
                positive_bases=int(sum(differences > 1e-12)), tied_bases=int(sum(abs(differences) <= 1e-12)),
                negative_bases=int(sum(differences < -1e-12))))
    write_csv(output/'comparisons.csv', comparisons)
    write_json(output/'validation.json', dict(passed=True, runs=len(records),
        actual_search_fe=sum(record['actual_evaluator_calls'] for record in records),
        expected_search_fe=324000, all_hv_recomputed=True, all_quotas_verified=True,
        inference='Exploratory development pilot; weights were learned on these same bases; bootstrap resamples six base-level means, not eighteen independent seeds',
        timing='Sequential execution; method order rotated by case and master seed; analysis is outside run timing'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if output.exists() or output.is_relative_to(HISTORICAL_ROOT):
        parser.error('Choose a new directory outside historical results')
    historical = json.loads((campaign_path('portfolio')/'manifest.json').read_text(encoding='utf-8'))
    cases = [case for case in historical['cases'] if case['split'] == 'development']
    assert len(cases) == 6
    seeds = historical['seeds']['development']
    assert seeds == [42, 43, 44]
    weights_file = ROOT/'configs/budget_shares/development_wins.json'
    weights = json.loads(weights_file.read_text(encoding='utf-8'))
    shares = {name: Fraction(value) for name, value in weights['shares'].items()}
    quotas = evaluation_quotas(3000, shares)
    source_files = [*sorted((ROOT/'src/mojssp').glob('*.py')), Path(__file__).resolve()]
    sources = {str(path.relative_to(ROOT)).replace('\\', '/'): digest(path) for path in source_files}
    output.mkdir(parents=True)
    for case in cases:
        original = input_path(case['path'])
        assert digest(original) == case['sha256']
        destination = output/'instances'/f"{case['name']}.dzn"
        destination.parent.mkdir(exist_ok=True)
        shutil.copy2(original, destination)
    for path in source_files:
        destination = output/'code'/path.relative_to(ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
    write_json(output/'weights.json', weights)
    config = dict(cases=[dict(name=case['name'], sha256=case['sha256']) for case in cases],
        split='development', master_seeds=seeds, methods=METHODS, budget=3000, block_size=50,
        population_size=30, window_size=10, exploration_factor=.07, reference=[1.1,1.1,1.1],
        weighted_quotas=quotas, weights_sha256=digest(weights_file), source_sha256=sources,
        seed_derivation='Individual arm seeds match their portfolio seeds: (master_seed*10007+offset) mod (2**31-1); offsets MOEA/D=17, NSGA-II=29, SPEA2=43',
        primary_comparison='weighted minus MOEA/D final HV; progress and runtime secondary',
        expected_runs=108, expected_search_fe=324000, statistical_unit='instance/base, average three seeds first',
        scope='Development only; no confirmatory claim; no historical results concatenated',
        runtime_versions={name: importlib.metadata.version(name) for name in ['numpy','pytest']})
    write_json(output/'config.json', config)
    records = []
    started = time.perf_counter()
    original_evaluate = Evaluator.evaluate
    for case_index, case in enumerate(cases):
        instance = load_dzn(output/'instances'/f"{case['name']}.dzn")
        normalizer = ObjectiveNormalizer(compute_instance_bounds(instance))
        for seed_index, master_seed in enumerate(seeds):
            shift = (case_index * len(seeds) + seed_index) % len(METHODS)
            order = METHODS[shift:] + METHODS[:shift]
            for method in order:
                assert all(digest(ROOT/rel) == sha for rel, sha in sources.items()), 'Code changed during pilot'
                calls = 0
                def counted(evaluator, *a, **kw):
                    nonlocal calls
                    calls += 1
                    return original_evaluate(evaluator, *a, **kw)
                with patch.object(Evaluator, 'evaluate', counted):
                    if method in INDIVIDUALS:
                        name, offset = INDIVIDUALS[method]
                        arm_seed = (master_seed*10007+offset) % (2**31-1)
                        result = run_standalone_experiment(instance, name, arm_seed, 3000, 50, 30)
                        history = ()
                    else:
                        result, history = run_phase2_portfolio_experiment(instance, master_seed,
                            total_budget=3000, block_size=50, population_size=30, policy=method,
                            budget_shares=shares if method == 'weighted' else None)
                assert calls == result.evaluations_used == 3000 and result.completed
                hv = compute_hypervolume([normalizer.normalize_tuple(point) for point in result.pareto_front])
                assert math.isclose(hv, result.hypervolume, rel_tol=0, abs_tol=1e-12)
                if method == 'weighted':
                    assert {name: allocation.evaluations_assigned for name, allocation in result.arm_allocations.items()} == quotas
                record = asdict(result)
                record.update(case=case['name'], master_seed=master_seed, method=method,
                              actual_evaluator_calls=calls, auc_hv=auc(result.checkpoints,3000), blocks=[])
                for block in history:
                    row = asdict(block)
                    if row['ucb_indices'] is not None:
                        row['ucb_indices'] = {name: value if math.isfinite(value) else None for name,value in row['ucb_indices'].items()}
                    record['blocks'].append(row)
                write_json(output/'runs'/f"{case['name']}__{master_seed}__{method}.json", record)
                records.append(record)
                print(f"{len(records)}/108 {case['name']} seed={master_seed} {method}: HV={hv:.6f} time={result.runtime_seconds:.2f}s elapsed={time.perf_counter()-started:.1f}s", flush=True)
    assert len(records) == 108 and sum(record['actual_evaluator_calls'] for record in records) == 324000
    analyze(output, records)
    print('Pilot complete and validated.', flush=True)


if __name__ == '__main__':
    main()
