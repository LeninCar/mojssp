"""Export the per-run JSONs of the final campaigns to one compact gzip JSON Lines file each.

Keeps what the thesis figures need (HV curve, arm per block, allocation and the
deduplicated Pareto front objectives) and drops genotypes and traces, so the
files fit in git and the figures can be made without the local runs/ folders.
"""

import argparse
import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAMPAIGNS = [
    'holdout_early_moead_600_20261024',
    'holdout_policy_comparison_20261025',
    'cut_sweep_development_20261028',
]
KEYS = ['case', 'master_seed', 'method', 'composition', 'dimension', 'hypervolume', 'auc_hv',
        'runtime_seconds', 'evaluations_used', 'allocations']


def compact(run):
    row = {k: run[k] for k in KEYS if k in run}
    row['checkpoints'] = [[int(fe), round(hv, 6)] for fe, hv in run.get('checkpoints', [])]
    row['block_arms'] = [b['arm_name'] for b in run.get('blocks', [])]
    row['front'] = sorted({tuple(p) for p in run.get('pareto_front', [])})
    return row


def export(campaign):
    folder = ROOT / 'results' / 'experiments' / campaign
    paths = sorted((folder / 'runs').glob('*.json'))
    if not paths:
        print(f'{campaign}: sin carpeta runs/, se omite')
        return
    target = folder / 'compact_runs.jsonl.gz'
    with gzip.open(target, 'wt', encoding='utf-8') as out:
        for path in paths:
            out.write(json.dumps(compact(json.loads(path.read_text())), separators=(',', ':')) + '\n')
    print(f'{campaign}: {len(paths)} corridas -> {target.relative_to(ROOT)} ({target.stat().st_size / 1e6:.1f} MB)')


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('campaigns', nargs='*', default=CAMPAIGNS)
    for campaign in parser.parse_args().campaigns:
        export(campaign)


if __name__ == '__main__':
    main()
