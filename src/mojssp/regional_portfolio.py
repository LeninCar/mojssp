"""Opt-in region guidance using the existing arms, selectors and orchestrator."""
from collections import Counter
from dataclasses import asdict
import math
import random
import time

from .arms import NSGA2Arm
from .moead import MOEADArm
from .spea2 import SPEA2Arm
from .normalization import ObjectiveNormalizer, compute_instance_bounds
from .orchestrator import AdaptivePortfolioOrchestrator
from .portfolio import Portfolio
from .provenance import compute_genotype_id
from .regional_explorer import RegionalExplorerArm, region_geometry, region_distance, regional_score
from .reward import HypervolumeRewardTracker
from .selectors import make_selector


SUPPORTED_ARMS = ('MOEA/D','NSGA-II','SPEA2','RegionExplorer')
POLICY_PROFILES = {
    'uniform':{},
    'sw_ucb':dict(window_size=10,exploration_factor=.07),
    'scaled':dict(window_size=10,exploration_factor=.07),
    'ph':dict(exploration_factor=.07,delta=.001,threshold=.05,min_instances=5),
    'dynamic':dict(round_size=300,minimum_share=.1),
}


def _block_record(record):
    row=asdict(record)
    if row['ucb_indices'] is not None:
        row['ucb_indices']={name:value if math.isfinite(value) else None
                            for name,value in row['ucb_indices'].items()}
    return row


class RegionalParentGuidance:
    """Up to five archive parents per native block, one every ten matings.

    Only the second crossover parent is supplied. Each arm retains its own
    crossover, mutation, decoding, evaluation and survivor selection.
    """
    def __init__(self,instance,normalizer,seed,parent_count=5,every=10):
        self.instance,self.normalizer = instance,normalizer
        self.parent_count,self.every = parent_count,every
        self._rng = random.Random(seed)
        self._pool,self._calls,self._used = [],0,0
        self.trace,self.events = [],[]

    def prepare(self,arm,archive,global_fe_before):
        self._pool,self._calls,self._used = [],0,0
        if not archive.entries or not arm.current_archive.entries:
            return
        geometry = region_geometry([self.normalizer.normalize_tuple(e.objectives) for e in archive.entries])
        selected = self._rng.randrange(len(geometry['weights']))
        weight = geometry['weights'][selected]
        self._pool = sorted(archive.entries,key=lambda e:(
            region_distance(self.normalizer.normalize_tuple(e.objectives),weight,geometry),
            regional_score(self.normalizer.normalize_tuple(e.objectives),weight,geometry),
            compute_genotype_id(e.solution)))[:self.parent_count]
        self.trace.append(dict(arm=arm.arm_name,global_fe_before=global_fe_before,
            selected_weight=list(weight),geometry=geometry,
            donor_ids=[compute_genotype_id(e.solution) for e in self._pool],
            global_parent_ids=sorted(compute_genotype_id(e.solution) for e in archive.entries)))

    def parent(self,arm,native_parent):
        self._calls += 1
        if self._calls%self.every or self._used>=len(self._pool):
            return native_parent
        donor = self._pool[self._used]
        self._used += 1
        if donor.solution==native_parent:
            return native_parent
        self.events.append(dict(arm=arm.arm_name,global_fe_before=self.trace[-1]['global_fe_before'],
            mating_index=self._calls,donor_id=compute_genotype_id(donor.solution),
            native_parent_id=compute_genotype_id(native_parent),donor_objectives=list(donor.objectives),
            donor_sequence=list(donor.solution.sequence),donor_modes=list(donor.solution.modes)))
        return donor.solution


class RegionAwarePortfolio(Portfolio):
    """Prepare region context immediately before an arm executes its budget."""
    def __init__(self,arms,normalizer,instance,seed,guidance=False):
        super().__init__(arms)
        self._region_context = normalizer,instance,seed,guidance
        self._attach_guides()

    def _attach_guides(self):
        normalizer,instance,seed,guidance = self._region_context
        self.guides = {}
        if guidance:
            for index,(name,arm) in enumerate(self.arms.items()):
                if name=='RegionExplorer':
                    continue
                guide = RegionalParentGuidance(instance,normalizer,(seed*10007+101+index)%(2**31-1))
                arm.set_archive_guidance(guide)
                self.guides[name] = guide

    def reset(self):
        super().reset()
        self._attach_guides()

    def run_arm(self,arm_name,budget):
        arm = self.get_arm(arm_name)
        if isinstance(arm,RegionalExplorerArm):
            arm.prepare(self.global_archive)['global_fe_before'] = self.total_evaluations
        elif arm.arm_name in self.guides:
            self.guides[arm.arm_name].prepare(arm,self.global_archive,self.total_evaluations)
        return super().run_arm(arm_name,budget)


def run_regional_policy_experiment(instance,seed,selected_arms,policy='scaled',guidance=False,
                                   budget=3000,block_size=50,population_size=30,*,minimum_share=None,
                                   dynamic_options=None):
    names = tuple(selected_arms)
    if len(names)<2 or len(set(names))!=len(names) or not set(names)<=set(SUPPORTED_ARMS):
        raise ValueError('Choose at least two distinct supported arms')
    if names[0]=='RegionExplorer':
        raise ValueError('A native arm must seed the archive before the explorer')
    if policy not in POLICY_PROFILES:
        raise ValueError('Unknown policy')
    if minimum_share is not None and policy!='dynamic':
        raise ValueError('Minimum share applies only to dynamic rounds')
    if dynamic_options and policy!='dynamic':
        raise ValueError('Dynamic options apply only to dynamic rounds')
    if dynamic_options and not set(dynamic_options)<={'share_power','exclusive_arm','exclusive_after'}:
        raise ValueError('Unknown dynamic option')
    if block_size<population_size or budget<len(names)*block_size:
        raise ValueError('Budget must cover a full initial block for every arm')
    norm = ObjectiveNormalizer(compute_instance_bounds(instance))
    arms = {}
    for name in names:
        if name=='MOEA/D':
            arm = MOEADArm(instance,population_size=population_size,seed=(seed*10007+17)%(2**31-1))
        elif name=='NSGA-II':
            arm = NSGA2Arm(instance,population_size=population_size,max_generations=None,seed=(seed*10007+29)%(2**31-1))
        elif name=='SPEA2':
            arm = SPEA2Arm(instance,population_size=population_size,archive_size=population_size,seed=(seed*10007+43)%(2**31-1))
        else:
            arm = RegionalExplorerArm(instance,norm,policy='random',seed=(seed*10007+71)%(2**31-1),max_evaluations=budget)
        arms[name] = arm
    portfolio = RegionAwarePortfolio(arms,norm,instance,seed,guidance)
    profile = dict(POLICY_PROFILES[policy])
    if minimum_share is not None:
        from .dynamic_budget import round_shares
        round_shares(dict.fromkeys(names,0.),minimum_share)
        profile['minimum_share'] = minimum_share
    if dynamic_options:
        profile.update(dynamic_options)
    selector = make_selector('uniform' if policy=='dynamic' else policy,names,seed=seed,
                             **({} if policy=='dynamic' else profile))
    tracker = HypervolumeRewardTracker(norm)
    orchestrator = AdaptivePortfolioOrchestrator(portfolio,selector,tracker)
    started = time.perf_counter()
    if policy=='dynamic':
        if profile['round_size']//len(names)<block_size:
            raise ValueError('First dynamic round must cover all initialization blocks')
        execution = orchestrator.run_dynamic_rounds(budget,block_size,**profile)
    else:
        execution = orchestrator.run(budget,block_size,neutral_warmup=True)
    elapsed = time.perf_counter()-started
    if execution.total_evaluations!=budget:
        raise RuntimeError('Incomplete execution')
    allocations = Counter()
    for row in execution.history:
        allocations[row.arm_name] += row.evaluations_used
    return dict(budget=budget,evaluations_used=execution.total_evaluations,policy=policy,
        policy_profile=profile,guidance=guidance,arms=list(names),allocations=dict(allocations),
        hypervolume=tracker.current_hv,runtime_seconds=elapsed,
        checkpoints=[[r.fe_after,r.hv_after] for r in execution.history],
        blocks=[_block_record(r) for r in execution.history],
        pareto_front=[list(e.objectives) for e in portfolio.global_archive.entries],
        front_entries=[dict(sequence=list(e.solution.sequence),modes=list(e.solution.modes),objectives=list(e.objectives))
                       for e in portfolio.global_archive.entries],
        region_trace=arms['RegionExplorer'].trace if 'RegionExplorer' in arms else [],
        guidance_trace=[t for guide in portfolio.guides.values() for t in guide.trace],
        guidance_events=[e for guide in portfolio.guides.values() for e in guide.events],completed=True)
