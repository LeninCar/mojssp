"""Offline tests only: no evolutionary search or evaluator calls."""
from copy import deepcopy
import random
import unittest
from unittest.mock import patch

from mojssp.contribution_report import ARMS, contribution_report, nondominated
from mojssp.evaluator import Evaluator
from mojssp.hypervolume import compute_hypervolume
from mojssp.provenance import compute_genotype_id
from mojssp.solution import Solution


def entry(n, point):
    sol = Solution((n,), (1,))
    return dict(id=compute_genotype_id(sol), sequence=[n], modes=[1],
                objectives=dict(makespan=point[0], tardiness=point[1], energy=point[2]), normalized=list(point))


def fixture(archives):
    points = nondominated([e['normalized'] for es in archives.values() for e in es])
    unique = {e['id']: e for es in archives.values() for e in es}
    front = [e for e in unique.values() if tuple(e['normalized']) in points]
    blocks = [dict(arm_name=ARMS[i%3], evaluations_used=50, reward=0.,
                   phase='warmup' if i<3 else 'adaptive') for i in range(60)]
    hv = compute_hypervolume(points)
    return dict(split='development', method='scaled', search_fe=3000, blocks=blocks,
                arm_archives=archives, milestones={'3000': front}, hv=hv,
                allocation={a:1000 for a in ARMS}, marginal_hv={a:hv-compute_hypervolume(
                    [e['normalized'] for b in ARMS if b!=a for e in archives[b]]) for a in ARMS})


class ContributionTests(unittest.TestCase):
    def setUp(self):
        self.guard = patch.object(Evaluator, 'evaluate', side_effect=AssertionError('New FE forbidden'))
        self.mock = self.guard.start()
        self.addCleanup(self.guard.stop)

    def test_analytic_volume_and_dominated_points_reappear(self):
        r = contribution_report(fixture({ARMS[0]:[entry(1,(.1,.1,.1))],
                                        ARMS[1]:[entry(2,(.6,.6,.6))], ARMS[2]:[]}))
        self.assertAlmostEqual(r['global_hv'],1.)
        self.assertAlmostEqual(r['arms'][ARMS[0]]['mc'],.875)
        self.assertEqual(r['recommended_arm'],ARMS[0])
        self.mock.assert_not_called()

    def test_shared_genotype_survives_arm_removal(self):
        e=entry(1,(.1,.1,.1))
        r=contribution_report(fixture({ARMS[0]:[e],ARMS[1]:[deepcopy(e)],ARMS[2]:[]}))
        self.assertEqual(r['status'],'no_positive_contribution')
        self.assertIsNone(r['recommended_arm'])
        for a in ARMS[:2]:
            self.assertEqual(r['arms'][a]['mc'],0)
            self.assertEqual(r['arms'][a]['shared_global_genotypes'],1)

    def test_distinct_genotypes_equal_objectives_and_duplicates(self):
        e=entry(1,(.1,.1,.1))
        r=contribution_report(fixture({ARMS[0]:[e,e],ARMS[1]:[entry(2,(.1,.1,.1))],ARMS[2]:[]}))
        self.assertEqual(r['global_genotypes'],2)
        self.assertEqual(r['global_unique_objectives'],1)
        self.assertEqual(r['arms'][ARMS[0]]['exclusive_global_genotypes'],1)
        self.assertEqual(r['arms'][ARMS[0]]['shared_global_objectives'],1)
        self.assertEqual(r['arms'][ARMS[0]]['mc'],0)

    def test_positive_tie_not_forced(self):
        r=contribution_report(fixture({ARMS[0]:[entry(1,(.1,.6,.6))],
                                      ARMS[1]:[entry(2,(.6,.1,.6))],ARMS[2]:[]}))
        self.assertEqual(r['status'],'tie')
        self.assertIsNone(r['recommended_arm'])

    def test_budget_and_holdout_rejected(self):
        run=fixture({ARMS[0]:[entry(1,(.1,.1,.1))], ARMS[1]:[], ARMS[2]:[]})
        for change in ({'search_fe':2999},{'split':'holdout_test'},{'split':'confirmation'},{'method':'combined'}):
            with self.assertRaises(ValueError): contribution_report(dict(run,**change))
        bad=deepcopy(run);bad['blocks'][0]['evaluations_used']=49
        with self.assertRaises(ValueError): contribution_report(bad)

    def test_unknown_provenance_or_forged_id_rejected(self):
        run=fixture({ARMS[0]:[entry(1,(.1,.1,.1))], ARMS[1]:[], ARMS[2]:[]})
        bad=deepcopy(run);bad['milestones']['3000'].append(entry(999,(0,0,0)))
        with self.assertRaises(ValueError): contribution_report(bad)
        bad=deepcopy(run);bad['arm_archives'][ARMS[0]][0]['id']='forged'
        with self.assertRaises(ValueError): contribution_report(bad)

    def test_deterministic_readonly_rng_and_metrics(self):
        run=fixture({ARMS[0]:[entry(1,(.1,.1,.1))], ARMS[1]:[], ARMS[2]:[]})
        before=deepcopy(run);rng=random.getstate()
        self.assertEqual(contribution_report(run),contribution_report(run))
        self.assertEqual(run,before)
        self.assertEqual(random.getstate(),rng)
        bad=deepcopy(run);bad['hv']+=.01
        with self.assertRaises(ValueError): contribution_report(bad)


if __name__=='__main__':
    unittest.main()
