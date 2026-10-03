"""Comparable timing dimensions, assumed navigation and exposure guardrails."""

from datetime import datetime, timedelta, timezone

import pytest

from baselhack.interfaces import (
    LogisticsAssumptions,
    LogisticsFeatures,
    LogisticsResult,
    ObservationSource,
    OfficialNavigationSignal,
    RhineFeatures,
    ShipmentState,
    TrafficFeature,
    WeatherFeatures,
)
from baselhack.simulation import simulate

AS_OF = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)


@pytest.fixture
def setup():
    assumptions = LogisticsAssumptions(
        n_runs=1000,
        seed=42,
        transport_sd_min=0,
        handling_sd_min=0,
        traffic_min_per_positive_z=10,
        traffic_z_cap=3,
        falling_level_min_per_cm_hour=5,
        falling_discharge_min_per_m3_s_hour=1,
        river_penalty_cap_min=60,
        rain_min_per_mm=3,
        wind_threshold_m_s=10,
        wind_min_per_m_s=2,
        delay_threshold_min=15,
        ambient_reference_band_c=(2, 8),
        exposure_budget_degree_min=400,
        expedite_transport_factor=0.5,
        expedite_handling_factor=0.5,
        reroute_transport_min=50,
        reroute_transport_sd_min=0,
        reroute_extra_handling_min=10,
        reroute_traffic_factor=0.5,
        max_traffic_age_min=120,
        max_rhine_age_min=120,
        max_weather_age_min=120,
        trend_window_min=180,
        trend_min_span_min=60,
        baseline_min_samples=3,
    )
    shipment = ShipmentState(
        shipment_id="SIMULATED-dimensions",
        as_of=AS_OF,
        deadline_at=AS_OF + timedelta(minutes=120),
        route_mode="river",
        planned_remaining_min=100,
        handling_min=20,
        protection_remaining_min=80,
        stock_available=1,
    )
    features = LogisticsFeatures(
        as_of=AS_OF,
        traffic=[
            TrafficFeature(
                station_id="test-station",
                interval_end=AS_OF,
                observed_count=100,
                baseline_mean=100,
                baseline_sd=10,
                baseline_sample_count=10,
                z_score=0,
                status="ok",
            )
        ],
        rhine=RhineFeatures(
            observed_at=AS_OF,
            level_masl=245,
            discharge_m3_s=1000,
            level_trend_cm_per_hour=0,
            discharge_trend_m3_s_per_hour=0,
            sample_count=6,
        ),
        weather=WeatherFeatures(
            observed_at=AS_OF,
            air_temperature_c=18,
            precipitation_mm=0,
            wind_speed_m_s=0,
            relative_humidity_pct=60,
            temperature_trend_c_per_hour=None,
        ),
        warnings=[],
    )
    sources = [
        ObservationSource(
            provider="Unit-test source fixture",
            dataset="test-only",
            url="https://example.com/test-only",
            retrieved_at=AS_OF,
            licence="test-only",
        )
    ]
    return shipment, features, assumptions, sources


def action(result, name):
    return next(item for item in result.actions if item.action == name)


def official(**changes):
    """Synthetic adapter input only; no integrated official source is claimed."""
    return OfficialNavigationSignal.model_validate(
        {
            "kind": "OFFICIAL_FORECAST",
            "state": "RESTRICTED",
            "provider": "Unit-test official adapter",
            "source_url": "https://example.com/test-only",
            "issued_at": AS_OF - timedelta(minutes=10),
            "valid_from": AS_OF - timedelta(minutes=5),
            "valid_until": AS_OF + timedelta(minutes=60),
            "normal_route_eligible": True,
            "expected_delay_min": 45,
        }
        | changes
    )


def test_stock_continuity_and_incoming_arrival_are_separate(setup):
    shipment, features, assumptions, sources = setup
    shipment = shipment.model_copy(
        update={"deadline_at": AS_OF, "protection_remaining_min": 0}
    )
    result = simulate(shipment, features, assumptions, sources)
    buffer = action(result, "BUFFER")
    assert buffer.production_continuity_probability == 1
    assert buffer.on_time_arrival_probability == 0
    assert buffer.cold_chain_exposure_proxy_risk == 1
    assert buffer.predicted_delay_min == 0
    assert buffer.predicted_arrival_delay_min == 120
    assert (
        buffer.success_probability == 1
    )  # Deprecated stock event, explicitly retained.
    assert "incoming shipment" in buffer.assessment


def test_ineligible_buffer_reports_incoming_factory_fallback(setup):
    shipment, features, assumptions, sources = setup
    result = simulate(
        shipment.model_copy(update={"stock_available": 0}),
        features,
        assumptions,
        sources,
    )
    buffer = action(result, "BUFFER")
    assert not buffer.eligible
    assert (
        buffer.production_continuity_probability
        == buffer.on_time_arrival_probability
        == 1
    )
    assert buffer.predicted_delay_min == buffer.predicted_arrival_delay_min == 0
    assert buffer.success_probability == 0


def test_exact_deadline_metrics_do_not_use_legacy_delay_tolerance(setup):
    shipment, features, assumptions, sources = setup
    shipment = shipment.model_copy(
        update={"deadline_at": AS_OF + timedelta(minutes=115), "stock_available": 0}
    )
    features = features.model_copy(
        update={"weather": features.weather.model_copy(update={"air_temperature_c": 5})}
    )
    assumptions = assumptions.model_copy(
        update={"expedite_transport_factor": 1, "expedite_handling_factor": 1}
    )
    expedite = action(simulate(shipment, features, assumptions, sources), "EXPEDITE")
    assert (
        expedite.production_continuity_probability
        == expedite.on_time_arrival_probability
        == 0
    )
    assert expedite.predicted_arrival_delay_min == 5
    assert expedite.delay_risk == 0
    assert expedite.success_probability == 1  # Legacy 15-min tolerance + zero proxy.


def test_seeded_timing_and_proxy_frequencies_remain_distinct_dimensions(setup):
    shipment, features, assumptions, sources = setup
    shipment = shipment.model_copy(
        update={
            "handling_min": 0,
            "protection_remaining_min": 0,
            "deadline_at": AS_OF + timedelta(minutes=100),
        }
    )
    features = features.model_copy(
        update={"weather": features.weather.model_copy(update={"air_temperature_c": 9})}
    )
    assumptions = assumptions.model_copy(
        update={
            "transport_sd_min": 20,
            "exposure_budget_degree_min": 100,
            "expedite_transport_factor": 1,
            "expedite_handling_factor": 1,
            "delay_threshold_min": 0,
        }
    )
    result = simulate(shipment, features, assumptions, sources)
    expedite, buffer = (action(result, name) for name in ("EXPEDITE", "BUFFER"))
    assert 0.4 < expedite.on_time_arrival_probability < 0.6
    assert (
        expedite.production_continuity_probability
        == expedite.on_time_arrival_probability
    )
    assert (
        expedite.on_time_arrival_probability
        == 1 - expedite.cold_chain_exposure_proxy_risk
    )
    assert expedite.success_probability == expedite.on_time_arrival_probability
    assert buffer.production_continuity_probability == 1
    assert buffer.on_time_arrival_probability == expedite.on_time_arrival_probability


def test_canonical_proxy_json_and_deprecated_python_aliases(setup):
    result = simulate(*setup)
    dump = result.model_dump()
    assert "cold_chain_exposure_proxy_risk" in dump
    assert "thermal_exposure_risk" not in dump
    assert result.thermal_exposure_risk == result.cold_chain_exposure_proxy_risk
    for item in result.actions:
        assert (
            item.shipment_thermal_exposure_risk == item.cold_chain_exposure_proxy_risk
        )
        assert "shipment_thermal_exposure_risk" not in item.model_dump()
    dump["thermal_exposure_risk"] = dump.pop("cold_chain_exposure_proxy_risk")
    for item in dump["actions"]:
        item["shipment_thermal_exposure_risk"] = item.pop(
            "cold_chain_exposure_proxy_risk"
        )
    assert (
        LogisticsResult.model_validate(dump).cold_chain_exposure_proxy_risk
        == result.cold_chain_exposure_proxy_risk
    )


@pytest.mark.parametrize("ambient", [-100, 100])
def test_ambient_alone_cannot_create_qa_review(setup, ambient):
    shipment, features, assumptions, sources = setup
    features = features.model_copy(
        update={
            "weather": features.weather.model_copy(
                update={"air_temperature_c": ambient}
            )
        }
    )
    result = simulate(
        shipment.model_copy(update={"protection_remaining_min": 0}),
        features,
        assumptions,
        sources,
    )
    assert result.cold_chain_exposure_proxy_risk == 1
    assert result.recommendation.action in {"BUFFER", "EXPEDITE", "REROUTE"}
    assert {item.action for item in result.actions} == {"BUFFER", "EXPEDITE", "REROUTE"}
    assert (
        "Ambient weather observations alone do not establish actual product-temperature excursion, pharmaceutical quality, or QA release status."
        in result.limitations
    )


@pytest.mark.parametrize(
    "trend,state,penalty",
    [(0, "NORMAL", 0), (-1, "WATCH", 5), (-6, "RESTRICTED", 30), (-12, "SEVERE", 60)],
)
def test_assumed_navigation_state_uses_configured_delay_bands(
    setup, trend, state, penalty
):
    shipment, features, assumptions, sources = setup
    features = features.model_copy(
        update={
            "rhine": features.rhine.model_copy(
                update={"level_trend_cm_per_hour": trend}
            )
        }
    )
    navigation = simulate(shipment, features, assumptions, sources).navigation
    assert (navigation.state, navigation.delay_penalty_min) == (state, penalty)
    assert navigation.kind == navigation.delay_kind == "ASSUMED"
    assert navigation.normal_route_eligible
    assert "ASSUMED delay bands" in navigation.reason


def test_level_and_discharge_do_not_double_count(setup):
    shipment, features, assumptions, sources = setup
    features = features.model_copy(
        update={
            "rhine": features.rhine.model_copy(
                update={
                    "level_trend_cm_per_hour": -2,
                    "discharge_trend_m3_s_per_hour": -10,
                }
            )
        }
    )
    result = simulate(shipment, features, assumptions, sources)
    assert result.navigation.delay_penalty_min == 10
    drivers = [
        item for item in result.main_risk_drivers if item.name.startswith("Rhine")
    ]
    assert sum(item.estimated_delay_contribution_min for item in drivers) == 10


@pytest.mark.parametrize(
    "rhine_change",
    [
        None,
        {"observed_at": AS_OF - timedelta(minutes=121)},
        {"observed_at": AS_OF + timedelta(minutes=1)},
        {"level_trend_cm_per_hour": None, "discharge_trend_m3_s_per_hour": None},
    ],
)
def test_missing_or_unusable_navigation_is_unknown(setup, rhine_change):
    shipment, features, assumptions, sources = setup
    rhine = (
        None if rhine_change is None else features.rhine.model_copy(update=rhine_change)
    )
    result = simulate(
        shipment, features.model_copy(update={"rhine": rhine}), assumptions, sources
    )
    assert result.navigation.state == "UNKNOWN"
    assert result.navigation.kind == "ASSUMED"
    assert result.recommendation.confidence == "LOW"
    assert result.navigation.warnings


def test_valid_official_input_overrides_state_and_delay(setup):
    shipment, features, assumptions, sources = setup
    features = features.model_copy(
        update={
            "official_navigation": official(),
            "rhine": features.rhine.model_copy(update={"level_trend_cm_per_hour": -12}),
        }
    )
    result = simulate(shipment, features, assumptions, sources)
    assert result.navigation.state == "RESTRICTED"
    assert result.navigation.kind == result.navigation.delay_kind == "OFFICIAL_FORECAST"
    assert result.navigation.delay_penalty_min == 45
    assert result.navigation.provider == "Unit-test official adapter"
    assert result.predicted_delay_min == 45
    official_driver = next(
        item
        for item in result.main_risk_drivers
        if item.name == "Rhine official navigation delay"
    )
    assert official_driver.evidence_kind == "official_forecast"


def test_official_operational_status_is_distinct_from_forecast(setup):
    shipment, features, assumptions, sources = setup
    features = features.model_copy(
        update={"official_navigation": official(kind="REAL")}
    )
    result = simulate(shipment, features, assumptions, sources)
    assert result.navigation.kind == result.navigation.delay_kind == "REAL"
    official_driver = next(
        item
        for item in result.main_risk_drivers
        if item.name == "Rhine official navigation delay"
    )
    assert official_driver.evidence_kind == "observed"


@pytest.mark.parametrize("boundary", ["valid_from", "valid_until"])
def test_official_validity_window_includes_exact_snapshot_boundary(setup, boundary):
    shipment, features, assumptions, sources = setup
    features = features.model_copy(
        update={"official_navigation": official(**{boundary: AS_OF})}
    )
    result = simulate(shipment, features, assumptions, sources)
    assert result.navigation.kind == "OFFICIAL_FORECAST"


def test_official_state_without_delay_retains_labelled_assumed_fallback(setup):
    shipment, features, assumptions, sources = setup
    features = features.model_copy(
        update={
            "official_navigation": official(state="SEVERE", expected_delay_min=None),
            "rhine": features.rhine.model_copy(update={"level_trend_cm_per_hour": -1}),
        }
    )
    result = simulate(shipment, features, assumptions, sources)
    assert result.navigation.state == "SEVERE"
    assert result.navigation.kind == "OFFICIAL_FORECAST"
    assert result.navigation.delay_kind == "ASSUMED"
    assert result.navigation.delay_penalty_min == 5
    assert "no delay estimate" in " ".join(result.limitations)


@pytest.mark.parametrize(
    "changes",
    [
        {"issued_at": AS_OF + timedelta(minutes=1)},
        {"valid_from": AS_OF + timedelta(minutes=1)},
        {"valid_until": AS_OF - timedelta(minutes=1)},
    ],
)
def test_invalid_at_snapshot_official_input_is_ignored(setup, changes):
    shipment, features, assumptions, sources = setup
    features = features.model_copy(update={"official_navigation": official(**changes)})
    result = simulate(shipment, features, assumptions, sources)
    assert result.navigation.state == "NORMAL"
    assert result.navigation.kind == result.navigation.delay_kind == "ASSUMED"
    assert "not valid at as_of" in " ".join(result.limitations)


def test_official_block_cannot_arrive_even_when_finite_horizon_fits_deadline(setup):
    shipment, features, assumptions, sources = setup
    shipment = shipment.model_copy(
        update={"deadline_at": AS_OF + timedelta(minutes=3000)}
    )
    features = features.model_copy(
        update={
            "official_navigation": official(
                state="SEVERE", normal_route_eligible=False, expected_delay_min=0
            )
        }
    )
    result = simulate(shipment, features, assumptions, sources)
    buffer, expedite, reroute = (
        action(result, name) for name in ("BUFFER", "EXPEDITE", "REROUTE")
    )
    assert buffer.production_continuity_probability == 1
    assert buffer.on_time_arrival_probability == 0
    assert (
        expedite.production_continuity_probability
        == expedite.on_time_arrival_probability
        == expedite.success_probability
        == 0
    )
    assert not expedite.eligible
    assert (
        reroute.production_continuity_probability
        == reroute.on_time_arrival_probability
        == 1
    )
    assert result.recommendation.action == "REROUTE"
    assert "not an arrival forecast" in " ".join(result.limitations)
    assert result.navigation.delay_penalty_min == assumptions.route_block_delay_min
    assert result.navigation.reported_delay_min == 0
    assert result.navigation.delay_kind == "ASSUMED"
    assert result.navigation.kind == "OFFICIAL_FORECAST"


@pytest.mark.parametrize(
    "reported,effective,delay_kind,eligible",
    [
        (0, 1440, "ASSUMED", False),
        (6000, 6000, "OFFICIAL_FORECAST", False),
        (0, 0, "OFFICIAL_FORECAST", True),
    ],
)
def test_navigation_exports_actual_applied_delay_and_separate_reported_value(
    setup, reported, effective, delay_kind, eligible
):
    shipment, features, assumptions, sources = setup
    shipment = shipment.model_copy(update={"deadline_at": AS_OF})
    features = features.model_copy(
        update={
            "official_navigation": official(
                expected_delay_min=reported,
                normal_route_eligible=eligible,
            )
        }
    )
    result = simulate(shipment, features, assumptions, sources)
    assert result.navigation.reported_delay_min == reported
    assert result.navigation.delay_penalty_min == effective
    assert result.navigation.kind == "OFFICIAL_FORECAST"
    assert result.navigation.delay_kind == delay_kind
    assert result.predicted_delay_min == 120 + effective
    assert (
        action(result, "EXPEDITE").predicted_arrival_delay_min
        == (120 + effective) * 0.5
    )
    rhine_drivers = [
        item for item in result.main_risk_drivers if item.name.startswith("Rhine")
    ]
    assert (
        sum(item.estimated_delay_contribution_min for item in rhine_drivers)
        == effective
    )
    assert result.data_provenance["rhine_navigation_delay"].kind == delay_kind


def test_simulated_intervention_availability_blocks_selection(setup):
    shipment, features, assumptions, sources = setup
    shipment = shipment.model_copy(
        update={
            "stock_available": 0,
            "expedite_available": False,
            "reroute_available": False,
        }
    )
    result = simulate(shipment, features, assumptions, sources)
    assert result.recommendation.action is None
    assert all(not item.eligible for item in result.actions)
    assert all(
        action(result, name).production_continuity_probability == 0
        for name in ("EXPEDITE", "REROUTE")
    )


def test_sensitivity_text_reports_actual_single_input_reruns(setup):
    result = simulate(*setup)
    assert result.recommendation.action == "BUFFER"
    changed_input = "SIMULATED planned_remaining_min changed from 100 to 150 min"
    assert any(
        changed_input in text and "selects EXPEDITE" in text
        for text in result.recommendation.would_change_if
    )
    shipment, features, assumptions, sources = setup
    changed = simulate(
        shipment.model_copy(update={"planned_remaining_min": 150}),
        features,
        assumptions,
        sources,
    )
    assert changed.recommendation.action == "EXPEDITE"
    assert len(result.recommendation.would_change_if) <= 3
    assert result.model_dump_json() == simulate(*setup).model_dump_json()
