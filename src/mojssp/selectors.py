"""Budget-selection policies shared by the experiment runner."""
import math

from .dmab import ArmStats, RoundRobinSelector, SlidingWindowUCB
from .page_hinkley import ClassicalUCB1Selector, PageHinkleyDMABSelector

class ScaleAwareUCB(SlidingWindowUCB):
    """Raw ΔHV is stored intact; normalize exploitation at decision time only.

    Divide all recent rewards by their common maximum, including earlier
    observations (not a per-observation moving denominator). Zero windows use
    scale one, retaining ordinary exploration. Expired arms retain infinite
    UCB, hence remain eligible for complementary discoveries.
    """

    def _compute_arm_stats(self, arm_name):
        stats = super()._compute_arm_stats(arm_name)
        if stats.window_pulls == 0:
            return stats
        scale = max((abs(r) for _, r in self._window), default=0.0) or 1.0
        mean = stats.window_mean / scale
        t_eff = min(self._total_pulls, self._window_size)
        bonus = self._c * math.sqrt(math.log(t_eff) / stats.window_pulls) if t_eff > 1 else 0.0
        return ArmStats(stats.arm_name, stats.total_pulls, stats.window_pulls,
                        stats.window_mean, mean+bonus)



POLICIES = ('uniform', 'sw_ucb', 'scaled', 'ph')
ALIASES = {'adaptive': 'sw_ucb', 'dmab_ph': 'ph'}


def make_selector(policy, arm_names, *, seed=None, window_size=10,
                  exploration_factor=0.07, delta=0.001, threshold=0.05,
                  min_instances=5, feed_initial_probe_to_detector=False,
                  feed_reexploration_to_detector=False):
    policy = ALIASES.get(policy, policy)
    if policy == 'uniform':
        return RoundRobinSelector(arm_names)
    if policy in ('sw_ucb', 'scaled'):
        selector = SlidingWindowUCB if policy == 'sw_ucb' else ScaleAwareUCB
        return selector(arm_names, window_size=window_size,
                        exploration_factor=exploration_factor, seed=seed)
    if policy == 'ph':
        return PageHinkleyDMABSelector(arm_names, exploration_factor=exploration_factor,
            delta=delta, threshold=threshold, min_instances=min_instances,
            feed_initial_probe_to_detector=feed_initial_probe_to_detector,
            feed_reexploration_to_detector=feed_reexploration_to_detector, seed=seed)
    if policy == 'ucb1':
        return ClassicalUCB1Selector(arm_names, exploration_factor=exploration_factor, seed=seed)
    raise ValueError(f'Unknown policy: {policy}')
