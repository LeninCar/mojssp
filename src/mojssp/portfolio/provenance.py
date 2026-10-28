"""Provenance observability and solution life-cycle tracking for MO-JSSP portfolios.

Phase 4 implementation providing non-invasive, bit-for-bit reproducible tracking
of solution origin, ingestion timing, dominance status, evictions, and multiple
provenance for objective vectors in the Global Pareto Archive.
"""

from dataclasses import dataclass, field
from enum import Enum
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union
import csv
import json

from mojssp.algorithms.algorithm_contract import AlgorithmBlockResult, PortfolioArm
from mojssp.metrics.dominance import dominates
from mojssp.model.evaluator import ObjectiveValues
from mojssp.metrics.pareto_archive import ArchiveEntry, ParetoArchive
from mojssp.portfolio.portfolio import Portfolio, PortfolioBlockResult
from mojssp.model.solution import Solution


def compute_genotype_id(solution: Solution) -> str:
    """Compute a deterministic, stable 16-character hex hash identifying a genotype.

    Args:
        solution: Solution genotype (sequence, modes).

    Returns:
        Deterministic SHA-256 prefix hex string.
    """
    key_str = f"seq:{solution.sequence}_modes:{solution.modes}"
    return hashlib.sha256(key_str.encode("utf-8")).hexdigest()[:16]


def compute_objective_key(objectives: ObjectiveValues) -> Tuple[int, int, float]:
    """Extract a canonical tuple representation of the objective vector.

    Args:
        objectives: ObjectiveValues instance.

    Returns:
        Tuple (makespan, tardiness, energy_rounded_4).
    """
    return (int(objectives.makespan), int(objectives.tardiness), round(float(objectives.energy), 4))


class IngestionStatus(str, Enum):
    """Status of a candidate solution presented to the Global Pareto Archive."""

    ACCEPTED_NEW = "ACCEPTED_NEW"
    OBSERVED_INCUMBENT = "OBSERVED_INCUMBENT"
    REJECTED_DOMINATED = "REJECTED_DOMINATED"
    REJECTED_DUPLICATE_GENOTYPE = "REJECTED_DUPLICATE_GENOTYPE"


@dataclass(frozen=True)
class EvictionRecord:
    """Record of an active archive member being evicted due to Pareto dominance.

    Attributes:
        genotype_id: ID of the evicted genotype.
        objective_key: Objectives of the evicted solution.
        original_arm: Arm that originally discovered and introduced the solution.
        ingested_at_block: Block index when the solution entered the archive.
        ingested_at_fe: Global evaluations used when the solution entered.
        evicted_at_block: Block index when the eviction occurred.
        evicted_at_fe: Global evaluations used when the eviction occurred.
        evicted_by_arm: Arm that discovered the dominating solution.
        evicted_by_genotype_id: ID of the dominating genotype.
    """

    genotype_id: str
    objective_key: Tuple[int, int, float]
    original_arm: str
    ingested_at_block: int
    ingested_at_fe: int
    evicted_at_block: int
    evicted_at_fe: int
    evicted_by_arm: str
    evicted_by_genotype_id: str


@dataclass
class SolutionProvenanceRecord:
    """Comprehensive provenance and lifecycle record for a unique genotype.

    Attributes:
        genotype_id: Deterministic hex ID of the genotype.
        objective_key: Canonical objective vector (Cmax, T, E).
        first_observed_arm: Arm that first introduced this solution.
        first_observed_block: Block index of first observation.
        first_observed_ingestion_fe: Accumulated global evaluations at first observation.
        discovery_fe: Exact evaluation index when generated inside the algorithm.
            NOTE: Strictly None in non-invasive mode without algorithm inner-loop instrumentation.
        discovered_by_arms: Set of all arms that independently generated this exact genotype.
        status: Current status: 'ACTIVE', 'DOMINATED_EVICTED', or 'REJECTED_AT_INGESTION'.
        eviction_record: Eviction details if the solution was previously active and evicted.
    """

    genotype_id: str
    objective_key: Tuple[int, int, float]
    first_observed_arm: str
    first_observed_block: int
    first_observed_ingestion_fe: int
    discovery_fe: Optional[int] = None
    discovered_by_arms: Set[str] = field(default_factory=set)
    status: str = "ACTIVE"
    eviction_record: Optional[EvictionRecord] = None


@dataclass(frozen=True)
class BlockProvenanceTrace:
    """Per-block telemetry of solution flow, archive updates, and hypervolume progression.

    Attributes:
        block_index: Sequential index of the executed block (0-indexed).
        arm_selected: Canonical identifier of the executed algorithm arm.
        budget_allocated: Evaluation budget granted for this block.
        evaluations_used: Actual evaluations consumed by the arm.
        ingestion_fe: Cumulative global portfolio evaluations at block end.
        hv_before: Global archive hypervolume before incorporating solutions.
        hv_after: Global archive hypervolume after incorporating solutions.
        delta_hv: Hypervolume change achieved by this block (hv_after - hv_before).
        solutions_offered: Total candidate solutions delivered in the arm's snapshot.
        solutions_accepted_new: Solutions accepted into the global archive for the first time.
        solutions_incumbent: Solutions already present in the archive from previous blocks.
        solutions_rejected_dominated: Solutions rejected because dominated by the global archive.
        solutions_rejected_duplicate: Solutions rejected because duplicate genotype already in archive.
        solutions_evicted: Previously active archive solutions dominated and removed in this block.
        active_archive_size: Size of the global archive after this block.
    """

    block_index: int
    arm_selected: str
    budget_allocated: int
    evaluations_used: int
    ingestion_fe: int
    hv_before: float
    hv_after: float
    delta_hv: float
    solutions_offered: int
    solutions_accepted_new: int
    solutions_incumbent: int
    solutions_rejected_dominated: int
    solutions_rejected_duplicate: int
    solutions_evicted: int
    active_archive_size: int


class ProvenanceTracker:
    """Observer that records fine-grained solution provenance and lifecycle events.

    Maintains:
    - Unique genotype registry with origin, ingestion timing, and eviction tracking.
    - Objective-vector multiple provenance mapping (tracks all arms finding each objective triple).
    - Chronological block traces of ingestion outcomes and hypervolume deltas.
    """

    def __init__(self) -> None:
        self._solutions: Dict[str, SolutionProvenanceRecord] = {}
        self._objective_arms: Dict[Tuple[int, int, float], Set[str]] = {}
        self._block_traces: List[BlockProvenanceTrace] = []
        self._evictions: List[EvictionRecord] = []
        self._seen_genotypes_by_arm: Dict[str, Set[str]] = {}

    @property
    def solutions(self) -> Dict[str, SolutionProvenanceRecord]:
        """All recorded solutions indexed by genotype_id."""
        return self._solutions

    @property
    def objective_provenance(self) -> Dict[Tuple[int, int, float], Set[str]]:
        """Mapping from objective vector (Cmax, T, E) to set of arms that produced it."""
        return {k: set(v) for k, v in self._objective_arms.items()}

    @property
    def block_traces(self) -> Tuple[BlockProvenanceTrace, ...]:
        """Chronological sequence of all block provenance records."""
        return tuple(self._block_traces)

    @property
    def evictions(self) -> Tuple[EvictionRecord, ...]:
        """All recorded solution eviction events."""
        return tuple(self._evictions)

    def register_observation(
        self,
        arm_name: str,
        solution: Solution,
        objectives: ObjectiveValues,
        block_index: int,
        ingestion_fe: int,
    ) -> Tuple[str, Tuple[int, int, float], bool]:
        """Register an arm producing a solution, tracking multiple provenance.

        Returns:
            Tuple (genotype_id, objective_key, is_reobservation_by_this_arm).
        """
        gid = compute_genotype_id(solution)
        okey = compute_objective_key(objectives)

        # Track multiple provenance for the objective vector
        if okey not in self._objective_arms:
            self._objective_arms[okey] = set()
        self._objective_arms[okey].add(arm_name)

        # Track multiple provenance for the exact genotype
        is_reobservation = False
        if arm_name not in self._seen_genotypes_by_arm:
            self._seen_genotypes_by_arm[arm_name] = set()

        if gid in self._seen_genotypes_by_arm[arm_name]:
            is_reobservation = True
        else:
            self._seen_genotypes_by_arm[arm_name].add(gid)

        if gid not in self._solutions:
            self._solutions[gid] = SolutionProvenanceRecord(
                genotype_id=gid,
                objective_key=okey,
                first_observed_arm=arm_name,
                first_observed_block=block_index,
                first_observed_ingestion_fe=ingestion_fe,
                discovery_fe=None,  # Not observable without inner-loop instrumentation
                discovered_by_arms={arm_name},
                status="ACTIVE",
            )
        else:
            self._solutions[gid].discovered_by_arms.add(arm_name)

        return gid, okey, is_reobservation

    def record_eviction(self, record: EvictionRecord) -> None:
        """Record the eviction of a previously active member."""
        self._evictions.append(record)
        if record.genotype_id in self._solutions:
            sol_rec = self._solutions[record.genotype_id]
            sol_rec.status = "DOMINATED_EVICTED"
            sol_rec.eviction_record = record

    def record_block_trace(self, trace: BlockProvenanceTrace) -> None:
        """Append a block provenance trace."""
        self._block_traces.append(trace)

    def get_arm_contribution_summary(self) -> Dict[str, Dict[str, Any]]:
        """Compute aggregated provenance statistics per algorithm arm."""
        summary: Dict[str, Dict[str, Any]] = {}
        for rec in self._solutions.values():
            arm = rec.first_observed_arm
            if arm not in summary:
                summary[arm] = {
                    "total_unique_genotypes_introduced": 0,
                    "currently_active_in_archive": 0,
                    "evicted_by_dominance": 0,
                    "rejected_at_ingestion": 0,
                }
            summary[arm]["total_unique_genotypes_introduced"] += 1
            if rec.status == "ACTIVE":
                summary[arm]["currently_active_in_archive"] += 1
            elif rec.status == "DOMINATED_EVICTED":
                summary[arm]["evicted_by_dominance"] += 1
            else:
                summary[arm]["rejected_at_ingestion"] += 1
        return summary

    def export_traces_to_dict(self) -> Dict[str, Any]:
        """Export all captured provenance telemetry into a serializable dictionary."""
        return {
            "summary_by_arm": self.get_arm_contribution_summary(),
            "objective_vector_multiple_provenance": [
                {
                    "objective_key": list(okey),
                    "arms_count": len(arms),
                    "arms": sorted(list(arms)),
                }
                for okey, arms in self._objective_arms.items()
                if len(arms) > 1
            ],
            "total_evictions": len(self._evictions),
            "evictions": [
                {
                    "genotype_id": e.genotype_id,
                    "objective_key": list(e.objective_key),
                    "original_arm": e.original_arm,
                    "ingested_at_block": e.ingested_at_block,
                    "evicted_at_block": e.evicted_at_block,
                    "evicted_by_arm": e.evicted_by_arm,
                    "evicted_by_genotype_id": e.evicted_by_genotype_id,
                }
                for e in self._evictions
            ],
            "block_traces": [
                {
                    "block_index": b.block_index,
                    "arm_selected": b.arm_selected,
                    "budget_allocated": b.budget_allocated,
                    "evaluations_used": b.evaluations_used,
                    "ingestion_fe": b.ingestion_fe,
                    "hv_before": b.hv_before,
                    "hv_after": b.hv_after,
                    "delta_hv": b.delta_hv,
                    "solutions_offered": b.solutions_offered,
                    "solutions_accepted_new": b.solutions_accepted_new,
                    "solutions_incumbent": b.solutions_incumbent,
                    "solutions_rejected_dominated": b.solutions_rejected_dominated,
                    "solutions_rejected_duplicate": b.solutions_rejected_duplicate,
                    "solutions_evicted": b.solutions_evicted,
                    "active_archive_size": b.active_archive_size,
                }
                for b in self._block_traces
            ],
        }


class ProvenanceObservingPortfolio(Portfolio):
    """Subclass of Portfolio that intercepts block updates to record solution provenance.

    Maintains bit-for-bit equivalence with standard Portfolio when enabled, and behaves
    identically to Portfolio when disabled or when no tracker is attached.
    Does not consume additional evaluations and does not modify random number streams.
    """

    def __init__(
        self,
        arms: Optional[Union[Sequence[PortfolioArm], Dict[str, PortfolioArm]]] = None,
        tracker: Optional[ProvenanceTracker] = None,
        enabled: bool = True,
    ) -> None:
        super().__init__(arms=arms)
        self.tracker = tracker if tracker is not None else (ProvenanceTracker() if enabled else None)
        self.enabled = enabled
        self._block_counter = 0

    def run_arm(self, name: str, budget: int) -> PortfolioBlockResult:
        """Execute a budget block on the arm and capture provenance telemetry."""
        if not self.enabled or self.tracker is None:
            return super().run_arm(name, budget)

        arm = self.get_arm(name)
        canonical_name = arm.arm_name
        current_block = self._block_counter
        self._block_counter += 1

        fe_before = self._total_evaluations

        # Execute block on the underlying arm (untouched logic and budget accounting)
        result: AlgorithmBlockResult = arm.run(budget)
        fe_after = fe_before + result.evaluations_used

        offered_entries = result.solutions.entries if (result.solutions and not result.solutions.is_empty) else ()
        solutions_offered = len(offered_entries)

        accepted_new = 0
        incumbent_count = 0
        rejected_dominated = 0
        rejected_duplicate = 0
        evicted_count = 0

        # Snapshot active entries map by genotype before updating
        archive_before_map = {compute_genotype_id(e.solution): e for e in self._global_archive.entries}

        for entry in offered_entries:
            gid, okey, is_reobs = self.tracker.register_observation(
                arm_name=canonical_name,
                solution=entry.solution,
                objectives=entry.objectives,
                block_index=current_block,
                ingestion_fe=fe_after,
            )

            # Check if this exact genotype is already active in global archive
            if gid in archive_before_map:
                incumbent_count += 1
                continue

            # Check if candidate is dominated by any existing member in global archive
            is_dom = False
            for existing in self._global_archive.entries:
                if dominates(existing.objectives, entry.objectives):
                    is_dom = True
                    break

            if is_dom:
                rejected_dominated += 1
                if gid in self.tracker.solutions and self.tracker.solutions[gid].status == "ACTIVE":
                    self.tracker.solutions[gid].status = "REJECTED_AT_INGESTION"
                continue

            # Check if candidate duplicates genotype in current archive (precautionary)
            if any(existing.solution == entry.solution for existing in self._global_archive.entries):
                rejected_duplicate += 1
                continue

            # Candidate is non-dominated: identify existing members that will be evicted
            evicted_in_this_step = [
                existing
                for existing in self._global_archive.entries
                if dominates(entry.objectives, existing.objectives)
            ]

            for ev in evicted_in_this_step:
                ev_gid = compute_genotype_id(ev.solution)
                ev_okey = compute_objective_key(ev.objectives)
                orig_arm = (
                    self.tracker.solutions[ev_gid].first_observed_arm
                    if ev_gid in self.tracker.solutions
                    else "UNKNOWN"
                )
                orig_block = (
                    self.tracker.solutions[ev_gid].first_observed_block
                    if ev_gid in self.tracker.solutions
                    else 0
                )
                orig_fe = (
                    self.tracker.solutions[ev_gid].first_observed_ingestion_fe
                    if ev_gid in self.tracker.solutions
                    else 0
                )
                self.tracker.record_eviction(
                    EvictionRecord(
                        genotype_id=ev_gid,
                        objective_key=ev_okey,
                        original_arm=orig_arm,
                        ingested_at_block=orig_block,
                        ingested_at_fe=orig_fe,
                        evicted_at_block=current_block,
                        evicted_at_fe=fe_after,
                        evicted_by_arm=canonical_name,
                        evicted_by_genotype_id=gid,
                    )
                )
                evicted_count += 1

            # Insert candidate into the global archive using standard logic
            added = self._global_archive.add_entry(entry)
            if added:
                accepted_new += 1
                archive_before_map[gid] = entry

        # Update evaluation counter
        self._total_evaluations += result.evaluations_used

        # Note: Hypervolume before/after can be retrieved from RewardTracker in Orchestrator
        # Default placeholder here; orchestrator or runner can attach exact HV
        trace = BlockProvenanceTrace(
            block_index=current_block,
            arm_selected=canonical_name,
            budget_allocated=budget,
            evaluations_used=result.evaluations_used,
            ingestion_fe=self._total_evaluations,
            hv_before=0.0,
            hv_after=0.0,
            delta_hv=0.0,
            solutions_offered=solutions_offered,
            solutions_accepted_new=accepted_new,
            solutions_incumbent=incumbent_count,
            solutions_rejected_dominated=rejected_dominated,
            solutions_rejected_duplicate=rejected_duplicate,
            solutions_evicted=evicted_count,
            active_archive_size=len(self._global_archive),
        )
        self.tracker.record_block_trace(trace)

        return PortfolioBlockResult(
            arm_name=canonical_name,
            evaluations_used=result.evaluations_used,
            completed=result.completed,
            global_archive=self.global_archive,
            arm_result=result,
        )

    def reset(self) -> None:
        """Reset portfolio and block counter."""
        super().reset()
        self._block_counter = 0
