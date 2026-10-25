"""Run the main three algorithms or their portfolio on one instance."""
import argparse
from dataclasses import asdict
import json
import hashlib
import math
from fractions import Fraction
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from mojssp.io import load_dzn
from mojssp.fixed_budget import evaluation_quotas
from mojssp.project_paths import HISTORICAL_ROOT, PROJECT_ROOT
from mojssp.runner import run_phase2_portfolio_experiment, run_standalone_experiment


def positive_int(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError('must be positive')
    return number


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--instance', type=Path, required=True)
    parser.add_argument('--algorithm', choices=['moead', 'nsga2', 'spea2', 'portfolio'], required=True)
    parser.add_argument('--policy', choices=['uniform', 'sw_ucb', 'scaled', 'ph', 'adaptive', 'weighted', 'dynamic'])
    parser.add_argument('--round-size', type=positive_int, default=300)
    parser.add_argument('--minimum-share', type=float, default=.1)
    parser.add_argument('--arms', nargs='+', choices=['moead', 'nsga2', 'spea2'],
                        help='Portfolio members; defaults to all three')
    parser.add_argument('--weights', type=Path, help='Weighted-policy configuration; defaults to configs/budget_shares/development_wins.json')
    parser.add_argument('--window-size', type=positive_int, default=10)
    parser.add_argument('--exploration-factor', type=float, default=0.07)
    parser.add_argument('--ph-delta', type=float, default=0.001)
    parser.add_argument('--ph-threshold', type=float, default=0.05)
    parser.add_argument('--ph-min-instances', type=positive_int, default=5)
    parser.add_argument('--budget', type=positive_int, default=1000)
    parser.add_argument('--block-size', type=positive_int, default=50)
    parser.add_argument('--population-size', type=positive_int, default=30)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--output', type=Path, required=True, help='New JSON file; existing files are never overwritten')
    args = parser.parse_args()
    if args.algorithm != 'portfolio' and args.policy is not None:
        parser.error('--policy applies only to portfolio')
    if args.arms is not None and args.algorithm != 'portfolio':
        parser.error('--arms applies only to portfolio')
    if args.weights is not None and (args.algorithm != 'portfolio' or args.policy != 'weighted'):
        parser.error('--weights applies only to the weighted portfolio')
    if args.output.exists():
        parser.error('output already exists; choose a new file')
    if args.output.resolve().is_relative_to(HISTORICAL_ROOT):
        parser.error('new experiments must be outside results/historical')
    shares, weights_path = None, None
    if args.algorithm == 'portfolio' and args.policy == 'weighted':
        weights_path = args.weights or PROJECT_ROOT / 'configs/budget_shares/development_wins.json'
        weights_config = json.loads(weights_path.read_text(encoding='utf-8'))
        shares = {name: Fraction(str(value)) for name, value in weights_config['shares'].items()}
    instance = load_dzn(args.instance)
    history = ()
    if args.algorithm == 'portfolio':
        result, history = run_phase2_portfolio_experiment(
            instance, args.seed, total_budget=args.budget, block_size=args.block_size,
            population_size=args.population_size, policy=args.policy or 'sw_ucb',
            window_size=args.window_size, exploration_factor=args.exploration_factor,
            delta=args.ph_delta, threshold=args.ph_threshold,
            min_instances=args.ph_min_instances, budget_shares=shares,
            round_size=args.round_size, minimum_share=args.minimum_share,
            selected_arms=[{'moead': 'MOEA/D', 'nsga2': 'NSGA-II', 'spea2': 'SPEA2'}[name]
                           for name in args.arms] if args.arms is not None else None)
    else:
        result = run_standalone_experiment(
            instance, {'moead': 'MOEA/D', 'nsga2': 'NSGA-II', 'spea2': 'SPEA2'}[args.algorithm],
            args.seed, budget=args.budget, block_size=args.block_size,
            population_size=args.population_size)
    if result.evaluations_used != args.budget or not result.completed:
        raise RuntimeError('Run did not consume the requested evaluation budget')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(result)
    payload['config'] = {key: str(value) if isinstance(value, Path) else value
                         for key, value in vars(args).items() if key != 'output'}
    if args.algorithm == 'portfolio':
        payload['config']['policy'] = {'adaptive': 'sw_ucb'}.get(args.policy, args.policy) or 'sw_ucb'
        if args.policy == 'weighted':
            payload['config']['weights'] = str(weights_path.resolve())
            payload['config']['weights_sha256'] = hashlib.sha256(weights_path.read_bytes()).hexdigest()
            payload['config']['budget_shares'] = {name: float(value) for name, value in shares.items()}
            payload['config']['evaluation_quotas'] = evaluation_quotas(args.budget, shares)
            payload['config']['quota_basis'] = weights_config.get('basis')
            payload['config']['quota_scope'] = 'Total evaluations, including initialization and warmup'
            payload['config']['scheduling'] = 'After warmup, serve the least completed quota proportion; stable arm order breaks ties'
    payload['instance_sha256'] = hashlib.sha256(args.instance.read_bytes()).hexdigest()
    payload['source_sha256'] = {
        str(path.relative_to(PROJECT_ROOT)).replace('\\', '/'):
        hashlib.sha256(path.read_bytes()).hexdigest()
        for path in [*sorted((PROJECT_ROOT / 'src/mojssp').glob('*.py')), Path(__file__).resolve()]}
    payload['blocks'] = []
    for block in history:
        record = asdict(block)
        if record['ucb_indices'] is not None:
            record['ucb_indices'] = {key: value if math.isfinite(value) else None
                                      for key, value in record['ucb_indices'].items()}
        payload['blocks'].append(record)
    with args.output.open('x', encoding='utf-8') as output:
        json.dump(payload, output, ensure_ascii=False, indent=2, allow_nan=False)
    print(f'{result.algorithm}: FE={result.evaluations_used}, HV={result.hypervolume:.6f}; {args.output}')


if __name__ == '__main__':
    main()
