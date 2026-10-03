"""Feature arithmetic, temporal boundaries and honest missing-data behavior."""

from datetime import datetime, timedelta, timezone

import pytest
import yaml

from baselhack.features import build_features
from baselhack.features.rhine import build_rhine_features
from baselhack.features.traffic import anomalies, build_baseline
from baselhack.features.weather import build_weather_features
from baselhack.interfaces import (
    LogisticsAssumptions,
    ObservationSource,
    RealObservations,
    RhineObservation,
    TrafficObservation,
    WeatherObservation,
)
from baselhack.storage import ROOT


def at(value):
    return datetime.fromisoformat(value)


@pytest.fixture
def assumptions():
    config = yaml.safe_load((ROOT / "config" / "logistics.yaml").read_text())
    return LogisticsAssumptions.model_validate(config)


def empty_observations():
    return RealObservations(
        traffic=[],
        rhine=[],
        weather=[],
        sources=[
            ObservationSource(
                provider="Synthetic unit-test fixture",
                dataset="Empty observation fixture",
                url="https://example.test/empty-fixture",
                retrieved_at=at("2026-09-30T11:00:00+00:00"),
                licence="Synthetic fixture; no external observations",
            )
        ],
    )


def traffic(start, count, station="A"):
    start = at(start).astimezone(timezone.utc)
    return TrafficObservation(
        station_id=station,
        interval_start=start,
        interval_end=start + timedelta(hours=1),
        vehicle_count=count,
    )


def wednesday_history(counts=(90, 100, 110), station="A"):
    return [
        traffic(f"2026-09-{day}T13:00:00+02:00", count, station)
        for day, count in zip(("09", "16", "23"), counts)
    ]


def test_baseline_excludes_entire_current_local_date_and_future():
    before = at("2026-09-30T13:00:00+02:00")
    history = wednesday_history() + [
        traffic("2026-09-30T13:00:00+02:00", 900),
        traffic("2026-09-30T00:00:00+02:00", 500),
        traffic("2026-10-07T13:00:00+02:00", 1000),
        traffic("2026-10-07T13:00:00+02:00", 2000),
    ]
    [baseline] = build_baseline(history, before)
    assert (baseline.weekday, baseline.hour, baseline.sample_count) == (2, 13, 3)
    assert baseline.mean_count == 100
    assert baseline.sd_count == 10  # Sample SD, not population SD.


def test_baseline_weekday_and_hour_use_basel_timezone():
    records = [
        traffic(f"2026-09-{day}T22:00:00+00:00", count)
        for day, count in (("06", 10), ("13", 20), ("20", 30))
    ]
    [baseline] = build_baseline(records, at("2026-09-28T00:00:00+02:00"))
    assert (baseline.weekday, baseline.hour) == (0, 0)
    assert baseline.mean_count == 20


def test_repeated_dst_hour_counts_as_one_daily_sample():
    records = [
        traffic("2026-10-11T00:00:00+00:00", 300),
        traffic("2026-10-18T00:00:00+00:00", 100),
        traffic("2026-10-25T00:00:00+00:00", 100),
        traffic("2026-10-25T01:00:00+00:00", 300),
    ]
    [baseline] = build_baseline(records, at("2026-11-01T03:00:00+01:00"))
    assert (baseline.weekday, baseline.hour, baseline.sample_count) == (6, 2, 3)
    assert baseline.mean_count == 200
    assert baseline.sd_count == 100


def test_anomaly_uses_latest_complete_hour_and_existing_station_total(assumptions):
    current = traffic("2026-09-30T13:00:00+02:00", 130)
    records = (
        wednesday_history()
        + [current, current]
        + [
            traffic("2026-09-30T14:00:00+02:00", 999),
        ]
    )
    features, warnings = anomalies(records, current.interval_end, ["A"], assumptions)
    [feature] = features
    assert feature.interval_end == current.interval_end
    assert feature.observed_count == 130
    assert feature.baseline_sample_count == 3
    assert feature.z_score == 3
    assert feature.status == "ok"
    assert not warnings


def test_same_local_day_does_not_train_dst_current_hour(assumptions):
    records = [
        traffic("2026-10-11T00:00:00+00:00", 90),
        traffic("2026-10-18T00:00:00+00:00", 110),
        traffic("2026-10-25T00:00:00+00:00", 999),
        traffic("2026-10-25T01:00:00+00:00", 200),
    ]
    [feature], warnings = anomalies(
        records, at("2026-10-25T02:00:00+00:00"), ["A"], assumptions
    )
    assert feature.observed_count == 200
    assert feature.baseline_sample_count == 2
    assert feature.baseline_mean == 100
    assert feature.status == "missing_baseline"
    assert feature.z_score is None
    assert any("insufficient" in warning for warning in warnings)


@pytest.mark.parametrize(
    "counts,status,sample_count",
    [((100, 100, 100), "zero_variance", 3), ((90, 110), "missing_baseline", 2)],
)
def test_unestimable_z_score_is_not_zero(assumptions, counts, status, sample_count):
    records = wednesday_history(counts) + [traffic("2026-09-30T13:00:00+02:00", 150)]
    [feature], warnings = anomalies(
        records, at("2026-09-30T14:00:00+02:00"), ["A"], assumptions
    )
    assert feature.status == status
    assert feature.baseline_sample_count == sample_count
    assert feature.z_score is None
    assert warnings


def test_missing_baseline_never_fabricates_mean_or_sd(assumptions):
    current = traffic("2026-09-30T13:00:00+02:00", 0)
    [feature], warnings = anomalies([current], current.interval_end, ["A"], assumptions)
    assert feature.observed_count == 0
    assert feature.baseline_mean is None
    assert feature.baseline_sd is None
    assert feature.z_score is None
    assert feature.baseline_sample_count == 0
    assert warnings


def test_stale_and_missing_traffic_stations_are_explicit(assumptions):
    records = [traffic("2026-09-30T13:00:00+02:00", 150)]
    features, warnings = anomalies(
        records, at("2026-09-30T16:00:00+02:00"), ["B", "A"], assumptions
    )
    assert features == []
    assert "station A" in warnings[0] and "stale" in warnings[0]
    assert "station B" in warnings[1] and "no complete" in warnings[1]


def test_conflicting_traffic_totals_fail_closed(assumptions):
    records = wednesday_history() + [traffic("2026-09-23T13:00:00+02:00", 700)]
    with pytest.raises(ValueError, match="conflicting counts"):
        build_baseline(records, at("2026-09-30T13:00:00+02:00"))
    records += [traffic("2026-09-30T13:00:00+02:00", 130)]
    [feature], warnings = anomalies(
        records, at("2026-09-30T14:00:00+02:00"), ["A"], assumptions
    )
    assert feature.baseline_sample_count == 2
    assert feature.z_score is None
    assert any("conflicting counts" in warning for warning in warnings)


def test_rhine_trend_units_window_and_fixed_station(assumptions):
    assumptions = assumptions.model_copy(update={"trend_window_min": 120})
    records = [
        RhineObservation(
            t=at("2026-09-30T08:00:00+00:00"), level_masl=900, discharge_m3_s=9999
        ),
        RhineObservation(
            t=at("2026-09-30T09:00:00+00:00"), level_masl=250.80, discharge_m3_s=1000
        ),
        RhineObservation(
            t=at("2026-09-30T10:00:00+00:00"), level_masl=250.79, discharge_m3_s=990
        ),
        RhineObservation(
            t=at("2026-09-30T11:00:00+00:00"), level_masl=250.78, discharge_m3_s=980
        ),
        RhineObservation(
            t=at("2026-09-30T12:00:00+00:00"), level_masl=300, discharge_m3_s=5000
        ),
        RhineObservation(
            t=at("2026-09-30T11:00:00+00:00"), station_id="OTHER", level_masl=1000
        ),
    ]
    feature, warnings = build_rhine_features(
        records, at("2026-09-30T13:00:00+02:00"), assumptions
    )
    assert feature.observed_at == at("2026-09-30T11:00:00+00:00")
    assert feature.level_masl == 250.78
    assert feature.discharge_m3_s == 980
    assert feature.level_trend_cm_per_hour == pytest.approx(-1)
    assert feature.discharge_trend_m3_s_per_hour == -10
    assert feature.sample_count == 3
    assert any("other stations" in warning for warning in warnings)


def test_rhine_missing_latest_metric_cannot_reuse_older_value(assumptions):
    records = [
        RhineObservation(
            t=at("2026-09-30T09:00:00+00:00"), level_masl=250.80, discharge_m3_s=10
        ),
        RhineObservation(
            t=at("2026-09-30T10:00:00+00:00"), level_masl=250.79, discharge_m3_s=5
        ),
        RhineObservation(t=at("2026-09-30T11:00:00+00:00"), discharge_m3_s=0),
    ]
    feature, warnings = build_rhine_features(records, records[-1].t, assumptions)
    assert feature.level_masl is None
    assert feature.level_trend_cm_per_hour is None
    assert feature.discharge_m3_s == 0
    assert feature.discharge_trend_m3_s_per_hour == -5
    assert any("level_masl is missing" in warning for warning in warnings)


def test_short_trend_span_and_single_point_are_unavailable(assumptions):
    records = [
        RhineObservation(t=at("2026-09-30T10:50:00+00:00"), level_masl=250.80),
        RhineObservation(
            t=at("2026-09-30T11:00:00+00:00"), level_masl=250.70, discharge_m3_s=980
        ),
    ]
    feature, warnings = build_rhine_features(records, records[-1].t, assumptions)
    assert feature.level_trend_cm_per_hour is None
    assert feature.discharge_trend_m3_s_per_hour is None
    assert sum("trend requires" in warning for warning in warnings) == 2


def test_rhine_exact_duplicates_do_not_increase_sample_count(assumptions):
    records = [
        RhineObservation(t=at("2026-09-30T10:00:00+00:00"), level_masl=250.8),
        RhineObservation(t=at("2026-09-30T11:00:00+00:00"), level_masl=250.7),
    ]
    feature, _ = build_rhine_features(records * 3, records[-1].t, assumptions)
    assert feature.sample_count == 2
    assert feature.level_trend_cm_per_hour == pytest.approx(-10)


def test_conflicting_latest_rhine_does_not_become_observed_fact(assumptions):
    records = [
        RhineObservation(t=at("2026-09-30T10:00:00+00:00"), level_masl=250.8),
        RhineObservation(t=at("2026-09-30T11:00:00+00:00"), level_masl=250.7),
        RhineObservation(t=at("2026-09-30T11:00:00+00:00"), level_masl=251),
    ]
    feature, warnings = build_rhine_features(records, records[-1].t, assumptions)
    assert feature is None  # Earlier evidence has exceeded the freshness limit.
    assert any("conflicting" in warning for warning in warnings)
    assert any("stale" in warning for warning in warnings)


def test_weather_zero_precipitation_is_valid_and_future_is_excluded(assumptions):
    assumptions = assumptions.model_copy(update={"trend_window_min": 60})
    records = [
        WeatherObservation(t=at("2026-09-30T09:00:00+00:00"), air_temperature_c=100),
        WeatherObservation(t=at("2026-09-30T10:00:00+00:00"), air_temperature_c=18),
        WeatherObservation(
            t=at("2026-09-30T11:00:00+00:00"),
            air_temperature_c=20,
            precipitation_mm=0,
            wind_speed_m_s=0,
            relative_humidity_pct=0,
        ),
        WeatherObservation(t=at("2026-09-30T12:00:00+00:00"), air_temperature_c=100),
    ]
    feature, warnings = build_weather_features(
        records, at("2026-09-30T11:00:00+00:00"), assumptions
    )
    assert feature.air_temperature_c == 20
    assert feature.temperature_trend_c_per_hour == 2
    assert feature.precipitation_mm == 0
    assert feature.wind_speed_m_s == 0
    assert feature.relative_humidity_pct == 0
    assert not warnings


def test_weather_stale_and_missing_optional_metrics_are_explicit(assumptions):
    record = WeatherObservation(t=at("2026-09-30T11:00:00+00:00"), air_temperature_c=20)
    feature, warnings = build_weather_features([record], record.t, assumptions)
    assert feature.precipitation_mm is None
    assert feature.wind_speed_m_s is None
    assert any("precipitation_mm is missing" in warning for warning in warnings)
    feature, warnings = build_weather_features(
        [record], at("2026-09-30T13:00:00+00:00"), assumptions
    )
    assert feature is None
    assert any("stale" in warning for warning in warnings)


def test_weather_complementary_duplicates_merge_without_double_weight(assumptions):
    records = [
        WeatherObservation(t=at("2026-09-30T10:00:00+00:00"), air_temperature_c=18),
        WeatherObservation(
            t=at("2026-09-30T11:00:00+00:00"), air_temperature_c=20, precipitation_mm=0
        ),
        WeatherObservation(
            t=at("2026-09-30T13:00:00+02:00"), air_temperature_c=20, wind_speed_m_s=3
        ),
    ]
    feature, warnings = build_weather_features(records, records[-1].t, assumptions)
    assert feature.precipitation_mm == 0
    assert feature.wind_speed_m_s == 3
    assert feature.temperature_trend_c_per_hour == 2
    assert not any("conflicting" in warning for warning in warnings)


def test_conflicting_weather_current_timestamp_is_excluded(assumptions):
    records = [
        WeatherObservation(t=at("2026-09-30T11:00:00+00:00"), air_temperature_c=20),
        WeatherObservation(t=at("2026-09-30T11:00:00+00:00"), air_temperature_c=25),
    ]
    feature, warnings = build_weather_features(records, records[-1].t, assumptions)
    assert feature is None
    assert any("conflicting" in warning for warning in warnings)
    assert any("no BAS observation" in warning for warning in warnings)


def test_empty_sources_are_none_with_warnings(assumptions):
    observations = empty_observations()
    features = build_features(
        observations, at("2026-09-30T11:00:00+00:00"), assumptions, ["A"]
    )
    assert features.traffic == []
    assert features.rhine is None
    assert features.weather is None
    assert any("Traffic station A" in warning for warning in features.warnings)
    assert any("Rhine: no usable" in warning for warning in features.warnings)
    assert any("Weather: no BAS" in warning for warning in features.warnings)


def test_feature_order_and_offset_normalization_are_deterministic(assumptions):
    records = (
        wednesday_history(station="B")
        + wednesday_history(station="A")
        + [
            traffic("2026-09-30T13:00:00+02:00", 130, "A"),
            traffic("2026-09-30T13:00:00+02:00", 140, "B"),
            TrafficObservation(
                station_id="A",
                interval_start=at("2026-09-30T13:00:00+02:00"),
                interval_end=at("2026-09-30T14:00:00+02:00"),
                vehicle_count=130,
            ),
        ]
    )
    first = anomalies(
        records, at("2026-09-30T12:00:00+00:00"), ["B", "A", "A"], assumptions
    )
    second = anomalies(
        list(reversed(records)),
        at("2026-09-30T12:00:00+00:00"),
        ["A", "B"],
        assumptions,
    )
    assert [feature.station_id for feature in first[0]] == ["A", "B"]
    assert [feature.model_dump_json() for feature in first[0]] == [
        feature.model_dump_json() for feature in second[0]
    ]
    assert first[1] == second[1]


def test_feature_as_of_requires_timezone(assumptions):
    observations = empty_observations()
    with pytest.raises(ValueError, match="explicit UTC offset"):
        build_features(observations, datetime(2026, 9, 30), assumptions, ["A"])
