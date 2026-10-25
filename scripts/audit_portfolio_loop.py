"""Independent reconstruction of saved genotypes, FE traces and research metrics."""
from collections import Counter
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from run_portfolio_loop import OUT, write_new
from mojssp.project_paths import HISTORICAL_ROOT
from mojssp.project_paths import input_path
from mojssp.decoder import Decoder
from mojssp.evaluator import Evaluator
from mojssp.hypervolume import compute_hypervolume
from mojssp.io import load_dzn
from mojssp.normalization import ObjectiveNormalizer, compute_instance_bounds
from mojssp.provenance import compute_genotype_id
from mojssp.schedule_validator import validate_schedule
from mojssp.solution import Solution


def audit():
    manifest=json.loads((OUT/'manifest.json').read_text(encoding='utf-8'))
    baseline_source=json.loads((OUT/'baseline_execution_provenance.json').read_text(encoding='utf-8'))
    for name,sha in baseline_source['loaded_module_sha256'].items():
        assert hashlib.sha256((OUT/'code/baseline'/name).read_bytes()).hexdigest()==sha
    assert hashlib.sha256((OUT/'code/baseline/run_portfolio_loop.py').read_bytes()).hexdigest()==baseline_source['runner_sha256']
    files=sorted((OUT/'runs').rglob('*.json'))
    assert not any(p.name.endswith('.failed.json') for p in files), 'Investigate failures before closure'
    instances={}
    verified={}
    count=0
    methods=Counter()
    totals=Counter()
    replay_count=0
    diverged_replays=0
    passive_union_count=0
    source_variants_checked=set()
    for path in files:
        r=json.loads(path.read_text(encoding='utf-8'))
        methods[r['method']]+=1
        if not (r['split']=='development' and r['method'] in ['moead','nsga2','spea2','uniform','adaptive']):
            signature=tuple(sorted(r['source_sha256'].items()))
            if signature not in source_variants_checked:
                snapshots=[OUT/'code'/n for n in ['research_v1','research_v2','confirmation_frozen']]
                assert any(all((s/name).exists() and hashlib.sha256((s/name).read_bytes()).hexdigest()==sha
                               for name,sha in signature) for s in snapshots), 'Missing exact frozen search source'
                source_variants_checked.add(signature)
        case=r['case']
        if case not in instances:
            record=next(c for c in manifest['cases'] if c['name']==case)
            instance_path=input_path(record['path'])
            assert hashlib.sha256(instance_path.read_bytes()).hexdigest()==record['sha256']
            instance=load_dzn(instance_path)
            instances[case]=(instance,ObjectiveNormalizer(compute_instance_bounds(instance)),record)
        instance,normalizer,record=instances[case]
        assert r['instance_sha256']==record['sha256']
        assert r['search_fe']==3000
        assert len(r['blocks'])==60
        assert sum(r['allocation'].values())==3000
        for i,b in enumerate(r['blocks']):
            assert b['fe']==(i+1)*50
            assert b['evaluations_used']==50
            assert b['hv_after']+1e-12 >= b['hv_before']
            assert math.isclose(b['reward'],b['hv_after']-b['hv_before'],abs_tol=1e-12)
            if i:
                assert math.isclose(b['hv_before'],r['blocks'][i-1]['hv_after'],abs_tol=1e-12)
        area=sum(50*(b['hv_before']+b['hv_after'])/2 for b in r['blocks'])/3000
        assert math.isclose(area,r['auc_hv'],abs_tol=1e-12)
        entry_groups = list(r['milestones'].items()) + [('arm:'+n,es) for n,es in r['arm_archives'].items()]
        for milestone,entries in entry_groups:
            points=[]
            for e in entries:
                key=(case,e['id'])
                if key not in verified:
                    sol=Solution(tuple(e['sequence']),tuple(e['modes']))
                    sol.validate_with_instance(instance)
                    assert compute_genotype_id(sol)==e['id']
                    schedule=Decoder().decode(instance,sol)
                    assert not validate_schedule(instance,schedule)
                    obj=Evaluator().evaluate(instance,schedule)
                    assert asdict(obj)==e['objectives']
                    assert list(normalizer.normalize_tuple(obj))==e['normalized']
                    verified[key]=(e['objectives'],e['normalized'])
                    count+=1
                assert verified[key]==(e['objectives'],e['normalized'])
                points.append(tuple(e['normalized']))
            raw_points=[tuple(e['objectives'][k] for k in ['makespan','tardiness','energy']) for e in entries]
            for i,p in enumerate(raw_points):
                assert not any(all(a<=b for a,b in zip(q,p)) and any(a<b for a,b in zip(q,p))
                               for j,q in enumerate(raw_points) if i!=j), 'Saved archive contains a dominated point'
            hv=compute_hypervolume(points)
            if not milestone.startswith('arm:'):
                assert math.isclose(hv,r['blocks'][int(milestone)//50-1]['hv_after'],abs_tol=1e-12)
        final=r['milestones']['3000']
        assert len({tuple(e['normalized']) for e in final})==r['unique_vectors']
        assert math.isclose(compute_hypervolume([tuple(e['normalized']) for e in final]),r['hv'],abs_tol=1e-12)
        if r['method']=='guidance':
            ref=json.loads(path.with_name(path.name.replace('__guidance.json','__adaptive.json')).read_text(encoding='utf-8'))
            assert [b['arm_name'] for b in r['blocks']]==[b['arm_name'] for b in ref['blocks']]
            assert r['allocation']==ref['allocation']
            diverged_replays += r['milestones']['3000'] != ref['milestones']['3000']
            replay_count+=1
        if r['method']=='uniform':
            independent=[]
            siblings_complete=True
            for method in ['moead','nsga2','spea2']:
                sibling=path.with_name(path.name.replace('__uniform.json',f'__{method}.json'))
                if sibling.exists():
                    independent.extend(json.loads(sibling.read_text(encoding='utf-8'))['milestones']['1000'])
                else:
                    siblings_complete=False
            if siblings_complete:
                # Exact set comparison, preserving genotype alternatives at objective ties.
                def dominated(p,q):
                    return all(a<=b for a,b in zip(q,p)) and any(a<b for a,b in zip(q,p))
                def raw(e):
                    return tuple(e['objectives'][k] for k in ['makespan','tardiness','energy'])
                nd={e['id'] for e in independent if not any(
                    dominated(raw(e),raw(o)) for o in independent)}
                assert nd=={e['id'] for e in final}
                assert math.isclose(compute_hypervolume([e['normalized'] for e in independent]),r['hv'],abs_tol=1e-12)
                passive_union_count+=1
        totals['search_fe']+=r['search_fe']
        totals['search_seconds']+=r['seconds']
        totals['metric_seconds']+=r['analysis_seconds']
        for name,archive in r['arm_archives'].items():
            points=[tuple(e['normalized']) for other,es in r['arm_archives'].items() if other!=name for e in es]
            marginal=max(0.,r['hv']-compute_hypervolume(points))
            assert math.isclose(marginal,r['marginal_hv'][name],abs_tol=1e-12)
    assert totals['search_fe']<=manifest['max_search_fe']
    reproduction=json.loads((OUT/'reproduction_audit.json').read_text(encoding='utf-8'))
    totals['reproduction_fe']=reproduction['additional_search_fe']
    totals['reproduction_seconds']=sum(r['seconds'] for r in reproduction['cases'])
    totals['all_search_fe']=totals['search_fe']+totals['reproduction_fe']
    assert totals['all_search_fe']<=manifest['max_search_fe']
    return {'runs':len(files),'methods':dict(methods),'totals':dict(totals),
            'unique_final_or_checkpoint_solutions_reevaluated':count,
            'audit_fe_not_used_for_search':count,'identical_allocation_guidance_pairs':replay_count,
            'guidance_pairs_with_different_final_genotypes':diverged_replays,
            'passive_uniform_equal_independent_1000_FE_union_pairs':passive_union_count,
            'exact_nonbaseline_execution_source_trees_verified':len(source_variants_checked),
            'passed':True,
            'scope':'Every saved milestone genotype decoded, schedule validated, objective reevaluated; FE traces, HV, AUC, exclusive contributions and guidance replay checked. Does not prove global optimality or universal superiority.'}


if __name__=='__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output already exists; choose a new file')
    if args.output.resolve().is_relative_to(HISTORICAL_ROOT):
        parser.error('output must be outside the saved campaign')
    result=audit()
    write_new(args.output,result)
    print(json.dumps(result,indent=2))
