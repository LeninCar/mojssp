import random
from pathlib import Path

import pytest

from mojssp.portfolio.curve_prediction import line_predictions, sampled_prediction
from mojssp.model.io import load_dzn
from mojssp.portfolio.regional_portfolio import run_regional_policy_experiment


def test_line_predictions_cover_every_recent_subcurve():
    points = [(50, 0.5), (100, 0.6), (150, 0.65), (200, 0.7)]
    predictions = line_predictions(points, 250)
    assert len(predictions) == 3
    assert predictions[0] == pytest.approx(0.75)
    assert all(value >= 0.7 for value in predictions)
    assert line_predictions([(50, 0.5), (100, 0.5)], 500) == [0.5]
    with pytest.raises(ValueError):
        line_predictions([(50, 0.5)], 100)


def test_sampled_prediction_is_one_of_the_line_predictions():
    points = [(50, 0.5), (100, 0.6), (150, 0.62)]
    value, predictions = sampled_prediction(points, 200, random.Random(3))
    assert value in predictions


def test_predicted_winner_spends_exact_budget_and_traces_every_choice():
    instance = load_dzn(Path(__file__).resolve().parents[1] / "data/validation/small_3x3.dzn")
    first = run_regional_policy_experiment(
        instance,
        7,
        ["MOEA/D", "RegionExplorer"],
        "multiea",
        False,
        budget=1200,
        block_size=50,
        population_size=30,
    )
    second = run_regional_policy_experiment(
        instance,
        7,
        ["MOEA/D", "RegionExplorer"],
        "multiea",
        False,
        budget=1200,
        block_size=50,
        population_size=30,
    )
    assert first["evaluations_used"] == 1200 and sum(first["allocations"].values()) == 1200
    assert first["pareto_front"] == second["pareto_front"] and first["blocks"] == second["blocks"]
    trace = first["prediction_trace"]
    predicted = [b for b in first["blocks"] if b["phase"] == "predicted"]
    assert len(trace) == len(predicted) == sum(b["phase"] == "predicted" for b in first["blocks"]) > 0
    for row, block in zip(trace, predicted):
        assert block["arm_name"] == row["chosen"] == max(row["predictions"], key=row["predictions"].get)


def test_credit_curve_variant_runs_and_differs_only_in_selection_signal():
    instance = load_dzn(Path(__file__).resolve().parents[1] / "data/validation/small_3x3.dzn")
    result = run_regional_policy_experiment(
        instance,
        7,
        ["MOEA/D", "RegionExplorer"],
        "multiea_credit",
        False,
        budget=1200,
        block_size=50,
        population_size=30,
    )
    assert result["evaluations_used"] == 1200 and result["policy_profile"]["curve"] == "credit"
    assert result["prediction_trace"]
