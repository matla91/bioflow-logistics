"""Basel traffic anomalies relative to earlier comparable station-hours."""

from collections import defaultdict
from datetime import datetime, timezone
from statistics import mean, stdev
from zoneinfo import ZoneInfo

from baselhack.interfaces import (
    LogisticsAssumptions,
    TrafficBaseline,
    TrafficFeature,
    TrafficObservation,
    offset_required,
)

BASEL_TIMEZONE = ZoneInfo("Europe/Zurich")


def _deduplicate(
    observations: list[TrafficObservation],
) -> tuple[list[TrafficObservation], list[str]]:
    grouped = defaultdict(list)
    for observation in observations:
        key = (
            observation.station_id,
            observation.interval_start.astimezone(timezone.utc),
        )
        grouped[key].append(observation)
    clean, warnings = [], []
    for (station, start), records in sorted(grouped.items()):
        if len({record.vehicle_count for record in records}) > 1:
            warnings.append(
                f"Traffic station {station}: conflicting counts at {start.isoformat()} "
                "were excluded."
            )
        else:
            clean.append(
                TrafficObservation(
                    station_id=station,
                    interval_start=start,
                    interval_end=records[0].interval_end.astimezone(timezone.utc),
                    vehicle_count=records[0].vehicle_count,
                )
            )
    return clean, warnings


def _daily_samples(
    history: list[TrafficObservation], before: datetime
) -> dict[tuple[str, int, int], list[float]]:
    """Repeated DST hours count once per local day; earlier dates only train."""
    before = offset_required(before).astimezone(timezone.utc)
    before_date = before.astimezone(BASEL_TIMEZONE).date()
    days = defaultdict(list)
    for observation in history:
        local = observation.interval_start.astimezone(BASEL_TIMEZONE)
        if (
            observation.interval_end.astimezone(timezone.utc) <= before
            and local.date() < before_date
        ):
            days[
                (observation.station_id, local.weekday(), local.hour, local.date())
            ].append(observation.vehicle_count)
    samples = defaultdict(list)
    for (station, weekday, hour, _), counts in sorted(days.items()):
        samples[(station, weekday, hour)].append(mean(counts))
    return samples


def build_baseline(
    history: list[TrafficObservation], before: datetime, min_samples: int = 3
) -> list[TrafficBaseline]:
    """Return station/weekday/local-hour sample means and sample deviations.

    Only complete observations strictly before the target's entire Basel-local
    date are eligible. Counts must already be station totals, not lane records.
    Contradictory duplicate totals fail closed rather than biasing training.
    """
    if min_samples < 2:
        raise ValueError("Traffic baselines require at least two daily samples")
    before = offset_required(before).astimezone(timezone.utc)
    before_date = before.astimezone(BASEL_TIMEZONE).date()
    history = [
        record
        for record in history
        if record.interval_end.astimezone(timezone.utc) <= before
        and record.interval_start.astimezone(BASEL_TIMEZONE).date() < before_date
    ]
    history, warnings = _deduplicate(history)
    if warnings:
        raise ValueError(" ".join(warnings))
    return [
        TrafficBaseline(
            station_id=station,
            weekday=weekday,
            hour=hour,
            sample_count=len(counts),
            mean_count=mean(counts),
            sd_count=stdev(counts),
        )
        for (station, weekday, hour), counts in sorted(
            _daily_samples(history, before).items()
        )
        if len(counts) >= min_samples
    ]


def anomalies(
    observations: list[TrafficObservation],
    as_of: datetime,
    station_ids: list[str],
    assumptions: LogisticsAssumptions,
) -> tuple[list[TrafficFeature], list[str]]:
    """Compare each selected station's latest fresh complete hour to prior days."""
    as_of = offset_required(as_of).astimezone(timezone.utc)
    stations = sorted(set(station_ids))
    selected = [
        record
        for record in observations
        if record.station_id in stations
        and record.interval_end.astimezone(timezone.utc) <= as_of
    ]
    selected, warnings = _deduplicate(selected)
    features = []
    if not stations:
        return [], ["Traffic: no station IDs were selected."]
    for station in stations:
        complete = [
            record
            for record in selected
            if record.station_id == station
            and record.interval_end.astimezone(timezone.utc) <= as_of
        ]
        if not complete:
            warnings.append(
                f"Traffic station {station}: no complete observation at or before as_of."
            )
            continue
        latest = max(
            complete, key=lambda record: record.interval_end.astimezone(timezone.utc)
        )
        age_min = (
            as_of - latest.interval_end.astimezone(timezone.utc)
        ).total_seconds() / 60
        if age_min > assumptions.max_traffic_age_min:
            warnings.append(
                f"Traffic station {station}: latest observation is stale ({age_min:g} min)."
            )
            continue
        features.append(_station_anomaly(latest, complete, assumptions, warnings))
    return features, warnings


def _station_anomaly(
    latest: TrafficObservation,
    complete: list[TrafficObservation],
    assumptions: LogisticsAssumptions,
    warnings: list[str],
) -> TrafficFeature:
    local = latest.interval_start.astimezone(BASEL_TIMEZONE)
    key = (latest.station_id, local.weekday(), local.hour)
    counts = _daily_samples(complete, latest.interval_start).get(key, [])
    baseline_mean = mean(counts) if counts else None
    baseline_sd = stdev(counts) if len(counts) >= 2 else None
    z_score, status = None, "missing_baseline"
    if len(counts) < assumptions.baseline_min_samples:
        warnings.append(
            f"Traffic station {latest.station_id}: insufficient earlier weekday/hour "
            f"baseline ({len(counts)} daily samples; {assumptions.baseline_min_samples} required)."
        )
    elif baseline_sd == 0:
        status = "zero_variance"
        warnings.append(
            f"Traffic station {latest.station_id}: baseline has zero variance; z-score unavailable."
        )
    else:
        status = "ok"
        z_score = (latest.vehicle_count - baseline_mean) / baseline_sd
    return TrafficFeature(
        station_id=latest.station_id,
        interval_end=latest.interval_end,
        observed_count=latest.vehicle_count,
        baseline_mean=baseline_mean,
        baseline_sd=baseline_sd,
        baseline_sample_count=len(counts),
        z_score=z_score,
        status=status,
    )
