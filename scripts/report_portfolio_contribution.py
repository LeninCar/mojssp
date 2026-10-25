"""Offline development-only report. No optimization, no overwrite, no evaluator.

python -B -X utf8 scripts/report_portfolio_contribution.py --output NEW_DIRECTORY
"""
import argparse
import csv
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from mojssp.project_paths import PROJECT_ROOT, HISTORICAL_ROOT, campaign_path, input_path
from mojssp.contribution_report import ARMS, contribution_report
from mojssp.cooperation import ScaleAwareUCB
from mojssp.decoder import Decoder
from mojssp.evaluator import Evaluator
from mojssp.io import load_dzn
from mojssp.normalization import ObjectiveNormalizer, compute_instance_bounds
from mojssp.schedule_validator import ScheduleValidator
from mojssp.solution import Solution


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write_json(p, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('x', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, allow_nan=False)


def table(p, rows):
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('x', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--data-root', type=Path, default=PROJECT_ROOT,
                        help='Repository containing historical data/ entries')
    args = parser.parse_args()
    out = args.output.resolve()
    if out.is_relative_to(HISTORICAL_ROOT):
        parser.error("output must be outside results/historical")
    if out.exists():
        raise FileExistsError('Output directory must be new')
    campaign = campaign_path('portfolio')
    inputs = {}

    def read_json(p):
        inputs[str(p.relative_to(ROOT))] = digest(p)
        return json.loads(p.read_text(encoding='utf-8'))

    manifest = read_json(campaign / 'manifest.json')
    cases = [c for c in manifest['cases'] if c['split'] == 'development']
    assert len(cases) == 6 and manifest['budget'] == 3000 and manifest['block'] == 50
    recommendations, individuals, conservation, instance_rows = [], [], [], []
    reports = []
    # Hard stop if any accidental optimizer evaluation is introduced in this tool.
    with patch.object(Evaluator, 'evaluate', side_effect=AssertionError('New FE forbidden')):
        for case in cases:
            path = input_path(case['path'])
            assert digest(path) == case['sha256']
            inputs[str(path.relative_to(ROOT))] = digest(path)
            instance = load_dzn(path)
            normalizer = ObjectiveNormalizer(compute_instance_bounds(instance))
            instance_rows.append(dict(instance=case['name'], base_id=case['name'],
                                      configuration=f"{instance.num_jobs}x{instance.num_machines}",
                                      profile=case['config']['profile'], generator_seed=case['config']['seed'],
                                      source_file=str(path.relative_to(ROOT)), sha256=digest(path),
                                      split='development', cohort='loop_development'))
            for seed in manifest['seeds']['development']:
                source = campaign / 'runs/development' / f"{case['name']}__{seed}__scaled.json"
                run = read_json(source)
                before = json.dumps(run, sort_keys=True)
                assert run['case'] == case['name'] and run['seed'] == seed
                assert run['instance_sha256'] == case['sha256']
                report = contribution_report(run)
                for arm in ARMS:
                    for e in run['arm_archives'][arm]:
                        point = normalizer.normalize_tuple(tuple(e['objectives'][k] for k in ('makespan', 'tardiness', 'energy')))
                        assert max(abs(x-y) for x,y in zip(point, e['normalized'])) < 1e-12
                selector = ScaleAwareUCB(ARMS, window_size=10, exploration_factor=.07, seed=seed)
                for bi, block in enumerate(run['blocks']):
                    assert block['block_index'] == bi and block['budget_allocated'] == 50
                    assert block['fe'] == (bi+1)*50
                    if bi < 3:
                        assert block['arm_name'] == ARMS[bi] and block['phase'] == 'warmup'
                        selector.initialize_arm(block['arm_name'])
                    else:
                        assert selector.select_arm() == block['arm_name']
                        selector.update(block['arm_name'], block['reward'])
                for e in report['front']:
                    schedule = Decoder().decode(instance, Solution(tuple(e['sequence']), tuple(e['modes'])))
                    ScheduleValidator().validate(instance, schedule)
                    obj = dict(makespan=schedule.makespan,
                               tardiness=sum(max(0, schedule.get_job_completion_time(j.job_id)-j.due_date) for j in instance.jobs),
                               energy=sum(op.energy for op in schedule.operations))
                    assert all(abs(obj[k]-e['objectives'][k]) <= 1e-8 for k in obj)
                    e['schedule'] = [asdict(op) for op in schedule.operations]
                hv_standalone = {}
                for arm, method in zip(ARMS, ('moead', 'nsga2', 'spea2')):
                    standalone = read_json(campaign / 'runs/development' / f"{case['name']}__{seed}__{method}.json")
                    assert standalone['search_fe'] == 3000 and standalone['instance_sha256'] == case['sha256']
                    hv_standalone[arm] = standalone['hv']
                best = max(hv_standalone.values())
                winners = [a for a in ARMS if best-hv_standalone[a] <= report['tolerance']]
                info = dict(cohort='loop_development', split='development', instance=case['name'],
                            base_id=case['name'], seed=seed, budget=3000,
                            source_file=str(source.relative_to(ROOT)), source_sha256=inputs[str(source.relative_to(ROOT))])
                report.update(info)
                report['standalone_hv'] = hv_standalone
                report['standalone_winner_set'] = winners
                recommendations.append(dict(info, recommended_arm=report['recommended_arm'],
                    status=report['status'], global_hv=report['global_hv'],
                    global_genotypes=report['global_genotypes'], global_unique_objectives=report['global_unique_objectives'],
                    standalone_winner=';'.join(winners), agrees_standalone=report['recommended_arm'] in winners,
                    **{a+'_hv': hv_standalone[a] for a in ARMS},
                    **{a+'_mc': report['arms'][a]['mc'] for a in ARMS},
                    limitation='retained archive membership; recommendation is retrospective, not standalone superiority'))
                for arm in ARMS:
                    individuals.append(dict(info, arm=arm, **report['arms'][arm]))
                assert before == json.dumps(run, sort_keys=True)
                conservation.append(dict(info, selector_decisions_replayed=57, total_fe_checked=3000,
                    normalization_verified=True, schedules_verified=len(report['front']),
                    raw_hv_and_mc_match=True, input_unchanged=True, evaluator_calls=0,
                    limitation='No fresh optimizer rerun; source preservation and saved-feedback replay only'))
                reports.append(report)
    # Only after all runs validate do we create a new output tree.
    out.mkdir(parents=True, exist_ok=False)
    for report in reports:
        write_json(out / 'runs' / f"{report['instance']}__{report['seed']}.json", report)
    table(out / 'tables/recommendations.csv', recommendations)
    table(out / 'tables/individual_contributions.csv', individuals)
    table(out / 'tables/conservation.csv', conservation)
    table(out / 'tables/instances.csv', instance_rows)
    # Historical candidates: inspect development-only records; never infer portfolio
    # provenance from standalone fronts or compare campaigns as paired treatments.
    cfg = read_json(campaign_path('phase2') / 'budget_diagnostic/budget_config.json')
    selected_names = ('base_c01_5x5_b03', 'base_c01_5x5_b05_tard_med', 'base_c03_20x10_b04_btnk_high')
    candidates, known = [], []
    raw_fronts = campaign_path('phase2') / 'budget_diagnostic/budget_fronts.jsonl'
    inputs[str(raw_fronts.relative_to(ROOT))] = digest(raw_fronts)
    with raw_fronts.open(encoding='utf-8') as f:
        for line in f:
            d = json.loads(line)
            if d['instance_name'] in selected_names and d['budget'] == 3000 and d['method_type'] == 'standalone':
                known.append(dict(cohort='phase2_budget', split='development', instance=d['instance_name'],
                    base_id=d['base_id'], configuration=d['configuration'], profile=d['profile'],
                    seed=d['seed'], budget=3000, arm=d['algorithm'], hv=d['final_hv'],
                    source_file=str(raw_fronts.relative_to(ROOT)), source_run_id=d['run_id'],
                    limitation='historical source/seeding differs; not paired with a new scaled run'))
    for c in cfg['instances']:
        if c['instance_name'] not in selected_names:
            continue
        assert c['assigned_split'] == 'development'
        candidate_path = input_path(c['file_path'], args.data_root)
        exists = candidate_path.is_file()
        actual_hash = digest(candidate_path) if exists else None
        assert not exists or actual_hash == c['file_sha256']
        candidates.append(dict(c, resolved_path=str(candidate_path), exists=exists, actual_sha256=actual_hash,
                               scaled_3000_archives_available=False,
                               limitation='historical budget fronts have no per-arm portfolio genotypes/schedules'))
    table(out / 'tables/historical_standalones.csv', known)
    write_json(out / 'evidence/candidate_identity.json', candidates)
    write_json(out / 'evidence/input_hashes.json', inputs)
    write_json(out / 'evidence/protocol.json', dict(new_search_fe=0, reference=manifest['reference'],
        cases=[c['name'] for c in cases], seeds=manifest['seeds']['development'],
        budget=3000, block=50, population=30, selector='ScaleAwareUCB W=10 c=0.07',
        interpretation='retrospective final-archive attribution', holdout_opened=False,
        source_commit=subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT,text=True).strip()))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    (out / 'figures').mkdir()
    fig, axes = plt.subplots(2, 3, figsize=(15,8), sharey=True)
    for ax, case in zip(axes.flat, cases):
        for i, arm in enumerate(ARMS):
            vals = [r[arm+'_mc'] for r in recommendations if r['instance'] == case['name']]
            ax.bar(np.arange(3)+(i-1)*.25, vals, width=.25, label=arm)
        ax.set_title(case['name']); ax.set_xticks(range(3), [42,43,44]); ax.set_xlabel('Semilla nominal')
        ax.set_ylabel('Contribución marginal de HV (normalizado)')
    axes.flat[0].legend()
    fig.suptitle('UCB escalado · desarrollo · 3000 FE · 6 instancias × 3 semillas')
    fig.text(.02,.01,'Fuente: runs/development/*__scaled.json; unión de archivos locales retenidos; referencia (1.1,1.1,1.1).',fontsize=9)
    fig.tight_layout(rect=(0,.04,1,.95)); fig.savefig(out/'figures/contributions.png',dpi=170); plt.close(fig)
    fig, ax = plt.subplots(figsize=(10,6))
    matrix = np.array([[ARMS.index(r['recommended_arm']) if r['recommended_arm'] else -1
                        for r in recommendations if r['instance']==c['name']] for c in cases])
    im=ax.imshow(matrix,vmin=-.5,vmax=2.5,cmap=plt.get_cmap('viridis',3),aspect='auto')
    for i in range(6):
        for j in range(3): ax.text(j,i,ARMS[matrix[i,j]] if matrix[i,j]>=0 else 'Incierto',ha='center',va='center',color='white')
    ax.set_yticks(range(6),[c['name'] for c in cases]); ax.set_xticks(range(3),[42,43,44]); ax.set_xlabel('Semilla nominal');ax.set_ylabel('Instancia de desarrollo')
    ax.set_title('Mayor contribución marginal final · UCB escalado · 3000 FE\n6 instancias × 3 semillas; no implica mejor standalone')
    fig.text(.02,.01,'Fuente: tables/recommendations.csv; colores identifican brazos, sin escala de rendimiento.',fontsize=9)
    fig.tight_layout(rect=(0,.04,1,1));fig.savefig(out/'figures/recommendations.png',dpi=170);plt.close(fig)
    # Inputs are never written by this program.
    for rel, sha in inputs.items():
        assert digest(input_path(rel)) == sha
    print(json.dumps(dict(output=str(out),runs=len(reports),new_fe=0,
        recommendations={a:sum(r['recommended_arm']==a for r in recommendations) for a in ARMS},
        schedules=sum(r['global_genotypes'] for r in recommendations)),ensure_ascii=False))


if __name__ == '__main__':
    main()
