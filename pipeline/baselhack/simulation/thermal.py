"""Ambient exposure proxy, deliberately without a product temperature model."""

import numpy as np
from numpy.typing import NDArray

from baselhack.interfaces import LogisticsAssumptions, ShipmentState, WeatherFeatures


def ambient_distance_c(
    ambient_c: float, reference_band_c: tuple[float, float]
) -> float:
    """Return ambient degrees outside the assumed reference band, hot or cold."""
    lower, upper = reference_band_c
    return max(lower - ambient_c, ambient_c - upper, 0.0)


def exposure_proxy(
    elapsed_min: NDArray[np.float64],
    shipment: ShipmentState,
    weather: WeatherFeatures,
    assumptions: LogisticsAssumptions,
) -> NDArray[np.float64]:
    """Hold snapshot ambient constant after assumed packaging autonomy expires.

    Degree-minutes measure a scenario proxy only. Ambient observations alone
    cannot establish actual product temperature or product-temperature excursions.
    """
    degrees = ambient_distance_c(
        weather.air_temperature_c, assumptions.ambient_reference_band_c
    )
    unprotected_min = np.maximum(elapsed_min - shipment.protection_remaining_min, 0.0)
    return shipment.prior_exposure_degree_min + degrees * unprotected_min
