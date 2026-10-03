"""Domain examples for snapshot delay, ambient proxy, and stock intervention."""

from datetime import datetime, timedelta, timezone

import numpy as np
import pytest
from pydantic import ValidationError

from baselhack.interfaces import (
    LogisticsAssumptions,
    LogisticsFeatures,
    ObservationSource,
    RhineFeatures,
    ShipmentState,
    TrafficFeature,
    WeatherFeatures,
)
from baselhack.simulation import simulate
from baselhack.simulation.delay import journey_durations
from baselhack.simulation.thermal import ambient_distance_c

AS_OF = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)


@pytest.fixture
def assumptions():
    return LogisticsAssumptions(
        n_runs=10000,
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
        delay_threshold_min=0,
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


@pytest.fixture
def shipment():
    return ShipmentState(
        shipment_id="SIMULATED-test-lot",
        as_of=AS_OF,
        deadline_at=AS_OF + timedelta(minutes=120),
        route_mode="road",
        planned_remaining_min=100,
        handling_min=20,
        protection_remaining_min=80,
        stock_available=1,
    )


@pytest.fixture
def features():
    return LogisticsFeatures(
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


@pytest.fixture
def sources():
    # Clearly synthetic provenance for unit tests; demo provenance is captured from providers.
    return [
        ObservationSource(
            provider="Unit-test source fixture",
            dataset="test-only",
            url="https://example.com/test-only",
            retrieved_at=AS_OF,
            licence="test-only",
        )
    ]


def action(result, name):
    return next(item for item in result.actions if item.action == name)


def test_same_seed_same_json_and_different_seed_changes_results(
    shipment, features, assumptions, sources
):
    assumptions = assumptions.model_copy(
        update={"transport_sd_min": 30, "handling_sd_min": 10}
    )
    first = simulate(shipment, features, assumptions, sources)
    assert (
        first.model_dump_json()
        == simulate(shipment, features, assumptions, sources).model_dump_json()
    )
    changed = simulate(
        shipment, features, assumptions.model_copy(update={"seed": 43}), sources
    )
    assert first.predicted_delay_min != changed.predicted_delay_min
    assert first.assumptions.seed == 42
    assert first.assumptions.n_runs == 10000
    assert first.real_data_sources == sources
    assert first.simulated_shipment.simulated is True
    assert first.assumptions.assumed is True


def test_action_success_counts_joint_event_not_product_of_marginals(
    shipment, features, assumptions, sources
):
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
        }
    )
    result = simulate(shipment, features, assumptions, sources)
    expedite = action(result, "EXPEDITE")
    # Both events require elapsed <= 100 min, so they are perfectly dependent.
    assert 0.4 < expedite.success_probability < 0.6
    assert expedite.success_probability == pytest.approx(1 - expedite.delay_risk)
    assert expedite.success_probability == pytest.approx(
        1 - expedite.shipment_thermal_exposure_risk
    )
    assert expedite.success_probability != pytest.approx(
        (1 - expedite.delay_risk) * (1 - expedite.shipment_thermal_exposure_risk)
    )


def test_buffer_covers_factory_but_preserves_incoming_thermal_risk(
    shipment, features, assumptions, sources
):
    shipment = shipment.model_copy(
        update={"protection_remaining_min": 0, "deadline_at": AS_OF}
    )
    result = simulate(shipment, features, assumptions, sources)
    buffer = action(result, "BUFFER")
    assert result.predicted_delay_min == 120
    assert result.delay_risk == 1
    assert result.thermal_exposure_risk == 1
    assert buffer.eligible is True
    assert buffer.success_probability == 1
    assert buffer.predicted_delay_min == 0
    assert buffer.delay_risk == 0
    assert buffer.shipment_thermal_exposure_risk == result.thermal_exposure_risk


def test_insufficient_stock_never_claims_buffer_success(
    shipment, features, assumptions, sources
):
    shipment = shipment.model_copy(update={"stock_available": 0, "deadline_at": AS_OF})
    result = simulate(shipment, features, assumptions, sources)
    buffer = action(result, "BUFFER")
    assert buffer.eligible is False
    assert buffer.success_probability == 0
    assert buffer.predicted_delay_min == result.predicted_delay_min
    assert buffer.delay_risk == result.delay_risk
    assert buffer.shipment_thermal_exposure_risk == result.thermal_exposure_risk
    # Even an arriving safe lot does not make the unavailable stock action eligible.
    timely = simulate(
        shipment.model_copy(update={"deadline_at": AS_OF + timedelta(minutes=200)}),
        features,
        assumptions,
        sources,
    )
    assert action(timely, "BUFFER").success_probability == 0


@pytest.mark.parametrize("ambient", [18, -8])
def test_hot_and_cold_exposure_exact_budget_and_protection_boundary(
    shipment, features, assumptions, sources, ambient
):
    features = features.model_copy(
        update={
            "weather": features.weather.model_copy(
                update={"air_temperature_c": ambient}
            )
        }
    )
    assert ambient_distance_c(ambient, (2, 8)) == 10
    at_budget = simulate(shipment, features, assumptions, sources)
    assert at_budget.thermal_exposure_risk == 0  # 10°C * (120 - 80) min = 400°C·min.
    beyond = simulate(
        shipment.model_copy(update={"protection_remaining_min": 79}),
        features,
        assumptions,
        sources,
    )
    assert beyond.thermal_exposure_risk == 1
    protected = simulate(
        shipment.model_copy(update={"protection_remaining_min": 120}),
        features,
        assumptions,
        sources,
    )
    assert protected.thermal_exposure_risk == 0


def test_prior_proxy_survives_protection_and_ambient_inside_band(
    shipment, features, assumptions, sources
):
    features = features.model_copy(
        update={"weather": features.weather.model_copy(update={"air_temperature_c": 5})}
    )
    assert simulate(shipment, features, assumptions, sources).thermal_exposure_risk == 0
    prior = shipment.model_copy(
        update={"prior_exposure_degree_min": 401, "protection_remaining_min": 10000}
    )
    result = simulate(prior, features, assumptions, sources)
    assert result.thermal_exposure_risk == 1
    assert all(item.shipment_thermal_exposure_risk == 1 for item in result.actions)


def test_river_penalties_only_river_and_weather_reaches_reroute(
    shipment, features, assumptions, sources
):
    features = features.model_copy(
        update={
            "traffic": [features.traffic[0].model_copy(update={"z_score": 2})],
            "rhine": features.rhine.model_copy(
                update={
                    "level_trend_cm_per_hour": -2,
                    "discharge_trend_m3_s_per_hour": -10,
                }
            ),
            "weather": features.weather.model_copy(
                update={"precipitation_mm": 1, "wind_speed_m_s": 12}
            ),
        }
    )
    shipment = shipment.model_copy(update={"deadline_at": AS_OF})
    road = simulate(shipment, features, assumptions, sources)
    river = simulate(
        shipment.model_copy(update={"route_mode": "river"}),
        features,
        assumptions,
        sources,
    )
    # Transport 100 + traffic 20 + rain 3 + wind 4; handling 20 is separate.
    assert road.predicted_delay_min == 147
    assert river.predicted_delay_min == 167  # River level 10 + discharge 10.
    assert action(road, "EXPEDITE").predicted_delay_min == 73.5
    assert action(river, "EXPEDITE").predicted_delay_min == 83.5
    # Alternative transport 50 + half traffic 10 + weather 7, plus handling 20 + transfer 10.
    assert action(road, "REROUTE").predicted_delay_min == 97
    assert action(river, "REROUTE").predicted_delay_min == 97
    assert not any(item.name.startswith("Rhine") for item in road.main_risk_drivers)


def test_traffic_uses_largest_positive_z_with_cap_and_river_cap(
    shipment, features, assumptions, sources
):
    features = features.model_copy(
        update={
            "traffic": [
                features.traffic[0].model_copy(
                    update={"z_score": value, "station_id": f"station-{value}"}
                )
                for value in (-5, 2, 10)
            ],
            "rhine": features.rhine.model_copy(
                update={
                    "level_trend_cm_per_hour": -2,
                    "discharge_trend_m3_s_per_hour": -20,
                }
            ),
        }
    )
    assumptions = assumptions.model_copy(update={"river_penalty_cap_min": 10})
    shipment = shipment.model_copy(update={"route_mode": "river", "deadline_at": AS_OF})
    result = simulate(shipment, features, assumptions, sources)
    assert (
        result.predicted_delay_min == 160
    )  # 100 transport + 20 handling + 30 traffic + capped river 10.
    river_drivers = [
        item for item in result.main_risk_drivers if item.name.startswith("Rhine")
    ]
    assert sum(
        item.estimated_delay_contribution_min for item in river_drivers
    ) == pytest.approx(10)
    assert all(item.evidence_kind == "observed" for item in river_drivers)
    assert all("ASSUMED" in item.explanation for item in river_drivers)


def test_negative_traffic_and_rising_rhine_do_not_accelerate_route(
    shipment, features, assumptions, sources
):
    features = features.model_copy(
        update={
            "traffic": [features.traffic[0].model_copy(update={"z_score": -2})],
            "rhine": features.rhine.model_copy(
                update={
                    "level_trend_cm_per_hour": 2,
                    "discharge_trend_m3_s_per_hour": 10,
                }
            ),
        }
    )
    shipment = shipment.model_copy(update={"route_mode": "river", "deadline_at": AS_OF})
    assert simulate(shipment, features, assumptions, sources).predicted_delay_min == 120


def test_paired_draws_and_nonnegative_durations(shipment, assumptions):
    assumptions = assumptions.model_copy(
        update={"transport_sd_min": 1000, "handling_sd_min": 1000}
    )
    durations = journey_durations(shipment, assumptions, 10, 20, 5)
    assert all(np.all(values >= 0) for values in durations.values())
    assert np.array_equal(durations["BASELINE"], durations["BUFFER"])
    # Equal half-speed factors halve every same paired baseline journey.
    assert np.array_equal(durations["EXPEDITE"], durations["BASELINE"] * 0.5)


@pytest.mark.parametrize("threshold,expected_risk", [(19, 1), (20, 0), (21, 0)])
def test_delay_threshold_boundary_does_not_change_mean_lateness(
    shipment, features, assumptions, sources, threshold, expected_risk
):
    shipment = shipment.model_copy(
        update={"deadline_at": AS_OF + timedelta(minutes=100)}
    )
    assumptions = assumptions.model_copy(update={"delay_threshold_min": threshold})
    result = simulate(shipment, features, assumptions, sources)
    assert result.predicted_delay_min == 20
    assert result.delay_risk == expected_risk


@pytest.mark.parametrize("offset_min", [-121, 1])
def test_stale_or_future_weather_is_rejected(
    shipment, features, assumptions, sources, offset_min
):
    features = features.model_copy(
        update={
            "weather": features.weather.model_copy(
                update={"observed_at": AS_OF + timedelta(minutes=offset_min)}
            )
        }
    )
    with pytest.raises(ValueError, match="Weather"):
        simulate(shipment, features, assumptions, sources)


def test_missing_weather_and_mismatched_snapshot_are_rejected(
    shipment, features, assumptions, sources
):
    with pytest.raises(ValueError, match="Weather is missing"):
        simulate(
            shipment,
            features.model_copy(update={"weather": None}),
            assumptions,
            sources,
        )
    with pytest.raises(ValueError, match="same instant"):
        simulate(
            shipment,
            features.model_copy(update={"as_of": AS_OF + timedelta(minutes=1)}),
            assumptions,
            sources,
        )
    with pytest.raises(ValueError, match="provenance"):
        simulate(shipment, features, assumptions, [])


def test_missing_or_stale_flow_signals_warn_and_are_ignored(
    shipment, features, assumptions, sources
):
    shipment = shipment.model_copy(update={"route_mode": "river", "deadline_at": AS_OF})
    features = features.model_copy(
        update={
            "traffic": [
                features.traffic[0].model_copy(
                    update={
                        "z_score": 100,
                        "interval_end": AS_OF - timedelta(minutes=121),
                    }
                )
            ],
            "rhine": features.rhine.model_copy(
                update={
                    "observed_at": AS_OF - timedelta(minutes=121),
                    "level_trend_cm_per_hour": -100,
                }
            ),
        }
    )
    result = simulate(shipment, features, assumptions, sources)
    assert result.predicted_delay_min == 120
    assert any(
        "traffic delay risk may be underestimated" in item
        for item in result.limitations
    )
    assert any(
        "river delay risk may be underestimated" in item for item in result.limitations
    )
    missing = simulate(
        shipment,
        features.model_copy(update={"traffic": [], "rhine": None}),
        assumptions,
        sources,
    )
    assert missing.predicted_delay_min == 120


@pytest.mark.parametrize(
    "warning",
    [
        "Traffic station absent: no complete observation at or before as_of.",
        "Traffic station absent: latest observation is stale (121 min).",
        "Traffic station absent: conflicting counts were excluded.",
        "Traffic station absent: insufficient earlier weekday/hour baseline.",
    ],
)
def test_partial_selected_traffic_coverage_warns_with_usable_station(
    shipment, features, assumptions, sources, warning
):
    # The missing station has already been omitted by feature extraction.
    features = features.model_copy(update={"warnings": [warning]})
    result = simulate(shipment, features, assumptions, sources)
    assert len(result.features.traffic) == 1
    assert result.features.traffic[0].status == "ok"
    assert any(
        "traffic delay risk may be underestimated" in value
        for value in result.limitations
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"planned_remaining_min": -1},
        {"handling_min": -1},
        {"protection_remaining_min": -1},
        {"stock_available": -1},
        {"deadline_at": AS_OF - timedelta(minutes=1)},
        {"as_of": datetime(2026, 10, 3, 12)},
    ],
)
def test_invalid_shipment_states_rejected(shipment, changes):
    with pytest.raises(ValidationError):
        ShipmentState.model_validate(shipment.model_dump() | changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"n_runs": 0},
        {"seed": -1},
        {"transport_sd_min": -1},
        {"traffic_min_per_positive_z": float("nan")},
        {"ambient_reference_band_c": (8, 2)},
        {"exposure_budget_degree_min": 0},
        {"expedite_transport_factor": 1.1},
    ],
)
def test_invalid_assumptions_rejected(assumptions, changes):
    with pytest.raises(ValidationError):
        LogisticsAssumptions.model_validate(assumptions.model_dump() | changes)


def test_output_names_explicitly_limit_thermal_claims(
    shipment, features, assumptions, sources
):
    result = simulate(shipment, features, assumptions, sources)
    assert any(
        "ambient observations alone do not establish actual product-temperature excursions"
        in value
        for value in result.limitations
    )
    assert any(
        "ASSUMED snapshot ambient remains constant" in value
        for value in result.limitations
    )
    assert {item.action for item in result.actions} == {"BUFFER", "EXPEDITE", "REROUTE"}
    assert set(result.action_success_probabilities) == {"BUFFER", "EXPEDITE", "REROUTE"}
    assert all(
        0 <= value <= 1 for value in result.action_success_probabilities.values()
    )
