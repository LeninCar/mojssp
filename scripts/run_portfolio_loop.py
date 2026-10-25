"""Prospective, append-only portfolio experiments; no final-test access.

Run from any cwd: python scripts/run_portfolio_loop.py --phase baseline
Other phases: prepare, guidance, scaled, <registered later treatments>.
Existing completed cases are never overwritten. Failures retain .failed.json.
"""
import argparse
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import platform
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'scripts')]
from generate_mojssp_instances import InstanceConfig, generate_single_instance
from mojssp.arms import NSGA2Arm
from mojssp.dmab import RoundRobinSelector, SlidingWindowUCB
from mojssp.evaluator import Evaluator
from mojssp.hypervolume import compute_archive_hypervolume
from mojssp.io import load_dzn
from mojssp.moead import MOEADArm
from mojssp.normalization import ObjectiveNormalizer, compute_instance_bounds
from mojssp.orchestrator import AdaptivePortfolioOrchestrator
from mojssp.pareto_archive import ParetoArchive
from mojssp.portfolio import Portfolio
from mojssp.provenance import compute_genotype_id
from mojssp.reward import HypervolumeRewardTracker
from mojssp.spea2 import SPEA2Arm

from mojssp.project_paths import campaign_path, input_path

OUT = campaign_path('portfolio')
NAMES = ('MOEA/D', 'NSGA-II', 'SPEA2')
BASELINES = ['moead', 'nsga2', 'spea2', 'uniform', 'adaptive']
PHASES = {'baseline': BASELINES, 'guidance': ['guidance'], 'scaled': ['scaled'],
          'combined': ['combined']}
BUDGET = 3000
BLOCK = 50


def write_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as f:
        json.dump(value, f, indent=2, ensure_ascii=False, allow_nan=False)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare():
    manifest_path = OUT / 'manifest.json'
    if manifest_path.exists():
        return json.loads(manifest_path.read_text(encoding='utf-8'))
    cases = []
    sizes = [(5, 5), (10, 10), (20, 10), (10, 20), (20, 20), (30, 20), (40, 20), (50, 50)]
    profiles = [{}, {'tardiness_profile': 'tard_high'}, {'energy_profile': 'nrg_strong'},
                {'bottleneck_profile': 'btnk_high'}, {'duration_profile': 'dur_high'},
                {'release_profile': 'rel_high'}, {'energy_profile': 'nrg_strong'},
                {'tardiness_profile': 'tard_high'}]
    for split, offset, count in [('development', 81000, 6), ('confirmation', 91000, 8)]:
        for i, (nj, nm) in enumerate(sizes[:count]):
            name = f'{split}_{i:02}_{nj}x{nm}'
            cfg = InstanceConfig(name=name, group='loop', profile=str(profiles[i]),
                                 num_jobs=nj, num_machines=nm, seed=offset+i, **profiles[i])
            content, _ = generate_single_instance(cfg)
            p = OUT / 'instances' / f'{name}.dzn'
            p.parent.mkdir(parents=True, exist_ok=True)
            with p.open('x', encoding='utf-8') as f:
                f.write(content)
            cases.append({'name': name, 'split': split, 'path': str(p.relative_to(ROOT)),
                          'sha256': digest(p), 'config': asdict(cfg)})
    manifest = {'cases': cases, 'seeds': {'development': [42, 43, 44],
                                       'confirmation': [142, 143, 144]},
                'budget': BUDGET, 'block': BLOCK, 'population': 30,
                'reference': [1.1, 1.1, 1.1], 'max_search_fe': 1200000,
                'max_experiment_seconds': 2700, 'python': platform.python_version(),
                'platform': platform.platform(),
                'protocol_sha256': digest(OUT / 'protocol.md')}
    write_new(manifest_path, manifest)
    return manifest


def genotype_distance(a, b):
    n = len(a.sequence)
    return (sum(x != y for x, y in zip(a.sequence, b.sequence)) +
            sum(x != y for x, y in zip(a.modes, b.modes))) / (2*n)


def population(arm):
    if isinstance(arm, MOEADArm):
        return [s.solution for s in arm.subproblems]
    if isinstance(arm, SPEA2Arm):
        return [s.solution for s in arm.archive_population]
    return [s.solution for s in arm._population]


def genetic_diversity(arm):
    sols = population(arm)
    ds = [genotype_distance(a, b) for i, a in enumerate(sols) for b in sols[i+1:]]
    return sum(ds)/len(ds) if ds else 0.0


def entries_json(archive, normalizer):
    return [{'id': compute_genotype_id(e.solution), 'sequence': e.solution.sequence,
             'modes': e.solution.modes, 'objectives': asdict(e.objectives),
             'normalized': normalizer.normalize_tuple(e.objectives)} for e in archive.entries]


def make_arms(instance, seed, method):
    args = dict(instance=instance, population_size=30, max_evaluations=BUDGET)
    arms = [MOEADArm(**args, seed=seed),
            NSGA2Arm(**args, seed=seed+1, max_generations=None),
            SPEA2Arm(**args, seed=seed+2, archive_size=30)]
    if method in BASELINES[:3]:
        return [arms[BASELINES.index(method)]]
    return arms


def source_hashes():
    paths = list((ROOT / 'src' / 'mojssp').glob('*.py')) + [Path(__file__)]
    return {str(p.relative_to(ROOT)): digest(p) for p in paths}


def run_case(case, seed, method, split):
    path = input_path(case['path'])
    assert digest(path) == case['sha256']
    instance = load_dzn(path)
    normalizer = ObjectiveNormalizer(compute_instance_bounds(instance))
    arms = make_arms(instance, seed, method)
    portfolio = Portfolio(arms)
    if method == 'uniform' or len(arms) == 1:
        selector = RoundRobinSelector(portfolio.arm_names)
    elif method in ('scaled', 'combined'):
        from mojssp.cooperation import ScaleAwareUCB
        selector = ScaleAwareUCB(portfolio.arm_names, window_size=10,
                                 exploration_factor=.07, seed=seed)
    else:
        selector = SlidingWindowUCB(portfolio.arm_names, window_size=10,
                                    exploration_factor=.07, seed=seed)
    orchestrator = AdaptivePortfolioOrchestrator(
        portfolio, selector, HypervolumeRewardTracker(normalizer))
    replay = None
    guidance = None
    if method in ('guidance', 'combined'):
        if method == 'guidance':
            control = OUT / 'runs' / split / f"{case['name']}__{seed}__adaptive.json"
            replay = json.loads(control.read_text(encoding='utf-8'))['blocks']
        from mojssp.cooperation import ArchiveGuidance
        guidance = ArchiveGuidance(instance, normalizer)
        for arm in arms:
            arm.set_archive_guidance(guidance)
    blocks, first_seen, initial_diversity, milestones = [], {}, {}, {}
    actual_fe = 0
    original_evaluate = Evaluator.evaluate

    def counted(evaluator, *args, **kwargs):
        nonlocal actual_fe
        actual_fe += 1
        return original_evaluate(evaluator, *args, **kwargs)

    started = time.perf_counter()
    with patch.object(Evaluator, 'evaluate', counted):
        for bi in range(BUDGET // BLOCK):
            t0 = time.perf_counter()
            if replay:
                name = replay[bi]['arm_name']
            elif bi < len(arms):
                name = portfolio.arm_names[bi]
            else:
                name = selector.select_arm()
            arm = portfolio.get_arm(name)
            donor = None
            if guidance:
                donor = guidance.prepare(arm, portfolio.global_archive, first_seen)
            if bi < len(arms):
                rec = orchestrator.run_warmup_block(name, BLOCK)
            elif replay:
                # Force control's allocation; feedback remains observation only.
                hb = orchestrator.reward_tracker.current_hv
                result = portfolio.run_arm(name, BLOCK)
                reward = orchestrator.reward_tracker.compute_reward(portfolio.global_archive)
                from mojssp.orchestrator import BlockExecutionRecord
                rec = BlockExecutionRecord(bi, name, BLOCK, result.evaluations_used,
                                           reward, hb, orchestrator.reward_tracker.current_hv,
                                           result.completed, replay[bi]['phase'])
            else:
                # select_arm tie breaking must occur exactly once.
                original_select = selector.select_arm
                selector.select_arm = lambda: name
                try:
                    rec = orchestrator.step(BLOCK)
                finally:
                    selector.select_arm = original_select
            assert rec.evaluations_used == BLOCK
            assert actual_fe == portfolio.total_evaluations == (bi+1)*BLOCK
            for e in arm.current_archive.entries:
                first_seen.setdefault(compute_genotype_id(e.solution), name)
            if name not in initial_diversity:
                initial_diversity[name] = genetic_diversity(arm)
            row = asdict(rec)
            row.update(fe=actual_fe, elapsed=time.perf_counter()-started,
                       block_seconds=time.perf_counter()-t0,
                       donor=donor, guided_crossovers=guidance.uses if guidance else 0)
            blocks.append(row)
            if actual_fe in (1000, 3000):
                milestones[str(actual_fe)] = entries_json(portfolio.global_archive, normalizer)
    search_seconds = time.perf_counter()-started
    metrics_start = time.perf_counter()
    archive = portfolio.global_archive
    hv = compute_archive_hypervolume(archive, normalizer)
    points = sorted(set(normalizer.normalize_tuple(e.objectives) for e in archive.entries))
    nn = [min(math.dist(p,q) for j,q in enumerate(points) if i!=j)
          for i,p in enumerate(points)] if len(points)>1 else [0.0]
    marginal = {}
    for name in portfolio.arm_names:
        without = ParetoArchive()
        for other in arms:
            if other.arm_name != name:
                without.update(other.current_archive.entries)
        marginal[name] = max(0.0, hv-compute_archive_hypervolume(without, normalizer))
    prev_hv, auc = 0., 0.
    for block in blocks:
        auc += BLOCK * (prev_hv + block['hv_after']) / 2
        prev_hv = block['hv_after']
    result = {'case': case['name'], 'split': split, 'seed': seed, 'method': method,
              'search_fe': actual_fe, 'hv': hv, 'auc_hv': auc/BUDGET,
              'seconds': search_seconds, 'hv_per_fe': hv/BUDGET,
              'unique_vectors': len(points), 'archive_size': len(archive),
              'objective_range': [max(p[k] for p in points)-min(p[k] for p in points)
                                  for k in range(3)],
              'mean_nn_distance': sum(nn)/len(nn),
              'genetic_diversity_initial': initial_diversity,
              'genetic_diversity_final': {a.arm_name: genetic_diversity(a) for a in arms},
              'marginal_hv': marginal,
              'allocation': {n: sum(b['evaluations_used'] for b in blocks if b['arm_name']==n)
                             for n in portfolio.arm_names},
              'first_observed_final': {n: sum(first_seen[compute_genotype_id(e.solution)]==n
                                             for e in archive.entries) for n in portfolio.arm_names},
              'zero_gain_blocks': sum(b['reward']<=1e-14 for b in blocks),
              'blocks': blocks, 'milestones': milestones,
              'arm_archives': {a.arm_name: entries_json(a.current_archive, normalizer) for a in arms},
              'guidance_events': guidance.events if guidance else [],
              'source_sha256': EXECUTION_SOURCE_HASHES, 'instance_sha256': case['sha256']}
    result['analysis_seconds'] = time.perf_counter()-metrics_start
    return result


def main():
    parser = argparse.ArgumentParser(description='Frozen historical campaign. Use run_experiment.py for new experiments; reproduce_portfolio_baseline.py for saved baseline validation.')
    parser.parse_args()
    parser.error('Historical campaign is read-only; use run_experiment.py for new runs')


EXECUTION_SOURCE_HASHES = source_hashes()

if __name__ == '__main__':
    main()
