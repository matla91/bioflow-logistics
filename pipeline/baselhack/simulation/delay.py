"""Explainable transport penalties and paired Monte Carlo journey durations."""

import numpy as np
from numpy.typing import NDArray

from baselhack.interfaces import (
    LogisticsAssumptions,
    LogisticsFeatures,
    RiskDriver,
    ShipmentState,
)

from .navigation import assess_navigation


def delay_penalties(
    shipment: ShipmentState,
    features: LogisticsFeatures,
    assumptions: LogisticsAssumptions,
) -> tuple[float, float, float, list[RiskDriver]]:
    """Return traffic, river and weather mean-minute additions plus evidence."""
    traffic, traffic_drivers = _traffic_penalty(shipment, features, assumptions)
    river, river_drivers = _river_penalty(shipment, features, assumptions)
    weather, weather_drivers = _weather_penalty(features, assumptions)
    return traffic, river, weather, traffic_drivers + river_drivers + weather_drivers


def _traffic_penalty(shipment, features, assumptions):
    available = [
        item
        for item in features.traffic
        if item.status == "ok"
        and item.z_score is not None
        and 0
        <= (shipment.as_of - item.interval_end).total_seconds() / 60
        <= assumptions.max_traffic_age_min
    ]
    if not available:
        return 0.0, []
    largest = max(available, key=lambda item: item.z_score)
    positive_z = min(max(largest.z_score, 0.0), assumptions.traffic_z_cap)
    penalty = positive_z * assumptions.traffic_min_per_positive_z
    return penalty, [
        RiskDriver(
            name="Traffic anomaly",
            value=largest.z_score,
            unit="z-score",
            estimated_delay_contribution_min=penalty,
            explanation=(
                f"Station {largest.station_id} observed {largest.observed_count:g} vehicles "
                f"against baseline mean {largest.baseline_mean}; largest available z-score "
                f"is capped at ASSUMED {assumptions.traffic_z_cap:g} and multiplied by "
                f"ASSUMED {assumptions.traffic_min_per_positive_z:g} min/z. "
                "This adds mean transport time before random draws."
            ),
            evidence_kind="observed",
        )
    ]


def _river_penalty(shipment, features, assumptions):
    if shipment.route_mode != "river":
        return 0.0, []
    navigation, drivers = assess_navigation(shipment, features, assumptions)
    # Navigation owns the effective addition and its provenance, including any
    # finite ASSUMED blockage horizon; simulation separately forces arrival zero.
    return navigation.delay_penalty_min, drivers


def _weather_penalty(features, assumptions):
    weather = features.weather
    if weather is None:
        raise ValueError("Weather is required before computing delay penalties")
    rain = weather.precipitation_mm
    wind = weather.wind_speed_m_s
    rain_penalty = (rain or 0.0) * assumptions.rain_min_per_mm
    wind_penalty = (
        max((wind or 0.0) - assumptions.wind_threshold_m_s, 0.0)
        * assumptions.wind_min_per_m_s
    )
    drivers = []
    if rain is not None:
        drivers.append(
            RiskDriver(
                name="Observed rain",
                value=rain,
                unit="mm/hour",
                estimated_delay_contribution_min=rain_penalty,
                explanation=(
                    "Latest hourly precipitation multiplied by "
                    f"ASSUMED {assumptions.rain_min_per_mm:g} min/mm for every route. "
                    "This is an assumed mean transport addition, not a precipitation forecast."
                ),
                evidence_kind="observed",
            )
        )
    if wind is not None:
        drivers.append(
            RiskDriver(
                name="Observed wind",
                value=wind,
                unit="m/s",
                estimated_delay_contribution_min=wind_penalty,
                explanation=(
                    f"Observed wind above ASSUMED {assumptions.wind_threshold_m_s:g} m/s "
                    f"multiplied by ASSUMED {assumptions.wind_min_per_m_s:g} min per m/s "
                    "for every route; an assumed mean transport addition."
                ),
                evidence_kind="observed",
            )
        )
    return rain_penalty + wind_penalty, drivers


def journey_durations(
    shipment: ShipmentState,
    assumptions: LogisticsAssumptions,
    traffic_min: float,
    river_min: float,
    weather_min: float,
) -> dict[str, NDArray[np.float64]]:
    """Use the same independent transport/handling standard draws for each action."""
    random = np.random.default_rng(assumptions.seed)
    transport_draws = random.standard_normal(assumptions.n_runs)
    handling_draws = random.standard_normal(assumptions.n_runs)
    transport = np.maximum(
        shipment.planned_remaining_min
        + traffic_min
        + river_min
        + weather_min
        + assumptions.transport_sd_min * transport_draws,
        0.0,
    )
    handling = np.maximum(
        shipment.handling_min + assumptions.handling_sd_min * handling_draws, 0.0
    )
    reroute_transport = np.maximum(
        assumptions.reroute_transport_min
        + assumptions.reroute_traffic_factor * traffic_min
        + weather_min
        + assumptions.reroute_transport_sd_min * transport_draws,
        0.0,
    )
    baseline = transport + handling
    return {
        "BASELINE": baseline,
        "BUFFER": baseline,
        "EXPEDITE": transport * assumptions.expedite_transport_factor
        + handling * assumptions.expedite_handling_factor,
        "REROUTE": reroute_transport
        + handling
        + assumptions.reroute_extra_handling_min,
    }
