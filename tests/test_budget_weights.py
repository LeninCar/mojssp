import math

import pytest

from scripts.derive_budget_weights import budget_shares


def test_minimum_is_reserved_before_distributing_remaining_budget():
    shares = budget_shares({'moead': 7, 'nsga2': 2, 'spea2': 1}, minimum=.1)
    assert shares == pytest.approx({'moead': .59, 'nsga2': .24, 'spea2': .17})
    assert sum(shares.values()) == pytest.approx(1)


def test_no_gain_falls_back_to_uniform():
    assert list(budget_shares({'moead': 0, 'nsga2': 0, 'spea2': 0}).values()) == pytest.approx([1/3]*3)


@pytest.mark.parametrize('value', [-1, math.nan, math.inf])
def test_invalid_gain_is_rejected(value):
    with pytest.raises(ValueError):
        budget_shares({'moead': value, 'nsga2': 1, 'spea2': 1})
