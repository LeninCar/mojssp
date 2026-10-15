"""Independent reconstruction of saved genotypes, FE traces and research metrics."""
from collections import Counter
from dataclasses import asdict
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from run_portfolio_loop import OUT, write_new
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
    files=sorted((OUT/'runs').rglob('*.json'))
    assert not any(p.name.endswith('.failed.json') for p in files), 'Investigate failures before closure'
    instances={}
    verified={}
    count=0
    methods=Counter()
    totals=Counter()
    replay_count=0
    diverged_replays=0
    for path in files:
        r=json.loads(path.read_text(encoding='utf-8'))
        methods[r['method']]+=1
        case=r['case']
        if case not in instances:
            record=next(c for c in manifest['cases'] if c['name']==case)
            instance=load_dzn(ROOT/record['path'])
            instances[case]=(instance,ObjectiveNormalizer(compute_instance_bounds(instance)))
        instance,normalizer=instances[case]
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
        totals['search_fe']+=r['search_fe']
        totals['search_seconds']+=r['seconds']
        totals['metric_seconds']+=r['analysis_seconds']
        for name,archive in r['arm_archives'].items():
            points=[tuple(e['normalized']) for other,es in r['arm_archives'].items() if other!=name for e in es]
            marginal=max(0.,r['hv']-compute_hypervolume(points))
            assert math.isclose(marginal,r['marginal_hv'][name],abs_tol=1e-12)
    assert totals['search_fe']<=manifest['max_search_fe']
    return {'runs':len(files),'methods':dict(methods),'totals':dict(totals),
            'unique_final_or_checkpoint_solutions_reevaluated':count,
            'audit_fe_not_used_for_search':count,'identical_allocation_guidance_pairs':replay_count,
            'guidance_pairs_with_different_final_genotypes':diverged_replays,
            'passed':True,
            'scope':'Every saved milestone genotype decoded, schedule validated, objective reevaluated; FE traces, HV, AUC, exclusive contributions and guidance replay checked. Does not prove global optimality or universal superiority.'}


if __name__=='__main__':
    result=audit()
    write_new(OUT/'integrity_audit.json',result)
    print(json.dumps(result,indent=2))
