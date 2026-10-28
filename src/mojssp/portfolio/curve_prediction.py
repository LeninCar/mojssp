"""Convergence-curve prediction at a common future point, after MultiEA (Yuen et al., GECCO 2013)."""
import math


def line_predictions(points, target):
    """Predict the curve value at target from every recent sub-curve of two or more points.

    Each sub-curve holds the last l points (l = 2..len(points)) and is fitted by least
    squares. HV curves never decrease, so predictions are floored at the latest value.
    """
    if len(points) < 2:
        raise ValueError('At least two curve points are required')
    if any(not math.isfinite(x) or not math.isfinite(y) for x, y in points):
        raise ValueError('Curve points must be finite')
    latest = points[-1][1]
    predictions = []
    for length in range(2, len(points) + 1):
        tail = points[-length:]
        mean_x = sum(x for x, _ in tail) / length
        mean_y = sum(y for _, y in tail) / length
        sxx = sum((x - mean_x) ** 2 for x, _ in tail)
        slope = sum((x - mean_x) * (y - mean_y) for x, y in tail) / sxx if sxx else 0.
        predictions.append(max(latest, mean_y + slope * (target - mean_x)))
    return predictions


def sampled_prediction(points, target, rng):
    """Draw one prediction with equal weight per sub-curve, as MultiEA's bootstrap does."""
    predictions = line_predictions(points, target)
    return rng.choice(predictions), predictions
