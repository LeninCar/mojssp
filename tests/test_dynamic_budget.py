from pathlib import Path
from collections import defaultdict

import pytest

from mojssp.portfolio.dynamic_budget import round_shares
from mojssp.portfolio.fixed_budget import evaluation_quotas
from mojssp.model.io import load_dzn
from mojssp.portfolio.runner import run_phase2_portfolio_experiment


def test_scores_are_productivity_not_raw_gain():
    shares = round_shares({"a": 0.2 / 100, "b": 0.1 / 50, "c": 0})
    assert shares == pytest.approx({"a": 0.45, "b": 0.45, "c": 0.1})
    assert round_shares({"a": 0, "b": 0, "c": 0}) == pytest.approx(dict.fromkeys(["a", "b", "c"], 1 / 3))


def test_dynamic_rounds_reproduce_the_registered_rule_and_exact_budget():
    instance = load_dzn(Path(__file__).resolve().parents[1] / "data/validation/small_3x3.dzn")
    arguments = dict(
        seed=42,
        total_budget=641,
        block_size=20,
        population_size=10,
        policy="dynamic",
        round_size=120,
        minimum_share=0.1,
    )
    first, history = run_phase2_portfolio_experiment(instance, **arguments)
    second, replay = run_phase2_portfolio_experiment(instance, **arguments)
    assert first.evaluations_used == 641
    assert first.pareto_front == second.pareto_front and history == replay
    groups = defaultdict(list)
    for block in history:
        groups[block.round_index].append(block)
    names = ["MOEA/D", "NSGA-II", "SPEA2"]
    shares = dict.fromkeys(names, 1 / 3)
    for index, blocks in sorted(groups.items()):
        order = names[index % 3 :] + names[: index % 3]
        expected = evaluation_quotas(min(120, 641 - 120 * index), {name: shares[name] for name in order})
        actual = {name: sum(b.evaluations_used for b in blocks if b.arm_name == name) for name in names}
        assert actual == expected
        scores = {}
        for name in names:
            scored = [b for b in blocks if b.arm_name == name and b.phase != "warmup"]
            scores[name] = (
                sum(b.reward for b in scored) / sum(b.evaluations_used for b in scored) if scored else 0.0
            )
        shares = round_shares(scores)
    assert sum(b.phase == "warmup" for b in history) == 3


def test_share_power_sharpens_toward_the_most_productive_arm():
    rates = {"a": 0.03, "b": 0.01}
    assert round_shares(rates, power=1.0) == round_shares(rates)
    sharp = round_shares(rates, 0.1, 3.0)
    assert sharp == pytest.approx({"a": 0.1 + 0.8 * 27 / 28, "b": 0.1 + 0.8 / 28})
    assert round_shares({"a": 0, "b": 0}, 0.1, 3.0) == pytest.approx({"a": 0.5, "b": 0.5})
    with pytest.raises(ValueError):
        round_shares(rates, 0.1, 0.0)


def test_exclusive_phase_gives_later_rounds_to_one_arm():
    instance = load_dzn(Path(__file__).resolve().parents[1] / "data/validation/small_3x3.dzn")
    result, history = run_phase2_portfolio_experiment(
        instance,
        seed=42,
        total_budget=600,
        block_size=20,
        population_size=10,
        policy="dynamic",
        round_size=120,
        minimum_share=0.1,
        exclusive_arm="SPEA2",
        exclusive_after=240,
    )
    assert result.evaluations_used == 600
    late = [b for b in history if b.round_index >= 2]
    assert late and all(b.arm_name == "SPEA2" for b in late)
    assert sum(b.evaluations_used for b in late) == 360
