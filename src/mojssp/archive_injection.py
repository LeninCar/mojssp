"""Unidirectional archive migration through a bounded external-parent pool."""
import math

from .provenance import compute_genotype_id


class ArchiveParentInjection:
    """Use at most m foreign parents per recipient block, without population replacement.

    Observe each arm immediately after it executes. Origin means first observed
    archive or current population membership, not unobserved genetic ancestry.
    Donors must remain in the global archive and originate from the source arm.
    Selection is deterministic max-min objective distance and uses no RNG draws.
    Native offspring decoding, evaluation, mutation and replacement remain intact.
    """

    def __init__(self, instance, normalizer, source='SPEA2', recipient='MOEA/D', m=5, every=10):
        if source==recipient:
            raise ValueError('Migration requires distinct source and recipient')
        if any(isinstance(v,bool) or not isinstance(v,int) or v<1 for v in (m,every)):
            raise ValueError('m and every must be positive integers')
        self.instance,self.normalizer = instance,normalizer
        self.source,self.recipient,self.m,self.every = source,recipient,m,every
        self.origins,self.seen_by = {},{}
        self.events = []
        self.reset_block()

    def reset_block(self):
        self._donors = []
        self._mating_count = 0
        self._next_donor = 0
        self.block_index = None
        self.global_fe_before = None

    def observe(self, arm):
        if arm._instance is not self.instance:
            raise ValueError('Cannot observe another instance')
        solutions = [entry.solution for entry in arm.current_archive.entries]
        if hasattr(arm,'subproblems'):
            solutions += [sub.solution for sub in arm.subproblems]
        observed = self.seen_by.setdefault(arm.arm_name,set())
        for solution in solutions:
            gid = compute_genotype_id(solution)
            observed.add(gid)
            self.origins.setdefault(gid,arm.arm_name)

    def prepare(self, arm, global_archive, block_index, global_fe_before):
        if arm._instance is not self.instance or arm.arm_name!=self.recipient:
            raise ValueError('Invalid recipient')
        self.reset_block()
        self.block_index,self.global_fe_before = block_index,global_fe_before
        local = list(arm.current_archive.entries)
        anchors = [self.normalizer.normalize_tuple(entry.objectives) for entry in local]
        if not anchors:
            return []
        seen = self.seen_by.get(self.recipient,set())
        candidates = [entry for entry in global_archive.entries
                      if self.origins.get(compute_genotype_id(entry.solution))==self.source
                      and compute_genotype_id(entry.solution) not in seen]
        while candidates and len(self._donors)<self.m:
            donor = max(candidates,key=lambda entry:(
                min(math.dist(self.normalizer.normalize_tuple(entry.objectives),p) for p in anchors),
                compute_genotype_id(entry.solution)))
            candidates.remove(donor)
            self._donors.append(donor)
            anchors.append(self.normalizer.normalize_tuple(donor.objectives))
        return [compute_genotype_id(entry.solution) for entry in self._donors]

    def parent(self, arm, native_parent):
        if arm.arm_name!=self.recipient or arm._instance is not self.instance:
            raise ValueError('Only the designated recipient may receive parents')
        self._mating_count += 1
        if self._mating_count % self.every or self._next_donor>=len(self._donors):
            return native_parent
        donor = self._donors[self._next_donor]
        self._next_donor += 1
        if donor.solution==native_parent:
            return native_parent
        self.events.append(dict(block_index=self.block_index,global_fe_before=self.global_fe_before,
            recipient_fe_before_mating=arm.total_evaluations,source=self.source,recipient=self.recipient,
            mating_index=self._mating_count,donor_id=compute_genotype_id(donor.solution),
            native_parent_id=compute_genotype_id(native_parent),
            donor_sequence=list(donor.solution.sequence),donor_modes=list(donor.solution.modes),
            donor_objectives=list(donor.objectives)))
        return donor.solution
