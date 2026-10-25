"""Opt-in BLMR to MOEA/D parent injection with live dynamic allocation."""
from collections import Counter
import time

from .archive_injection import ArchiveParentInjection
from .moead import MOEADArm
from .regional_explorer import RegionalExplorerArm
from .regional_portfolio import RegionAwarePortfolio, _block_record
from .normalization import ObjectiveNormalizer, compute_instance_bounds
from .orchestrator import AdaptivePortfolioOrchestrator
from .reward import HypervolumeRewardTracker
from .selectors import make_selector
from .provenance import compute_genotype_id


class InjectedRegionalPortfolio(RegionAwarePortfolio):
    """Observe archive provenance and supply only eligible BLMR parents to MOEA/D."""

    def __init__(self, arms, normalizer, instance, seed, active=True, m=5, every=10):
        if list(arms) != ['MOEA/D', 'RegionExplorer']:
            raise ValueError('Injection requires the ordered MOEA/D and RegionExplorer pair')
        self._injection_config = instance, normalizer, active, m, every
        super().__init__(arms, normalizer, instance, seed, guidance=False)
        self._attach_injection()

    def _attach_injection(self):
        instance, normalizer, active, m, every = self._injection_config
        self.injection = ArchiveParentInjection(
            instance, normalizer, source='RegionExplorer', recipient='MOEA/D', m=m, every=every)
        self.injection_trace = []
        self.get_arm('MOEA/D').set_archive_guidance(self.injection if active else None)

    def reset(self):
        super().reset()
        self._attach_injection()

    def run_arm(self, arm_name, budget):
        arm = self.get_arm(arm_name)
        guide = self.injection
        before = self.total_evaluations
        events_before = len(guide.events)
        observed_before = set(guide.seen_by.get(arm_name, set()))
        row = dict(block_index=len(self.injection_trace), arm=arm_name, global_fe_before=before)
        if arm_name == guide.recipient:
            archive = self.global_archive
            row['global_points_before'] = {
                compute_genotype_id(e.solution):list(guide.normalizer.normalize_tuple(e.objectives))
                for e in archive.entries}
            row['recipient_points_before'] = [
                list(guide.normalizer.normalize_tuple(e.objectives)) for e in arm.current_archive.entries]
            row['prepared_donor_ids'] = guide.prepare(arm, archive, row['block_index'], before)
        else:
            row.update(global_points_before={}, recipient_points_before=[], prepared_donor_ids=[])
        result = super().run_arm(arm_name, budget)
        guide.observe(arm)
        row.update(global_fe_after=self.total_evaluations, evaluations_used=result.arm_result.evaluations_used,
                   new_observed_ids=sorted(guide.seen_by[arm_name]-observed_before),
                   used_donors=len(guide.events)-events_before)
        self.injection_trace.append(row)
        return result


def run_blmr_injection(instance, seed, active=True, budget=3000, block_size=50,
                       population_size=30, m=5, every=10):
    """Run live dynamic rounds; injected offspring still spend native MOEA/D FE."""
    if block_size < population_size or budget < 100:
        raise ValueError('Budget and blocks must cover both initial arm blocks')
    normalizer = ObjectiveNormalizer(compute_instance_bounds(instance))
    arms = {
        'MOEA/D':MOEADArm(instance, population_size=population_size,
                         seed=(seed*10007+17)%(2**31-1)),
        'RegionExplorer':RegionalExplorerArm(instance, normalizer, policy='random',
                         seed=(seed*10007+71)%(2**31-1), max_evaluations=budget)}
    portfolio = InjectedRegionalPortfolio(arms, normalizer, instance, seed, active, m, every)
    tracker = HypervolumeRewardTracker(normalizer)
    selector = make_selector('uniform', list(arms), seed=seed)
    orchestrator = AdaptivePortfolioOrchestrator(portfolio, selector, tracker)
    started = time.perf_counter()
    execution = orchestrator.run_dynamic_rounds(
        budget, block_size, round_size=300, minimum_share=.1)
    elapsed = time.perf_counter()-started
    assert execution.total_evaluations == budget
    allocations = Counter()
    for b in execution.history:
        allocations[b.arm_name] += b.evaluations_used
    return dict(budget=budget, evaluations_used=execution.total_evaluations,
        arms=list(arms), policy='dynamic', policy_profile=dict(round_size=300, minimum_share=.1),
        active_injection=active, migration_profile=dict(source='RegionExplorer',recipient='MOEA/D',m=m,every=every),
        allocations=dict(allocations), hypervolume=tracker.current_hv, runtime_seconds=elapsed,
        blocks=[_block_record(b) for b in execution.history],
        checkpoints=[[b.fe_after,b.hv_after] for b in execution.history],
        pareto_front=[list(e.objectives) for e in portfolio.global_archive.entries],
        front_entries=[dict(sequence=list(e.solution.sequence),modes=list(e.solution.modes),objectives=list(e.objectives))
                       for e in portfolio.global_archive.entries],
        region_trace=arms['RegionExplorer'].trace,
        migration_events=portfolio.injection.events, migration_uses=len(portfolio.injection.events),
        injection_trace=portfolio.injection_trace, completed=True)

