import math

import pytest
from baselhack.simulator.thermal import advance


def test_exposed_drift_and_exact_crossing():
    temperature, excursion = advance(5, 25, 90, 90, [2, 8])
    assert temperature == pytest.approx(25 - 20 / math.e)
    crossing = -90 * math.log((8 - 25) / (5 - 25))
    assert excursion == pytest.approx(90 - crossing)


def test_refrigerated_recovery_still_counts():
    temperature, excursion = advance(17, 5, 120, 60, [2, 8])
    assert temperature < 8
    assert excursion == pytest.approx(60 * math.log(4))


def test_boundaries_and_cold_excursion():
    assert advance(8, 8, 30, 60, [2, 8])[1] == 0
    assert advance(2, 2, 30, 60, [2, 8])[1] == 0
    assert advance(5, -10, 90, 90, [2, 8])[1] > 0
