"""Real-data feature layer for the separate simulated shipment risk model."""

from datetime import datetime

from baselhack.features.rhine import build_rhine_features
from baselhack.features.traffic import anomalies
from baselhack.features.weather import build_weather_features
from baselhack.interfaces import (
    LogisticsAssumptions,
    LogisticsFeatures,
    RealObservations,
    offset_required,
)


def build_features(
    observations: RealObservations,
    as_of: datetime,
    assumptions: LogisticsAssumptions,
    station_ids: list[str],
) -> LogisticsFeatures:
    """Extract observed features without future evidence, fallback values or factory data."""
    as_of = offset_required(as_of)
    traffic, traffic_warnings = anomalies(
        observations.traffic, as_of, station_ids, assumptions
    )
    rhine, rhine_warnings = build_rhine_features(observations.rhine, as_of, assumptions)
    weather, weather_warnings = build_weather_features(
        observations.weather, as_of, assumptions
    )
    return LogisticsFeatures(
        as_of=as_of,
        traffic=traffic,
        rhine=rhine,
        weather=weather,
        warnings=traffic_warnings + rhine_warnings + weather_warnings,
    )


__all__ = ["build_features"]
