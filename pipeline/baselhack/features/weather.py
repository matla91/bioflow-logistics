"""Fresh MeteoSwiss Basel/Binningen observations, never product temperatures."""

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from baselhack.features.rhine import linear_trend_per_hour
from baselhack.interfaces import (
    LogisticsAssumptions,
    WeatherFeatures,
    WeatherObservation,
    offset_required,
)


def _deduplicate(
    observations: list[WeatherObservation], as_of: datetime
) -> tuple[list[WeatherObservation], list[str]]:
    grouped = defaultdict(list)
    for record in observations:
        if record.station_id == "BAS" and record.t.astimezone(timezone.utc) <= as_of:
            grouped[record.t.astimezone(timezone.utc)].append(record)
    clean, warnings = [], []
    metrics = (
        "air_temperature_c",
        "precipitation_mm",
        "wind_speed_m_s",
        "relative_humidity_pct",
    )
    for at, records in sorted(grouped.items()):
        values = {
            metric: {
                getattr(record, metric)
                for record in records
                if getattr(record, metric) is not None
            }
            for metric in metrics
        }
        if any(len(readings) > 1 for readings in values.values()):
            warnings.append(
                f"Weather: conflicting BAS readings at {at.isoformat()} were excluded."
            )
        else:
            clean.append(
                WeatherObservation(
                    t=at,
                    **{
                        metric: next(iter(readings), None)
                        for metric, readings in values.items()
                    },
                )
            )
    return clean, warnings


def build_weather_features(
    observations: list[WeatherObservation],
    as_of: datetime,
    assumptions: LogisticsAssumptions,
) -> tuple[WeatherFeatures | None, list[str]]:
    """Return current ambient weather plus an earlier bounded temperature trend."""
    as_of = offset_required(as_of).astimezone(timezone.utc)
    clean, warnings = _deduplicate(observations, as_of)
    if not clean:
        return None, warnings + ["Weather: no BAS observation at or before as_of."]
    latest = clean[-1]
    age_min = (as_of - latest.t).total_seconds() / 60
    if age_min > assumptions.max_weather_age_min:
        return None, warnings + [
            f"Weather: latest BAS observation is stale ({age_min:g} min)."
        ]
    cutoff = as_of - timedelta(minutes=assumptions.trend_window_min)
    points = [
        (record.t, record.air_temperature_c) for record in clean if record.t >= cutoff
    ]
    slope = linear_trend_per_hour(points, assumptions.trend_min_span_min)
    if slope is None:
        warnings.append(
            "Weather: temperature trend requires two timestamps spanning at least "
            f"{assumptions.trend_min_span_min:g} min within the trend window."
        )
    for metric in ("precipitation_mm", "wind_speed_m_s", "relative_humidity_pct"):
        if getattr(latest, metric) is None:
            warnings.append(f"Weather: latest {metric} is missing.")
    return WeatherFeatures(
        observed_at=latest.t,
        air_temperature_c=latest.air_temperature_c,
        precipitation_mm=latest.precipitation_mm,
        wind_speed_m_s=latest.wind_speed_m_s,
        relative_humidity_pct=latest.relative_humidity_pct,
        temperature_trend_c_per_hour=slope,
    ), warnings
