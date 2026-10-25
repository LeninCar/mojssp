"""Offspring-level shared credit with unchanged dynamic quota equations."""
from collections import Counter
from dataclasses import replace
import math
import time

from .hypervolume import compute_hypervolume
from .provenance import compute_genotype_id
from .subproblem_injection import SubproblemInjectedPortfolio
from .moead import MOEADArm
from .regional_explorer import RegionalExplorerArm
from .normalization import ObjectiveNormalizer,compute_instance_bounds
from .reward import HypervolumeRewardTracker
from .orchestrator import AdaptivePortfolioOrchestrator,AdaptiveExecutionResult
from .selectors import make_selector
from .dynamic_budget import round_shares
from .fixed_budget import evaluation_quotas
from .regional_portfolio import _block_record


class OffspringObserver:
    """Keep a shadow objective front without touching native search state."""
    def __init__(self,portfolio,normalizer):
        self.portfolio,self.normalizer=portfolio,normalizer
        self.rows,self.blocks=[],[]
        self.pending_solution=None

    def begin(self):
        self.block_index=len(self.portfolio.injection_trace)
        self.global_fe_before=self.portfolio.total_evaluations
        self.front=[tuple(self.normalizer.normalize_tuple(e.objectives))
                    for e in self.portfolio.global_archive.entries]
        self.hv=compute_hypervolume(self.front)
        self.start_index=len(self.rows)
        self.blocks.append(dict(block_index=self.block_index,global_fe_before=self.global_fe_before,
                                starting_points=[list(p) for p in self.front],starting_hv=self.hv))

    def observe(self,arm,objectives):
        point=tuple(self.normalizer.normalize_tuple(objectives))
        before=self.hv
        if not any(all(q[k]<=point[k] for k in range(3)) for q in self.front):
            self.front=[q for q in self.front if not all(point[k]<=q[k] for k in range(3))]
            self.front.append(point)
            self.hv=compute_hypervolume(self.front)
        delta=self.hv-before
        if delta < -1e-12:
            raise RuntimeError('Shadow HV decreased')
        event=self.portfolio.injection.events[-1] if self.portfolio.injection.events else None
        assisted=bool(event and event['block_index']==self.block_index
                      and event['recipient_fe_before_mating']==arm.total_evaluations)
        solution=self.pending_solution
        if solution is None:
            raise RuntimeError('Evaluation has no decoded candidate')
        self.rows.append(dict(block_index=self.block_index,
            global_fe=self.global_fe_before+len(self.rows)-self.start_index+1,
            native_fe=arm.total_evaluations+1,genotype_id=compute_genotype_id(solution),
            sequence=list(solution.sequence),modes=list(solution.modes),objectives=list(objectives),
            normalized_objectives=list(point),shadow_hv_before=before,shadow_hv_after=self.hv,
            marginal_gain=max(0.,delta),assisted=assisted,
            donor_id=event['donor_id'] if assisted else None,
            source='RegionExplorer' if assisted else None))

    def end(self):
        rows=self.rows[self.start_index:]
        block=self.blocks[-1]
        block.update(ending_hv=self.hv,evaluations=len(rows),
            total_child_gain=sum(r['marginal_gain'] for r in rows),
            assisted_child_gain=sum(r['marginal_gain'] for r in rows if r['assisted']),
            assisted_children=sum(r['assisted'] for r in rows))


class ObservedDecoder:
    def __init__(self,delegate,observer):
        self.delegate,self.observer=delegate,observer
    def decode(self,instance,solution):
        self.observer.pending_solution=solution
        return self.delegate.decode(instance,solution)


class ObservedEvaluator:
    def __init__(self,delegate,observer,arm):
        self.delegate,self.observer,self.arm=delegate,observer,arm
    def evaluate(self,instance,schedule):
        result=self.delegate.evaluate(instance,schedule)
        self.observer.observe(self.arm,result)
        return result


class SharedCreditPortfolio(SubproblemInjectedPortfolio):
    def __init__(self,arms,normalizer,instance,seed,alpha):
        if not math.isfinite(alpha) or not 0<=alpha<=1:
            raise ValueError('Alpha must be between zero and one')
        self.alpha=alpha
        super().__init__(arms,normalizer,instance,seed,True,5,10)
        self._install_observer(normalizer)

    def _install_observer(self,normalizer):
        arm=self.get_arm('MOEA/D')
        decoder=arm._decoder.delegate if isinstance(arm._decoder,ObservedDecoder) else arm._decoder
        evaluator=arm._evaluator.delegate if isinstance(arm._evaluator,ObservedEvaluator) else arm._evaluator
        self.observer=OffspringObserver(self,normalizer)
        arm._decoder=ObservedDecoder(decoder,self.observer)
        arm._evaluator=ObservedEvaluator(evaluator,self.observer,arm)
        self.credit_trace=[]

    def reset(self):
        super().reset()
        self._install_observer(self._injection_config[1])

    def run_arm(self,name,budget):
        if name=='MOEA/D':
            self.observer.begin()
        result=super().run_arm(name,budget)
        if name=='MOEA/D':
            self.observer.end()
        return result

    def credit_for(self,record,scored):
        assisted_gain=0.
        if record.arm_name=='MOEA/D':
            block=self.observer.blocks[-1]
            assert block['block_index']==record.block_index
            assert abs(block['total_child_gain']-record.reward)<1e-10
            assisted_gain=block['assisted_child_gain']
            assert assisted_gain<=record.reward+1e-10
        credits=dict.fromkeys(self.arm_names,0.)
        if scored:
            transfer=min(record.reward,self.alpha*assisted_gain)
            credits[record.arm_name]=record.reward-transfer
            if record.arm_name=='MOEA/D':
                credits['RegionExplorer']+=transfer
        self.credit_trace.append(dict(block_index=record.block_index,arm=record.arm_name,
            round_index=record.round_index,scored=scored,raw_reward=record.reward,
            assisted_child_gain=assisted_gain,credits=credits))
        return credits


class SharedCreditOrchestrator(AdaptivePortfolioOrchestrator):
    """Use existing round shares and quotas, replacing only the reward ledger."""
    def run_shared_rounds(self,total_budget,block_size=50,round_size=300,minimum_share=.1):
        names=tuple(self._portfolio.arms)
        if self._history or self._portfolio.total_evaluations:
            raise ValueError('Fresh execution required')
        shares=round_shares(dict.fromkeys(names,0.),minimum_share)
        consumed,index=0,0
        while consumed<total_budget:
            order=names[index%len(names):]+names[:index%len(names)]
            quotas=evaluation_quotas(min(round_size,total_budget-consumed),{n:shares[n] for n in order})
            used=dict.fromkeys(names,0);scored_fe=dict.fromkeys(names,0);gains=dict.fromkeys(names,0.)
            while any(used[n]<quotas[n] for n in names):
                available=[n for n in order if used[n]<quotas[n]]
                name=min(available,key=lambda n:used[n]/quotas[n])
                amount=min(block_size,quotas[name]-used[name])
                warmup=index==0 and used[name]==0
                record=self.run_warmup_block(name,amount)
                assert record.evaluations_used==amount
                self._history[-1]=replace(record,phase='warmup' if warmup else 'dynamic',round_index=index)
                used[name]+=amount;consumed+=amount
                credits=self._portfolio.credit_for(self._history[-1],not warmup)
                if not warmup:
                    assert abs(sum(credits.values())-record.reward)<1e-12
                    scored_fe[name]+=amount
                    for n in names:gains[n]+=credits[n]
            rates={n:gains[n]/scored_fe[n] if scored_fe[n] else 0. for n in names}
            shares=round_shares(rates,minimum_share);index+=1
        return AdaptiveExecutionResult(self._portfolio.total_evaluations,len(self._history),
                                       self._portfolio.global_archive,tuple(self._history))


def run_shared_credit(instance,seed,alpha=.5,budget=3000,population_size=30):
    if not 0<population_size<=50 or budget<100:
        raise ValueError('Budget must cover the initial pair')
    normalizer=ObjectiveNormalizer(compute_instance_bounds(instance))
    arms={'MOEA/D':MOEADArm(instance,population_size=population_size,seed=(seed*10007+17)%(2**31-1)),
          'RegionExplorer':RegionalExplorerArm(instance,normalizer,policy='random',
              seed=(seed*10007+71)%(2**31-1),max_evaluations=budget)}
    portfolio=SharedCreditPortfolio(arms,normalizer,instance,seed,alpha)
    tracker=HypervolumeRewardTracker(normalizer)
    orchestrator=SharedCreditOrchestrator(portfolio,make_selector('uniform',list(arms),seed=seed),tracker)
    start=time.perf_counter()
    execution=orchestrator.run_shared_rounds(budget)
    elapsed=time.perf_counter()-start
    assert execution.total_evaluations==budget
    allocations=Counter()
    for b in execution.history:allocations[b.arm_name]+=b.evaluations_used
    return dict(budget=budget,evaluations_used=budget,alpha=alpha,arms=list(arms),policy='dynamic',
        policy_profile=dict(round_size=300,minimum_share=.1),allocations=dict(allocations),
        hypervolume=tracker.current_hv,runtime_seconds=elapsed,
        blocks=[_block_record(b) for b in execution.history],
        checkpoints=[[b.fe_after,b.hv_after] for b in execution.history],
        pareto_front=[list(e.objectives) for e in portfolio.global_archive.entries],
        front_entries=[dict(sequence=list(e.solution.sequence),modes=list(e.solution.modes),objectives=list(e.objectives))
                       for e in portfolio.global_archive.entries],
        region_trace=arms['RegionExplorer'].trace,migration_events=portfolio.injection.events,
        migration_uses=len(portfolio.injection.events),injection_trace=portfolio.injection_trace,
        child_ledger=portfolio.observer.rows,shadow_blocks=portfolio.observer.blocks,
        credit_trace=portfolio.credit_trace,completed=True)

