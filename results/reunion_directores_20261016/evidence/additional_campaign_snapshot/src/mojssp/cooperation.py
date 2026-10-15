"""Cooperation protocol, selection policies, and data structures for active solution exchange in MO-JSSP.

P6 Implementation: Enables stateful algorithm arms (MOEA/D, NSGA-II, SPEA2) to receive
pre-evaluated, non-dominated external solutions from other portfolio arms via the
Global Pareto Archive without re-evaluation, budget inflation, or invariant violations.
"""

from dataclasses import dataclass
import random
import time
from typing import Any, Dict, List, Optional, Protocol, Sequence, Tuple, Union, runtime_checkable

from .algorithm_contract import PortfolioArm
from .dominance import dominates
from .pareto_archive import ArchiveEntry, ParetoArchive
from .portfolio import Portfolio, PortfolioBlockResult
from .provenance import (
    BlockProvenanceTrace,
    EvictionRecord,
    ProvenanceObservingPortfolio,
    ProvenanceTracker,
    compute_genotype_id,
    compute_objective_key,
)
from .solution import Solution


@dataclass(frozen=True)
class ExternalSolutionOffer:
    """Pre-evaluated candidate solution offered to an algorithm arm for cooperation.

    Attributes:
        entry: Valid ArchiveEntry containing Solution, Schedule, and ObjectiveValues.
        source_arm: Canonical name of the algorithm arm that originally discovered the solution.
        global_archive_fe: Cumulative global evaluations at the time of injection.
    """

    entry: ArchiveEntry
    source_arm: str
    global_archive_fe: int


@dataclass(frozen=True)
class InjectionResult:
    """Detailed outcome of offering external solutions to an algorithm arm.

    Attributes:
        arm_name: Identifier of the target algorithm arm.
        offered_count: Total solutions offered to the arm (0 <= offered_count <= max_injections).
        accepted_count: Solutions accepted and incorporated into the internal population/subproblems.
        rejected_duplicate_count: Solutions rejected because identical genotype already present in arm.
        rejected_dominated_count: Solutions rejected because dominated or worse than arm incumbents.
        accepted_genotype_ids: Tuple of deterministic hex IDs of successfully accepted genotypes.
        surviving_in_population: Number of accepted solutions surviving in the arm's population at block end.
        injection_time_seconds: Overhead time in seconds spent evaluating and injecting solutions.
    """

    arm_name: str
    offered_count: int
    accepted_count: int
    rejected_duplicate_count: int
    rejected_dominated_count: int
    accepted_genotype_ids: Tuple[str, ...]
    surviving_in_population: int = 0
    injection_time_seconds: float = 0.0


@runtime_checkable
class CooperativeArm(Protocol):
    """Protocol for portfolio arms capable of receiving external evaluated solutions."""

    def inject_solutions(
        self, offers: Sequence[ExternalSolutionOffer]
    ) -> InjectionResult:
        """Attempt to incorporate external evaluated solutions into the arm's internal state.

        Args:
            offers: Sequence of ExternalSolutionOffer instances (at most max_injections).

        Returns:
            InjectionResult detailing acceptances and rejections.
        """
        ...

    def get_injected_survivors_count(self, genotype_ids: Sequence[str]) -> int:
        """Count how many of the specified injected genotypes currently remain in the arm's population."""
        ...


class CooperativePortfolio(ProvenanceObservingPortfolio):
    """Portfolio subclass orchestrating active, bounded solution injection between arms.

    Features:
    - Disabled by default (enabled=False reproduces exact passive portfolio behavior).
    - Invariant: Exact same total calls to Evaluator.evaluate() (zero additional evaluations).
    - Warm-up & probe protection: Injections occur exclusively from block_index >= min_block_index
      (default: block 6, after 150 FE warmup + 150 FE initial probe).
    - Rate-bounded: At most max_injections (default: 2) solutions offered per block.
    - Strict cross-provenance: Only solutions discovered by OTHER arms are offered.
    - Genotype deduplication: Identical genotypes are rejected before altering arm state.
    - Comprehensive telemetry: Tracks offers, acceptances, rejections, survivor retention,
      and wall-clock overhead.
    """

    def __init__(
        self,
        arms: Optional[Union[Sequence[PortfolioArm], Dict[str, PortfolioArm]]] = None,
        tracker: Optional[ProvenanceTracker] = None,
        cooperation_enabled: bool = False,
        observability_enabled: bool = True,
        max_injections_per_block: int = 2,
        min_cooperation_block: int = 6,
        seed: Optional[int] = 42,
    ) -> None:
        super().__init__(arms=arms, tracker=tracker, enabled=observability_enabled)
        self.cooperation_enabled = cooperation_enabled
        self.max_injections_per_block = max_injections_per_block
        self.min_cooperation_block = min_cooperation_block
        self._rng = random.Random(seed)
        self._injection_history: List[InjectionResult] = []

    @property
    def injection_history(self) -> Tuple[InjectionResult, ...]:
        """Chronological tuple of all injection results across executed blocks."""
        return tuple(self._injection_history)

    def select_cooperative_offers(
        self, target_arm_name: str
    ) -> List[ExternalSolutionOffer]:
        """Select up to max_injections_per_block eligible external solutions for the target arm.

        Eligibility criteria:
        1. Solution must be currently active in the Global Pareto Archive.
        2. Solution must have been originally discovered by an arm OTHER than target_arm_name.
        3. Deterministic selection prioritizing boundary and diverse points.

        Args:
            target_arm_name: Canonical name of the arm about to be executed.

        Returns:
            List of ExternalSolutionOffer instances (length <= max_injections_per_block).
        """
        if not self.cooperation_enabled or self.tracker is None:
            return []

        # Find active archive entries discovered by other arms
        eligible_offers: List[ExternalSolutionOffer] = []

        for entry in self._global_archive.entries:
            gid = compute_genotype_id(entry.solution)
            sol_rec = self.tracker.solutions.get(gid)
            if sol_rec is None:
                continue

            orig_arm = sol_rec.first_observed_arm
            if orig_arm != target_arm_name and sol_rec.status == "ACTIVE":
                eligible_offers.append(
                    ExternalSolutionOffer(
                        entry=entry,
                        source_arm=orig_arm,
                        global_archive_fe=self._total_evaluations,
                    )
                )

        if not eligible_offers:
            return []

        # Bounded selection: Pick up to max_injections_per_block solutions
        # To maintain strict determinism without external RNG disruption, sample or pick extremes
        if len(eligible_offers) <= self.max_injections_per_block:
            return list(eligible_offers)

        # Deterministic sorting: sort by objective values (makespan, tardiness, energy) ascending
        eligible_offers.sort(
            key=lambda off: (
                off.entry.objectives.makespan,
                off.entry.objectives.tardiness,
                off.entry.objectives.energy,
            )
        )
        # Select extremes (first and last) to maximize diversity coverage
        selected = [eligible_offers[0]]
        if self.max_injections_per_block >= 2:
            selected.append(eligible_offers[-1])
        return selected[: self.max_injections_per_block]

    def run_arm(self, name: str, budget: int) -> PortfolioBlockResult:
        """Execute a budget block on the arm with optional active cooperation before execution."""
        arm = self.get_arm(name)
        canonical_name = arm.arm_name
        current_block = self._block_counter

        # 1. Active Cooperation Phase (pre-execution injection)
        injection_res: Optional[InjectionResult] = None
        t_inj_start = time.perf_counter()

        if (
            self.cooperation_enabled
            and current_block >= self.min_cooperation_block
            and isinstance(arm, CooperativeArm)
        ):
            offers = self.select_cooperative_offers(canonical_name)
            if offers:
                inj_out = arm.inject_solutions(offers)
                t_inj_duration = time.perf_counter() - t_inj_start
                # Attach injection time
                injection_res = InjectionResult(
                    arm_name=inj_out.arm_name,
                    offered_count=inj_out.offered_count,
                    accepted_count=inj_out.accepted_count,
                    rejected_duplicate_count=inj_out.rejected_duplicate_count,
                    rejected_dominated_count=inj_out.rejected_dominated_count,
                    accepted_genotype_ids=inj_out.accepted_genotype_ids,
                    surviving_in_population=inj_out.surviving_in_population,
                    injection_time_seconds=t_inj_duration,
                )
                self._injection_history.append(injection_res)

        # 2. Execute block via standard ProvenanceObservingPortfolio logic
        block_res = super().run_arm(name, budget)

        # 3. Post-execution survivor update: if solutions were accepted, re-check survival in arm
        if injection_res is not None and injection_res.accepted_count > 0 and isinstance(arm, CooperativeArm):
            surv_now = arm.get_injected_survivors_count(injection_res.accepted_genotype_ids)
            # Update the last recorded injection result with post-block survival count
            self._injection_history[-1] = InjectionResult(
                arm_name=injection_res.arm_name,
                offered_count=injection_res.offered_count,
                accepted_count=injection_res.accepted_count,
                rejected_duplicate_count=injection_res.rejected_duplicate_count,
                rejected_dominated_count=injection_res.rejected_dominated_count,
                accepted_genotype_ids=injection_res.accepted_genotype_ids,
                surviving_in_population=surv_now,
                injection_time_seconds=injection_res.injection_time_seconds,
            )

        return block_res

    def reset(self) -> None:
        """Reset portfolio, provenance tracker, and injection history."""
        super().reset()
        self._injection_history.clear()
