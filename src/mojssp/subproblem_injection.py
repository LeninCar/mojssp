"""Subproblem-compatible BLMR parents for the existing MOEA/D mating hook."""
from collections import Counter
import time

from .archive_injection import ArchiveParentInjection
from .provenance import compute_genotype_id
from .moead import MOEADArm, tchebycheff_scalarizing
from .regional_explorer import RegionalExplorerArm
from .regional_injection import InjectedRegionalPortfolio
from .regional_portfolio import _block_record
from .normalization import ObjectiveNormalizer, compute_instance_bounds
from .orchestrator import AdaptivePortfolioOrchestrator
from .reward import HypervolumeRewardTracker
from .selectors import make_selector


class SubproblemParentInjection(ArchiveParentInjection):
    """Choose by live target weight and ideal point, with at most m uses per block."""

    def reset_block(self):
        super().reset_block()
        self._used_ids = set()
        self._uses = 0

    def prepare(self, arm, global_archive, block_index, global_fe_before):
        if arm._instance is not self.instance or arm.arm_name != self.recipient:
            raise ValueError('Invalid recipient')
        self.reset_block()
        self.block_index,self.global_fe_before = block_index,global_fe_before
        seen = self.seen_by.get(self.recipient,set())
        if not arm.current_archive.entries:
            return []
        self._donors = [e for e in global_archive.entries
            if self.origins.get(compute_genotype_id(e.solution)) == self.source
            and compute_genotype_id(e.solution) not in seen]
        return [compute_genotype_id(e.solution) for e in self._donors]

    def parent(self, arm, native_parent):
        if arm._instance is not self.instance or arm.arm_name != self.recipient:
            raise ValueError('Invalid recipient')
        self._mating_count += 1
        if self._mating_count % self.every or self._uses >= self.m:
            return native_parent
        candidates = [e for e in self._donors
            if compute_genotype_id(e.solution) not in self._used_ids and e.solution != native_parent]
        if not candidates:
            return native_parent
        index = arm.current_subproblem_idx
        weight = arm.weight_vectors[index]
        ideal = arm.ideal_point
        donor = min(candidates,key=lambda e:(
            tchebycheff_scalarizing(self.normalizer.normalize_tuple(e.objectives),weight,ideal),
            compute_genotype_id(e.solution)))
        gid = compute_genotype_id(donor.solution)
        self._used_ids.add(gid)
        self._uses += 1
        self.events.append(dict(block_index=self.block_index,global_fe_before=self.global_fe_before,
            recipient_fe_before_mating=arm.total_evaluations,source=self.source,recipient=self.recipient,
            mating_index=self._mating_count,donor_id=gid,native_parent_id=compute_genotype_id(native_parent),
            donor_sequence=list(donor.solution.sequence),donor_modes=list(donor.solution.modes),
            donor_objectives=list(donor.objectives),subproblem_index=index,target_weight=list(weight),
            ideal_point=list(ideal),donor_scalar_score=tchebycheff_scalarizing(
                self.normalizer.normalize_tuple(donor.objectives),weight,ideal)))
        return donor.solution


class SubproblemInjectedPortfolio(InjectedRegionalPortfolio):
    def _attach_injection(self):
        instance,normalizer,active,m,every = self._injection_config
        self.injection = SubproblemParentInjection(instance,normalizer,source='RegionExplorer',
            recipient='MOEA/D',m=m,every=every)
        self.injection_trace = []
        self.get_arm('MOEA/D').set_archive_guidance(self.injection if active else None)


def run_subproblem_injection(instance,seed,active=True,budget=3000,block_size=50,population_size=30):
    """Change donor selection only; preserve BLMR, native operators and dynamic rounds."""
    if population_size>block_size or block_size>150 or budget<100:
        raise ValueError('Blocks and budget must cover the initial pair')
    normalizer=ObjectiveNormalizer(compute_instance_bounds(instance))
    arms={'MOEA/D':MOEADArm(instance,population_size=population_size,seed=(seed*10007+17)%(2**31-1)),
          'RegionExplorer':RegionalExplorerArm(instance,normalizer,policy='random',
                            seed=(seed*10007+71)%(2**31-1),max_evaluations=budget)}
    portfolio=SubproblemInjectedPortfolio(arms,normalizer,instance,seed,active,5,10)
    tracker=HypervolumeRewardTracker(normalizer)
    orchestrator=AdaptivePortfolioOrchestrator(portfolio,make_selector('uniform',list(arms),seed=seed),tracker)
    start=time.perf_counter()
    execution=orchestrator.run_dynamic_rounds(budget,block_size,round_size=300,minimum_share=.1)
    elapsed=time.perf_counter()-start
    assert execution.total_evaluations==budget
    allocations=Counter()
    for b in execution.history:allocations[b.arm_name]+=b.evaluations_used
    return dict(budget=budget,evaluations_used=budget,arms=list(arms),policy='dynamic',
        policy_profile=dict(round_size=300,minimum_share=.1),active_injection=active,
        migration_profile=dict(source='RegionExplorer',recipient='MOEA/D',m=5,every=10,
            selection='Minimum native Tchebycheff value for current target subproblem; genotype ID breaks ties',
            pool='All source-eligible global donors frozen at block start; distinct donor uses capped at five'),
        allocations=dict(allocations),hypervolume=tracker.current_hv,runtime_seconds=elapsed,
        blocks=[_block_record(b) for b in execution.history],
        checkpoints=[[b.fe_after,b.hv_after] for b in execution.history],
        pareto_front=[list(e.objectives) for e in portfolio.global_archive.entries],
        front_entries=[dict(sequence=list(e.solution.sequence),modes=list(e.solution.modes),objectives=list(e.objectives))
                       for e in portfolio.global_archive.entries],
        region_trace=arms['RegionExplorer'].trace,migration_events=portfolio.injection.events,
        migration_uses=len(portfolio.injection.events),injection_trace=portfolio.injection_trace,completed=True)

