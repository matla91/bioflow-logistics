"""First-order thermal response; integrate exact threshold-crossing time."""

import math
from itertools import pairwise


def advance(temperature, target, duration_min, tau_min, limits):
    if duration_min < 0 or tau_min <= 0:
        raise ValueError("Duration must be nonnegative and tau positive")
    finish = target + (temperature - target) * math.exp(-duration_min / tau_min)
    cuts = [0.0, duration_min]
    for boundary in limits:
        if min(temperature, finish) < boundary < max(temperature, finish):
            ratio = (boundary - target) / (temperature - target)
            cuts.append(-tau_min * math.log(ratio))
    cuts.sort()
    outside = 0.0
    for start, end in pairwise(cuts):
        middle = target + (temperature - target) * math.exp(
            -(start + end) / (2 * tau_min)
        )
        if middle < limits[0] or middle > limits[1]:
            outside += end - start
    return finish, outside
