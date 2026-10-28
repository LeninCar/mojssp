"""Opt-in research mechanisms. Existing algorithms remain unguided by default.

Global entries supply genotypes only. Their offspring always use the native
decoder/evaluator/selection path; no cached fitness is assigned to a new child.
"""
from collections import defaultdict
import math

from mojssp.portfolio.selectors import ScaleAwareUCB
from mojssp.portfolio.provenance import compute_genotype_id


class GuidedMatingArm:
    """Optional external parent hook; does not replace population incumbents."""

    def set_archive_guidance(self, guidance):
        if guidance is not None and guidance.instance is not self._instance:
            raise ValueError('Guidance must belong to the identical instance object')
        self._archive_guidance = guidance

    def _guided_parent(self, native_parent):
        guide = getattr(self, '_archive_guidance', None)
        return guide.parent(self, native_parent) if guide else native_parent


class ArchiveGuidance:
    """Distant foreign Pareto parent at a bounded, deterministic mating cadence.

    Each block freezes one donor. The donor must be first observed in another
    arm and absent from the recipient's archive. Cadence is per arm, persists
    across blocks and consumes no RNG draws. No genotype is inserted directly
    in any local archive. First observation is not a genetic ancestry claim.
    """

    def __init__(self, instance, normalizer, every=10):
        if isinstance(every, bool) or not isinstance(every, int) or every < 1:
            raise ValueError('every must be a positive integer')
        self.instance = instance
        self.normalizer = normalizer
        self.every = every
        self.reset()

    def reset(self):
        self._counts = defaultdict(int)
        self._donors = {}
        self.events = []
        self.uses = 0

    def prepare(self, arm, archive, first_seen):
        if arm._instance is not self.instance:
            raise ValueError('Cannot exchange across problem instances')
        local = arm.current_archive.entries
        local_ids = {compute_genotype_id(e.solution) for e in local}
        points = [self.normalizer.normalize_tuple(e.objectives) for e in local]
        foreign = [e for e in archive.entries
                   if compute_genotype_id(e.solution) not in local_ids
                   and first_seen.get(compute_genotype_id(e.solution)) not in (None, arm.arm_name)]
        self._donors[arm.arm_name] = None
        if not points or not foreign:
            return None
        # Genotype ID makes equal-distance choices independent of archive order.
        donor = max(foreign, key=lambda e: (
            min(math.dist(self.normalizer.normalize_tuple(e.objectives), p) for p in points),
            compute_genotype_id(e.solution)))
        self._donors[arm.arm_name] = donor
        return compute_genotype_id(donor.solution)

    def parent(self, arm, native_parent):
        self._counts[arm.arm_name] += 1
        donor = self._donors.get(arm.arm_name)
        if donor is None or self._counts[arm.arm_name] % self.every:
            return native_parent
        if donor.solution == native_parent:
            return native_parent
        self.uses += 1
        self.events.append({'recipient': arm.arm_name,
                            'recipient_fe_before_mating': arm.total_evaluations,
                            'donor_id': compute_genotype_id(donor.solution),
                            'native_parent_id': compute_genotype_id(native_parent),
                            'mating_index': self._counts[arm.arm_name]})
        return donor.solution
