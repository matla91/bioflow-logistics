"""Validate the simulated shipment against the external snapshot it uses."""

from baselhack.interfaces import (
    LogisticsAssumptions,
    LogisticsFeatures,
    ShipmentState,
)


def validate_snapshot(
    shipment: ShipmentState,
    features: LogisticsFeatures,
    assumptions: LogisticsAssumptions,
) -> list[str]:
    """Reject unusable weather and surface gaps that can understate delay risk."""
    if shipment.as_of != features.as_of:
        raise ValueError(
            "Shipment as_of and feature as_of must describe the same instant"
        )
    weather = features.weather
    if weather is None:
        raise ValueError(
            "Weather is missing; thermal exposure risk cannot be estimated"
        )
    weather_age = (shipment.as_of - weather.observed_at).total_seconds() / 60
    if weather_age < 0:
        raise ValueError("Weather observation must not be later than as_of")
    if weather_age > assumptions.max_weather_age_min:
        raise ValueError("Weather is stale; thermal exposure risk cannot be estimated")

    warnings = list(features.warnings)
    usable_traffic = [
        item
        for item in features.traffic
        if item.status == "ok"
        and item.z_score is not None
        and 0
        <= (shipment.as_of - item.interval_end).total_seconds() / 60
        <= assumptions.max_traffic_age_min
    ]
    if not usable_traffic:
        warnings.append(
            "No recent traffic anomaly is available; traffic delay risk may be underestimated."
        )
    elif len(usable_traffic) < len(features.traffic) or any(
        warning.lower().startswith("traffic") for warning in features.warnings
    ):
        # Feature extraction omits unavailable stations, so present usable features
        # alone cannot establish that every selected station was observed.
        warnings.append(
            "Some selected traffic observations or anomalies are missing, stale, "
            "conflicting or lack a usable baseline; "
            "traffic delay risk may be underestimated."
        )
    if shipment.route_mode == "river":
        rhine = features.rhine
        recent = rhine is not None and (
            0
            <= (shipment.as_of - rhine.observed_at).total_seconds() / 60
            <= assumptions.max_rhine_age_min
        )
        if not recent:
            warnings.append(
                "No recent Rhine trends are available; river delay risk may be underestimated."
            )
        elif rhine is not None and (
            rhine.level_trend_cm_per_hour is None
            or rhine.discharge_trend_m3_s_per_hour is None
        ):
            warnings.append(
                "A Rhine level or discharge trend is missing; river delay risk may be underestimated."
            )
    if weather.precipitation_mm is None or weather.wind_speed_m_s is None:
        warnings.append(
            "Rain or wind observations are missing; weather delay risk may be underestimated."
        )
    return list(dict.fromkeys(warnings))
