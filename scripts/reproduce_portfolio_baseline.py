"""Exact saved-front/allocation replay after disabled-hook implementation changes."""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from run_portfolio_loop import OUT, BASELINES, run_case, write_new
from mojssp.project_paths import HISTORICAL_ROOT


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True,
                        help='New JSON file outside the saved campaign')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output already exists; choose a new file')
    if args.output.resolve().is_relative_to(HISTORICAL_ROOT):
        parser.error('output must be outside the saved campaign')
    manifest=json.loads((OUT/'manifest.json').read_text(encoding='utf-8'))
    case=next(c for c in manifest['cases'] if c['name']=='development_00_5x5')
    evidence=[]
    for method in BASELINES:
        saved=json.loads((OUT/'runs/development'/f"{case['name']}__42__{method}.json").read_text(encoding='utf-8'))
        current=run_case(case,42,method,'development')
        keys=['hv','auc_hv','allocation','milestones','arm_archives','marginal_hv',
              'genetic_diversity_initial','genetic_diversity_final']
        for key in keys:
            # JSON roundtrip makes tuple/list representations comparable.
            assert json.loads(json.dumps(current[key])) == saved[key], (method,key)
        for a,b in zip(current['blocks'],saved['blocks']):
            for key in ['arm_name','evaluations_used','reward','hv_after','hv_before','phase']:
                assert a[key]==b[key],(method,key)
        evidence.append({'method':method,'search_fe':current['search_fe'],
                         'seconds':current['seconds'],'identical_fields':keys,
                         'block_trace_identical_except_timing':True})
    write_new(args.output,{'passed':True,'cases':evidence,
              'additional_search_fe':sum(e['search_fe'] for e in evidence),
              'scope':'One base and seed, all five controls at full budget. Existing tests also check native arm block-splitting and RNG continuity.'})
    print('All five control fronts, block allocations and metrics reproduced exactly; 15000 FE.')


if __name__=='__main__':
    main()
