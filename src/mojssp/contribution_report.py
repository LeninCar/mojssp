"""Read-only final marginal-HV report; never calls an arm or an evaluator.

Provenance means membership in retained local archives, not first discovery or
genetic ancestry. This API accepts the saved scaled-UCB runner result.
"""
from collections import defaultdict
from math import isfinite

from .hypervolume import compute_hypervolume
from .provenance import compute_genotype_id
from .solution import Solution

ARMS = ('MOEA/D', 'NSGA-II', 'SPEA2')
LABEL = 'algoritmo con mayor contribución marginal al frente obtenido'


def nondominated(points):
    points = sorted(set(tuple(p) for p in points))
    return [p for p in points if not any(
        all(q[i] <= p[i] for i in range(3)) and q != p for q in points)]


def contribution_report(run):
    """Return deterministic JSON-compatible output without mutating ``run``.

    Fail closed on unsupported cohorts, budgets, search modes, malformed IDs,
    missing provenance, inconsistent archives, or recorded metric disagreement.
    Reference is the campaign's fixed (1.1, 1.1, 1.1). Normalized coordinates
    must additionally be checked against the instance by the caller.
    """
    if run.get('split') != 'development':
        raise ValueError('Only development is authorized')
    if run.get('method') != 'scaled':
        raise ValueError('Only the unchanged passive scaled-UCB architecture is supported')
    if run.get('search_fe') != 3000:
        raise ValueError('Expected exactly 3000 FE')
    blocks = run['blocks']
    if len(blocks) != 60 or any(b['evaluations_used'] != 50 for b in blocks):
        raise ValueError('Expected sixty blocks of fifty FE')
    if set(run['arm_archives']) != set(ARMS):
        raise ValueError('Missing or extra arm archives')
    entries, owners = {}, defaultdict(set)
    for arm in ARMS:
        for e in run['arm_archives'][arm]:
            gid = compute_genotype_id(Solution(tuple(e['sequence']), tuple(e['modes'])))
            if gid != e['id']:
                raise ValueError('Genotype ID mismatch')
            if not all(isfinite(x) for x in e['normalized']) or len(e['normalized']) != 3:
                raise ValueError('Invalid normalized objectives')
            if gid in entries and entries[gid] != e:
                raise ValueError('Inconsistent genotype records or hash collision')
            entries[gid] = e
            owners[gid].add(arm)
    saved = run['milestones']['3000']
    for e in saved:
        if e['id'] not in entries or entries[e['id']] != e:
            raise ValueError('Global provenance unverifiable; no conclusive recommendation')
    front_points = nondominated([e['normalized'] for e in entries.values()])
    if set(front_points) != set(tuple(e['normalized']) for e in saved):
        raise ValueError('Global front differs from union of retained archives')
    front_ids = {gid for gid, e in entries.items() if tuple(e['normalized']) in front_points}
    hv = compute_hypervolume(front_points)
    tolerance = max(1e-12, 1e-10 * abs(hv))
    if abs(hv - run['hv']) > tolerance:
        raise ValueError('Recorded global HV mismatch')
    objective_owners = defaultdict(set)
    for gid in front_ids:
        objective_owners[tuple(entries[gid]['normalized'])].update(owners[gid])
    metrics = {}
    for arm in ARMS:
        # Retain a shared genotype whenever any other arm owns it. Include local
        # points dominated in the original union: these may reappear on removal.
        other_points = [e['normalized'] for gid, e in entries.items() if owners[gid] - {arm}]
        hv_without = compute_hypervolume(nondominated(other_points))
        raw_mc = hv - hv_without
        if raw_mc < -tolerance:
            raise ValueError('Removing an arm increased HV')
        mc = max(0.0, raw_mc)
        if abs(mc - run['marginal_hv'][arm]) > tolerance:
            raise ValueError('Recorded marginal HV mismatch')
        fe = sum(b['evaluations_used'] for b in blocks if b['arm_name'] == arm)
        if fe != run['allocation'][arm]:
            raise ValueError('Allocation mismatch')
        metrics[arm] = {
            'mc': mc, 'raw_mc': raw_mc, 'hv_without_arm': hv_without, 'fe': fe,
            'historical_reward_including_warmup': sum(b['reward'] for b in blocks if b['arm_name'] == arm),
            'historical_reward_selector_only': sum(b['reward'] for b in blocks if b['arm_name'] == arm and b['phase'] != 'warmup'),
            'exclusive_global_genotypes': sum(owners[g] == {arm} for g in front_ids),
            'shared_global_genotypes': sum(arm in owners[g] and len(owners[g]) > 1 for g in front_ids),
            'exclusive_global_objectives': sum(a == {arm} for a in objective_owners.values()),
            'shared_global_objectives': sum(arm in a and len(a) > 1 for a in objective_owners.values()),
        }
    best = max(m['mc'] for m in metrics.values())
    leaders = [a for a in ARMS if best - metrics[a]['mc'] <= tolerance]
    status = 'no_positive_contribution' if best <= tolerance else 'tie' if len(leaders) > 1 else 'unique'
    return {'label': LABEL, 'recommended_arm': leaders[0] if status == 'unique' else None,
            'leader_set': leaders, 'status': status, 'tolerance': tolerance,
            'global_hv': hv, 'saved_global_genotypes': len(saved),
            'global_genotypes': len(front_ids), 'global_unique_objectives': len(front_points),
            'search_fe': 3000, 'new_search_fe': 0, 'reference': [1.1, 1.1, 1.1],
            'provenance_definition': 'retained_local_archive_membership', 'arms': metrics,
            'front': [dict(entries[g], arms=sorted(owners[g])) for g in sorted(front_ids)]}
