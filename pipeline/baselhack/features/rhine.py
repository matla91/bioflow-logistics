"""Current Basel Rhine evidence and bounded, explainable linear trends."""

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from statistics import mean

from baselhack.interfaces import (
    LogisticsAssumptions,
    RhineFeatures,
    RhineObservation,
    offset_required,
)

BASEL_RHINE_STATION = "2289"


def linear_trend_per_hour(
    points: list[tuple[datetime, float]], min_span_min: float
) -> float | None:
    """OLS slope with actual elapsed hours, requiring enough temporal coverage."""
    if len(points) < 2:
        return None
    points = sorted(points, key=lambda point: point[0].astimezone(timezone.utc))
    origin = points[0][0].astimezone(timezone.utc)
    hours = [
        (at.astimezone(timezone.utc) - origin).total_seconds() / 3600
        for at, _ in points
    ]
    if hours[-1] * 60 < min_span_min or hours[-1] == 0:
        return None
    values = [value for _, value in points]
    hour_mean, value_mean = mean(hours), mean(values)
    return sum(
        (hour - hour_mean) * (value - value_mean) for hour, value in zip(hours, values)
    ) / sum((hour - hour_mean) ** 2 for hour in hours)


def _deduplicate(
    observations: list[RhineObservation], as_of: datetime
) -> tuple[list[RhineObservation], list[str]]:
    grouped = defaultdict(list)
    warnings = []
    wrong_station_count = 0
    for record in observations:
        if record.t.astimezone(timezone.utc) > as_of:
            continue
        if record.station_id != BASEL_RHINE_STATION:
            wrong_station_count += 1
            continue
        grouped[record.t.astimezone(timezone.utc)].append(record)
    if wrong_station_count:
        warnings.append(
            f"Rhine: excluded {wrong_station_count} observations from other stations."
        )
    clean = []
    for at, records in sorted(grouped.items()):
        levels = {
            record.level_masl for record in records if record.level_masl is not None
        }
        discharges = {
            record.discharge_m3_s
            for record in records
            if record.discharge_m3_s is not None
        }
        if len(levels) > 1 or len(discharges) > 1:
            warnings.append(
                f"Rhine: conflicting readings at {at.isoformat()} were excluded."
            )
        elif levels or discharges:
            clean.append(
                RhineObservation(
                    t=at,
                    level_masl=next(iter(levels), None),
                    discharge_m3_s=next(iter(discharges), None),
                )
            )
    return clean, warnings


def build_rhine_features(
    observations: list[RhineObservation],
    as_of: datetime,
    assumptions: LogisticsAssumptions,
) -> tuple[RhineFeatures | None, list[str]]:
    """Use only fresh station 2289 evidence preceding the simulation instant."""
    as_of = offset_required(as_of).astimezone(timezone.utc)
    clean, warnings = _deduplicate(observations, as_of)
    if not clean:
        return None, warnings + [
            "Rhine: no usable Basel observation at or before as_of."
        ]
    latest = clean[-1]
    age_min = (as_of - latest.t.astimezone(timezone.utc)).total_seconds() / 60
    if age_min > assumptions.max_rhine_age_min:
        return None, warnings + [
            f"Rhine: latest Basel observation is stale ({age_min:g} min)."
        ]
    cutoff = as_of - timedelta(minutes=assumptions.trend_window_min)
    window = [record for record in clean if record.t >= cutoff]
    level_trend = _metric_trend(
        window, latest, "level_masl", 100, assumptions, warnings
    )
    discharge_trend = _metric_trend(
        window, latest, "discharge_m3_s", 1, assumptions, warnings
    )
    return RhineFeatures(
        observed_at=latest.t,
        level_masl=latest.level_masl,
        discharge_m3_s=latest.discharge_m3_s,
        level_trend_cm_per_hour=level_trend,
        discharge_trend_m3_s_per_hour=discharge_trend,
        sample_count=max(1, len(window)),
    ), warnings


def _metric_trend(window, latest, metric, scale, assumptions, warnings):
    if getattr(latest, metric) is None:
        warnings.append(f"Rhine: latest {metric} is missing; its trend is unavailable.")
        return None
    points = [
        (record.t, getattr(record, metric) * scale)
        for record in window
        if getattr(record, metric) is not None
    ]
    slope = linear_trend_per_hour(points, assumptions.trend_min_span_min)
    if slope is None:
        warnings.append(
            f"Rhine: {metric} trend requires two timestamps spanning at least "
            f"{assumptions.trend_min_span_min:g} min within the trend window."
        )
    return slope
