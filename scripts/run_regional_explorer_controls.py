"""Independent random-start controls for the archive-region explorer."""
import argparse
import json
from pathlib import Path
import random
import shutil
import time
from unittest.mock import patch

from run_weighted_pilot import ROOT, auc, digest, write_csv, write_json
from mojssp.evaluator import Evaluator
from mojssp.decoder import Decoder
from mojssp.hypervolume import compute_hypervolume
from mojssp.io import load_dzn
from mojssp.normalization import ObjectiveNormalizer, compute_instance_bounds
from mojssp.pareto_archive import ParetoArchive
from mojssp.regional_explorer import RegionalExplorerArm
from mojssp.reward import HypervolumeRewardTracker
from mojssp.solution import Solution


def run_individual(instance,seed,policy,budget=3000,population_size=30,block_size=50):
    if not 0<population_size<block_size or budget % block_size:
        raise ValueError('Initialization must fit the first full block')
    norm = ObjectiveNormalizer(compute_instance_bounds(instance))
    explorer = RegionalExplorerArm(instance,norm,policy=policy,seed=(seed*10007+71)%(2**31-1),
        max_evaluations=budget-population_size,parent_count=5)
    archive = ParetoArchive()
    rng = random.Random((seed*10007+83)%(2**31-1))
    decoder,evaluator = Decoder(),Evaluator()
    started = time.perf_counter()
    for _ in range(population_size):
        solution = Solution.random(instance,rng=rng)
        schedule = decoder.decode(instance,solution)
        archive.add(solution,schedule,evaluator.evaluate(instance,schedule))
    total = population_size
    checkpoints = []
    tracker = HypervolumeRewardTracker(norm)
    while total<budget:
        amount = block_size-population_size if total==population_size else min(block_size,budget-total)
        row = explorer.prepare(archive)
        row['global_fe_before'] = total
        result = explorer.run(amount)
        assert result.evaluations_used==amount
        total += amount
        archive.update(result.solutions.entries)
        tracker.compute_reward(archive)
        checkpoints.append([total,tracker.current_hv])
    assert total==population_size+explorer.total_evaluations==budget
    front = [list(entry.objectives) for entry in archive.entries]
    assert abs(compute_hypervolume([norm.normalize_tuple(p) for p in front])-tracker.current_hv)<1e-12
    return dict(budget=budget,evaluations_used=total,hypervolume=tracker.current_hv,pareto_front=front,
        front_entries=[dict(sequence=list(e.solution.sequence),modes=list(e.solution.modes),objectives=list(e.objectives)) for e in archive.entries],
        initialization_fe=population_size,evolution_fe=explorer.total_evaluations,
        region_trace=explorer.trace,checkpoints=checkpoints,auc_hv=auc(checkpoints,budget),
        runtime_seconds=time.perf_counter()-started,completed=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if output.exists() or not output.is_relative_to(ROOT/'results/experiments'):
        parser.error('Choose a new output inside results/experiments')
    source = ROOT/'results/experiments/weighted_pilot_development_20261023'
    prior = json.loads((source/'config.json').read_text(encoding='utf-8'))
    files = [*sorted((ROOT/'src/mojssp').glob('*.py')),Path(__file__).resolve(),ROOT/'scripts/run_weighted_pilot.py']
    hashes = {str(p.relative_to(ROOT)):digest(p) for p in files}
    output.mkdir(parents=True)
    for p in files:
        target = output/'code'/p.relative_to(ROOT)
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(p,target)
    for case in prior['cases']:
        path = source/'instances'/f"{case['name']}.dzn"
        assert digest(path)==case['sha256']
        target = output/'instances'/path.name
        target.parent.mkdir(exist_ok=True)
        shutil.copy2(path,target)
    write_json(output/'config.json',dict(cases=prior['cases'],seeds=prior['master_seeds'],policies=['random','sparse'],
        budget=3000,population_size=30,block_size=50,initialization_fe=30,evolution_fe=2970,
        seed_formula='(master_seed*10007+offset) modulo (2**31-1)',initialization_seed_offset=83,operator_seed_offset=71,
        source_sha256=hashes,initialization='Thirty evaluated random solutions; no MOEA/D parents',
        first_block='30 initial evaluations plus 20 mutations; subsequent blocks contain 50 mutations',
        fairness='Same region geometry, operators, five-parent pool and policies as cooperative explorer'))
    original = Evaluator.evaluate
    records = []
    for ci,case in enumerate(prior['cases']):
        instance = load_dzn(output/'instances'/f"{case['name']}.dzn")
        for si,seed in enumerate(prior['master_seeds']):
            policies = ['random','sparse'] if (ci*3+si)%2==0 else ['sparse','random']
            for policy in policies:
                assert all(digest(ROOT/p)==sha for p,sha in hashes.items())
                calls = 0
                def counted(self,*a,**kw):
                    nonlocal calls
                    calls += 1
                    return original(self,*a,**kw)
                try:
                    with patch.object(Evaluator,'evaluate',counted):
                        r = run_individual(instance,seed,policy)
                    assert calls==r['evaluations_used']==3000
                    r.update(case=case['name'],master_seed=seed,method='explorer_'+policy+'_individual',actual_evaluator_calls=calls)
                    write_json(output/'runs'/f"{case['name']}__{seed}__{policy}.json",r)
                except Exception as error:
                    write_json(output/'failure.json',dict(case=case['name'],seed=seed,policy=policy,error=repr(error),actual_evaluator_calls=calls))
                    raise
                records.append(r)
                print(f"{len(records)}/36 {case['name']} seed={seed} {policy} HV={r['hypervolume']:.6f}",flush=True)
    write_csv(output/'runs.csv',[{k:r[k] for k in ['case','master_seed','method','hypervolume','auc_hv','runtime_seconds']} for r in records])
    write_json(output/'validation.json',dict(new_runs=len(records),new_search_fe=sum(r['actual_evaluator_calls'] for r in records),
        all_initialization_fe_included=True,all_budgets_exact=True))
    write_json(output/'artifact_manifest.json',{str(p.relative_to(output)):digest(p)
        for p in sorted(output.rglob('*')) if p.is_file() and p.name!='artifact_manifest.json'})


if __name__=='__main__':
    main()
