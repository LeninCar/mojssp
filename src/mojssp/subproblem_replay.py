"""Diagnostic execution under a previously recorded passive allocation trace."""
from collections import Counter
import time

from .moead import MOEADArm
from .normalization import ObjectiveNormalizer, compute_instance_bounds
from .regional_explorer import RegionalExplorerArm
from .subproblem_injection import SubproblemInjectedPortfolio
from .reward import HypervolumeRewardTracker


def validate_replay_schedule(schedule, budget, population_size=30):
    """Reject malformed schedules before any objective evaluation."""
    if isinstance(budget,bool) or not isinstance(budget,int) or budget<=0 or not schedule:
        raise ValueError('Positive budget and nonempty schedule required')
    cursor=0
    for row in schedule:
        used=row['evaluations_used']
        if isinstance(used,bool) or not isinstance(used,int) or not 0<used<=50:
            raise ValueError('Each scheduled block must contain one to fifty evaluations')
        if row['arm_name'] not in ('MOEA/D','RegionExplorer'):
            raise ValueError('Unknown scheduled arm')
        if row['fe_before']!=cursor or row['fe_after']!=cursor+used:
            raise ValueError('Schedule must be contiguous')
        if row['budget_allocated']!=used:
            raise ValueError('Scheduled and consumed evaluations must match')
        cursor+=used
    if cursor!=budget or schedule[0]['arm_name']!='MOEA/D' or schedule[0]['evaluations_used']<population_size:
        raise ValueError('Schedule must cover budget and initial MOEA/D population')


def run_subproblem_replay(instance,seed,schedule,active=True,budget=3000,population_size=30):
    """Hold block order and FE fixed; rewards do not modify future allocations."""
    validate_replay_schedule(schedule,budget,population_size)
    norm=ObjectiveNormalizer(compute_instance_bounds(instance))
    arms={'MOEA/D':MOEADArm(instance,population_size=population_size,seed=(seed*10007+17)%(2**31-1)),
          'RegionExplorer':RegionalExplorerArm(instance,norm,policy='random',
                            seed=(seed*10007+71)%(2**31-1),max_evaluations=budget)}
    portfolio=SubproblemInjectedPortfolio(arms,norm,instance,seed,active,5,10)
    tracker=HypervolumeRewardTracker(norm)
    blocks=[];allocations=Counter();start=time.perf_counter()
    for source in schedule:
        before,hv_before=portfolio.total_evaluations,tracker.current_hv
        result=portfolio.run_arm(source['arm_name'],source['evaluations_used'])
        assert result.arm_result.evaluations_used==source['evaluations_used']
        gain=tracker.compute_reward(portfolio.global_archive)
        row=dict(source)
        row.update(fe_before=before,fe_after=portfolio.total_evaluations,hv_before=hv_before,
            hv_after=tracker.current_hv,reward=gain,completed=result.arm_result.completed)
        blocks.append(row);allocations[source['arm_name']]+=result.arm_result.evaluations_used
    assert portfolio.total_evaluations==budget
    return dict(budget=budget,evaluations_used=budget,arms=list(arms),policy='external_replay',
        active_injection=active,allocation_source='Previously recorded passive dynamic trace',
        allocations=dict(allocations),hypervolume=tracker.current_hv,
        runtime_seconds=time.perf_counter()-start,blocks=blocks,
        checkpoints=[[b['fe_after'],b['hv_after']] for b in blocks],
        pareto_front=[list(e.objectives) for e in portfolio.global_archive.entries],
        front_entries=[dict(sequence=list(e.solution.sequence),modes=list(e.solution.modes),objectives=list(e.objectives))
                       for e in portfolio.global_archive.entries],
        region_trace=arms['RegionExplorer'].trace,migration_events=portfolio.injection.events,
        migration_uses=len(portfolio.injection.events),injection_trace=portfolio.injection_trace,completed=True)

