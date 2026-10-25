"""Round-wise budget shares from recent global hypervolume gain per evaluation."""
import math


def round_shares(gain_rates, minimum_share=.1):
    count = len(gain_rates)
    if not count or not math.isfinite(minimum_share) or not 0 <= minimum_share <= 1 / count:
        raise ValueError('Invalid minimum share')
    if any(not math.isfinite(value) or value < 0 for value in gain_rates.values()):
        raise ValueError('Gain rates must be finite and nonnegative')
    total = sum(gain_rates.values())
    if total == 0:
        return dict.fromkeys(gain_rates, 1 / count)
    return {name: minimum_share + (1-count*minimum_share)*rate/total
            for name,rate in gain_rates.items()}
