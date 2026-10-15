"""Budget, native-selection, diversity and forgetting safety of research mechanisms."""
from pathlib import Path
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from mojssp.arms import NSGA2Arm
from mojssp.cooperation import ArchiveGuidance, ScaleAwareUCB
from mojssp.evaluator import Evaluator
from mojssp.io import load_dzn
from mojssp.moead import MOEADArm
from mojssp.normalization import ObjectiveNormalizer, compute_instance_bounds
from mojssp.provenance import compute_genotype_id
from mojssp.schedule_validator import validate_schedule
from mojssp.spea2 import SPEA2Arm


@pytest.fixture
def instance():
    return load_dzn(Path(__file__).resolve().parents[1] / 'data/validation/toy_instance.dzn')


def arm_for(kind, instance, seed=42):
    kw = dict(instance=instance, population_size=10, seed=seed, max_evaluations=300)
    if kind is NSGA2Arm:
        kw['max_generations'] = None
    return kind(**kw)


@pytest.mark.parametrize('kind', [MOEADArm, NSGA2Arm, SPEA2Arm])
def test_guidance_evaluates_every_child_and_preserves_native_state(instance, kind):
    donor = arm_for(MOEADArm, instance, 999)
    donor.run(150)
    arm = arm_for(kind, instance)
    arm.run(50)
    guide = ArchiveGuidance(instance, ObjectiveNormalizer(compute_instance_bounds(instance)), every=2)
    first = {compute_genotype_id(e.solution): 'donor' for e in donor.current_archive.entries}
    assert guide.prepare(arm, donor.current_archive, first) is not None
    arm.set_archive_guidance(guide)
    before_rng = arm._rng.getstate()
    before_archive = arm.current_archive.entries
    # Preparing and installing transfers no population member or objective value.
    assert arm.current_archive.entries == before_archive
    assert arm._rng.getstate() == before_rng
    counter = 0
    original = Evaluator.evaluate
    def counted(self, *args, **kw):
        nonlocal counter
        counter += 1
        return original(self, *args, **kw)
    with patch.object(Evaluator, 'evaluate', counted):
        for cut in [1, 7, 42, 100, 100]:
            r = arm.run(cut)
            assert r.evaluations_used <= cut
    assert counter == 250
    assert arm.total_evaluations == 300
    assert guide.uses > 0
    for entry in arm.current_archive.entries:
        entry.solution.validate_with_instance(instance)
        assert validate_schedule(instance, entry.schedule) == []
        assert Evaluator().evaluate(instance, entry.schedule) == entry.objectives
    if kind is MOEADArm:
        assert len(arm.subproblems) == 10
        assert tuple(s.weight for s in arm.subproblems) == arm.weight_vectors
        assert all(s.normalized_objectives[k] >= arm.ideal_point[k]
                   for s in arm.subproblems for k in range(3))
    arm.reset()
    assert arm._archive_guidance is None
    assert arm.total_evaluations == 0


@pytest.mark.parametrize('kind', [MOEADArm, NSGA2Arm, SPEA2Arm])
def test_disabled_guidance_does_not_consume_randomness(instance, kind):
    a, b = arm_for(kind, instance), arm_for(kind, instance)
    b.set_archive_guidance(None)
    a.run(300)
    for cut in [1, 19, 50, 30, 200]:
        b.run(cut)
    assert a.current_archive.entries == b.current_archive.entries
    assert a._rng.getstate() == b._rng.getstate()


def test_cross_instance_guidance_rejected(instance):
    other = load_dzn(Path(__file__).resolve().parents[1] / 'data/validation/toy_instance.dzn')
    guide = ArchiveGuidance(other, ObjectiveNormalizer(compute_instance_bounds(other)))
    with pytest.raises(ValueError):
        arm_for(MOEADArm, instance).set_archive_guidance(guide)


def test_scaled_ucb_invariant_to_reward_units_and_retains_revisits():
    a = ScaleAwareUCB(['a', 'b', 'c'], window_size=10, exploration_factor=.07, seed=42)
    b = ScaleAwareUCB(['a', 'b', 'c'], window_size=10, exploration_factor=.07, seed=42)
    selections = []
    for i in range(200):
        selected = a.select_arm()
        assert selected == b.select_arm()
        selections.append(selected)
        reward = (1.0 if selected == 'a' else 0.001) / (i+1)
        a.update(selected, reward)
        b.update(selected, reward*1e-9)
    assert selections.count('a') > 100
    for name in a.arm_names:
        positions = [i for i,n in enumerate(selections) if n == name]
        assert max(y-x for x,y in zip(positions, positions[1:])) <= 12


def test_zero_rewards_and_expired_arms_are_finite_or_infinite_as_expected():
    s = ScaleAwareUCB(['a','b'], window_size=3, seed=1)
    for i in range(50):
        s.update(s.select_arm(), 0.)
    assert s.get_adaptive_pulls('a') > 10
    assert s.get_adaptive_pulls('b') > 10
    s.update('a', 1.)
    s.update('a', 1.)
    s.update('a', 1.)
    assert s.select_arm() == 'b'
