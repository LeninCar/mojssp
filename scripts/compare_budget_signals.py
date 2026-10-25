"""Compare prior-budget signals using saved individual development runs only."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
from statistics import mean

from derive_budget_weights import METHODS, ROOT, budget_shares, campaign_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if output.exists() or output.is_relative_to(ROOT / 'results/historical'):
        parser.error('Choose a new output directory outside historical results')
    source = campaign_path('portfolio')
    manifest_path = source / 'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    cases = [case['name'] for case in manifest['cases'] if case['split'] == 'development']
    seeds = manifest['seeds']['development']
    data, inputs = {}, {}
    for case in cases:
        for seed in seeds:
            for method in METHODS:
                path = source / 'runs/development' / f'{case}__{seed}__{method}.json'
                run = json.loads(path.read_text(encoding='utf-8'))
                assert (run['split'], run['method'], run['search_fe']) == ('development', method, 3000)
                endpoints = {block['fe']: block['hv_after'] for block in run['blocks']}
                assert all(point in endpoints for point in [50, 1000, 3000])
                data[case, seed, method] = endpoints
                inputs[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    signals = {name: dict.fromkeys(METHODS, 0.) for name in
               ['gain_50_3000', 'late_gain_1000_3000', 'final_hv', 'wins_by_base', 'wins_by_seed']}
    details, endpoints_table = [], []
    tolerance = 1e-12
    for case in cases:
        endpoints = {method: {cut: mean(data[case, seed, method][cut] for seed in seeds)
                             for cut in [50, 1000, 3000]} for method in METHODS}
        metrics = {
            'gain_50_3000': {m: max(0., endpoints[m][3000] - endpoints[m][50]) / 2950 for m in METHODS},
            'late_gain_1000_3000': {m: max(0., endpoints[m][3000] - endpoints[m][1000]) / 2000 for m in METHODS},
            'final_hv': {m: endpoints[m][3000] for m in METHODS},
        }
        for name, scores in metrics.items():
            proportions = budget_shares(scores, minimum=0.)
            for method in METHODS:
                signals[name][method] += proportions[method] / len(cases)
        final = metrics['final_hv']
        best = max(final.values())
        winners = [method for method in METHODS if best - final[method] <= tolerance]
        for method in winners:
            signals['wins_by_base'][method] += 1 / len(winners) / len(cases)
        ordered = sorted(final.values(), reverse=True)
        for method in METHODS:
            details.append(dict(instance=case, method=method, final_mean_hv=final[method],
                                gap_to_best=best-final[method], winner=method in winners,
                                gap_best_vs_second=ordered[0]-ordered[1]))
            for cut in [50, 1000, 3000]:
                endpoints_table.append(dict(instance=case, method=method, fe=cut, mean_hv=endpoints[method][cut]))
        for seed in seeds:
            finals = {method: data[case, seed, method][3000] for method in METHODS}
            top = max(finals.values())
            winners = [method for method in METHODS if top-finals[method] <= tolerance]
            for method in winners:
                signals['wins_by_seed'][method] += 1 / len(winners) / len(seeds) / len(cases)
    weights = {name: budget_shares(scores, minimum=.1) for name, scores in signals.items()}
    assert all(abs(sum(shares.values())-1)<1e-12 for shares in weights.values())
    output.mkdir(parents=True)
    for name, rows in [('final_quality_by_instance.csv', details), ('mean_trajectory_endpoints.csv', endpoints_table)]:
        with (output/name).open('x', encoding='utf-8-sig', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    summary = dict(split='development', bases=len(cases), seeds=len(seeds), runs=len(data),
                   minimum_share=.1, signals=signals, candidate_budget_shares=weights,
                   new_search_fe=0, numerical_tie_tolerance=tolerance,
                   limitations=['Signals are exploratory on six development bases; no portfolio benefit has been measured',
                                'Seed-level wins are clustered within bases, not independent instances',
                                'Win frequency ignores winning margins; final-HV ratios may conceal meaningful small differences',
                                'All signals use a 3000-FE individual horizon; optimal shares can depend on the target budget'],
                   manifest_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                   input_sha256=inputs, analysis_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    with (output/'signal_comparison.json').open('x', encoding='utf-8') as stream:
        json.dump(summary, stream, indent=2, allow_nan=False)
    print(json.dumps({name: {METHODS[m]: round(100*s, 2) for m,s in values.items()}
                      for name,values in weights.items()}, indent=2))
    print('Per-base final winners:', [(row['instance'], METHODS[row['method']], round(row['gap_best_vs_second'], 6))
                                      for row in details if row['winner']])


if __name__ == '__main__':
    main()
