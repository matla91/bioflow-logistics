"""Explainable policy cases use explicit factory and incoming-shipment outcomes."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

from baselhack.interfaces import (
    LogisticsActionResult,
    LogisticsAssumptions,
    LogisticsFeatures,
    ObservationSource,
    RecommendationPolicy,
    RhineFeatures,
    TrafficFeature,
    WeatherFeatures,
)
from baselhack.simulation.recommendation import recommend, with_counterfactual_changes

AS_OF = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)


@pytest.fixture
def assumptions():
    path = Path(__file__).resolve().parents[1] / "config" / "logistics.yaml"
    return LogisticsAssumptions.model_validate(yaml.safe_load(path.read_text()))


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
    # Synthetic unit-test metadata exercises the source-coverage heuristic only.
    return [
        ObservationSource(
            provider=provider,
            dataset=dataset,
            url="https://example.com/unit-test-only",
            retrieved_at=AS_OF,
            licence="unit-test-only",
        )
        for provider, dataset in (
            ("TEST FIXTURE Basel traffic", "100006"),
            ("TEST FIXTURE Basel Rhine", "100089"),
            ("TEST FIXTURE MeteoSwiss", "SwissMetNet BAS hourly observations"),
        )
    ]


def action(name, **changes):
    values = dict(
        action=name,
        eligible=True,
        production_continuity_probability=0.99,
        on_time_arrival_probability=0.97,
        cold_chain_exposure_proxy_risk=0.05,
        predicted_delay_min=1,
        predicted_arrival_delay_min=1,
        delay_risk=0.03,
        assessment="Unit-test scenario timing and ambient-proxy dimensions.",
        reason="Unit-test assumed route or stock availability.",
        success_probability=0,
    )
    values.update(changes)
    return LogisticsActionResult(**values)


def normal_actions():
    return [
        action("BUFFER", production_continuity_probability=1, predicted_delay_min=0),
        action(
            "EXPEDITE", cold_chain_exposure_proxy_risk=0, predicted_arrival_delay_min=0
        ),
        action("REROUTE", cold_chain_exposure_proxy_risk=0.01),
    ]


def disrupted_actions():
    return [
        action(
            "BUFFER",
            production_continuity_probability=1,
            on_time_arrival_probability=0.2,
            cold_chain_exposure_proxy_risk=0.8,
            predicted_delay_min=0,
            predicted_arrival_delay_min=80,
            success_probability=1,
        ),
        action(
            "EXPEDITE",
            cold_chain_exposure_proxy_risk=0.02,
            predicted_arrival_delay_min=1,
        ),
        action(
            "REROUTE",
            cold_chain_exposure_proxy_risk=0.15,
            predicted_arrival_delay_min=15,
        ),
    ]


def test_normal_stock_and_sufficient_incoming_shipment_prefer_buffer(
    features, assumptions, sources
):
    decision = recommend(normal_actions(), features, assumptions, sources)
    assert decision.action == "BUFFER"
    assert set(decision.why_not) == {"EXPEDITE", "REROUTE"}
    assert "no additional shipment intervention" in decision.reason
    assert "already meets all policy criteria" in decision.why_not["EXPEDITE"]


def test_buffer_factory_success_cannot_hide_incoming_delay_or_exposure(
    features, assumptions, sources
):
    decision = recommend(disrupted_actions(), features, assumptions, sources)
    assert decision.action == "EXPEDITE"
    assert "incoming on-time arrival 0.200 is below 0.900" in decision.why_not["BUFFER"]
    assert "cold-chain exposure proxy 0.800 exceeds 0.100" in decision.why_not["BUFFER"]
    assert "0.150 is higher than EXPEDITE's 0.020" in decision.why_not["REROUTE"]


@pytest.mark.parametrize(
    "expedite,reroute,expected",
    [
        (
            {"cold_chain_exposure_proxy_risk": 0.1, "predicted_arrival_delay_min": 40},
            {"cold_chain_exposure_proxy_risk": 0.2, "predicted_arrival_delay_min": 0},
            "EXPEDITE",
        ),
        (
            {"predicted_arrival_delay_min": 5},
            {"predicted_arrival_delay_min": 3},
            "REROUTE",
        ),
        (
            {"on_time_arrival_probability": 0.96},
            {"on_time_arrival_probability": 0.99},
            "REROUTE",
        ),
        ({}, {}, "EXPEDITE"),
    ],
)
def test_interventions_use_distinct_dimensions_in_order(
    features, assumptions, sources, expedite, reroute, expected
):
    actions = [
        action("BUFFER", eligible=False, success_probability=1),
        action("EXPEDITE", **expedite),
        action("REROUTE", **reroute),
    ]
    assert recommend(actions, features, assumptions, sources).action == expected
    # Input order must not change tie resolution.
    assert (
        recommend(list(reversed(actions)), features, assumptions, sources).action
        == expected
    )


def test_legacy_success_and_factory_delay_do_not_rank_incoming_actions(
    features, assumptions, sources
):
    actions = disrupted_actions()
    actions[1] = actions[1].model_copy(
        update={"success_probability": 0, "predicted_delay_min": 1000}
    )
    actions[2] = actions[2].model_copy(
        update={"success_probability": 1, "predicted_delay_min": 0}
    )
    assert recommend(actions, features, assumptions, sources).action == "EXPEDITE"


def test_qualified_stock_fallback_when_no_intervention_meets_continuity(
    features, assumptions, sources
):
    actions = disrupted_actions()
    actions[1] = actions[1].model_copy(
        update={"production_continuity_probability": 0.8}
    )
    actions[2] = actions[2].model_copy(
        update={"production_continuity_probability": 0.9}
    )
    decision = recommend(actions, features, assumptions, sources)
    assert decision.action == "BUFFER"
    assert "Incoming shipment criteria remain unmet" in decision.reason
    assert "0.800 is below the policy target 0.950" in decision.why_not["EXPEDITE"]


def test_unqualified_best_effort_prioritizes_factory_timing_then_proxy(
    features, assumptions, sources
):
    actions = [
        action(
            "BUFFER",
            production_continuity_probability=0.7,
            cold_chain_exposure_proxy_risk=0,
        ),
        action(
            "EXPEDITE",
            production_continuity_probability=0.94,
            cold_chain_exposure_proxy_risk=0.8,
        ),
        action(
            "REROUTE",
            production_continuity_probability=0.93,
            cold_chain_exposure_proxy_risk=0,
        ),
    ]
    decision = recommend(actions, features, assumptions, sources)
    assert decision.action == "EXPEDITE"
    assert "Reassessment is needed" in decision.reason
    assert "lower than EXPEDITE's 0.940" in decision.why_not["REROUTE"]


def test_no_eligible_action_returns_reassessment_without_an_invalid_choice(
    features, assumptions, sources
):
    actions = [a.model_copy(update={"eligible": False}) for a in normal_actions()]
    decision = recommend(actions, features, assumptions, sources)
    assert decision.action is None
    assert decision.confidence == "LOW"
    assert set(decision.why_not) == {"BUFFER", "EXPEDITE", "REROUTE"}
    assert all("Ineligible:" in reason for reason in decision.why_not.values())
    assert "reassess" in decision.reason


def test_unqualified_ties_use_action_priority_after_continuity_proxy_and_lateness(
    features, assumptions, sources
):
    actions = [
        action("BUFFER", eligible=False),
        action(
            "EXPEDITE",
            production_continuity_probability=0.94,
            on_time_arrival_probability=0.94,
        ),
        action(
            "REROUTE",
            production_continuity_probability=0.94,
            on_time_arrival_probability=0.99,
        ),
    ]
    decision = recommend(actions, features, assumptions, sources)
    assert decision.action == "EXPEDITE"
    assert "deterministic action priority" in decision.why_not["REROUTE"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("production_continuity_probability", 0.9499),
        ("on_time_arrival_probability", 0.8999),
        ("cold_chain_exposure_proxy_risk", 0.1001),
    ],
)
def test_buffer_target_boundaries_have_explicit_effects(
    features, assumptions, sources, field, value
):
    actions = normal_actions()
    actions[0] = actions[0].model_copy(
        update={
            "production_continuity_probability": 0.95,
            "on_time_arrival_probability": 0.90,
            "cold_chain_exposure_proxy_risk": 0.10,
        }
    )
    assert recommend(actions, features, assumptions, sources).action == "BUFFER"
    actions[0] = actions[0].model_copy(update={field: value})
    assert recommend(actions, features, assumptions, sources).action == "EXPEDITE"


def test_policy_targets_are_configurable_without_weighted_scoring(
    features, assumptions, sources
):
    actions = disrupted_actions()
    policy = RecommendationPolicy(
        target_on_time_arrival=0.1, max_exposure_proxy_risk=0.9
    )
    assumptions = assumptions.model_copy(update={"recommendation_policy": policy})
    assert recommend(actions, features, assumptions, sources).action == "BUFFER"


def test_complete_fresh_provider_coverage_can_only_reach_medium(
    features, assumptions, sources
):
    decision = recommend(normal_actions(), features, assumptions, sources)
    assert decision.confidence == "MEDIUM"
    assert assumptions.assumed is True


@pytest.mark.parametrize(
    "gap",
    [
        "warning",
        "missing_traffic",
        "unusable_traffic",
        "stale_traffic",
        "future_traffic",
        "missing_rhine",
        "stale_rhine",
        "missing_rhine_trend",
        "missing_weather",
        "stale_weather",
        "missing_rain",
        "missing_wind",
        "missing_source",
    ],
)
def test_data_gaps_reduce_evidence_quality_to_low(features, assumptions, sources, gap):
    if gap == "warning":
        features = features.model_copy(
            update={"warnings": ["Traffic coverage is incomplete."]}
        )
    elif gap == "missing_traffic":
        features = features.model_copy(update={"traffic": []})
    elif gap in {"unusable_traffic", "stale_traffic", "future_traffic"}:
        updates = (
            {"status": "missing_baseline", "z_score": None}
            if gap == "unusable_traffic"
            else {
                "interval_end": AS_OF
                - timedelta(minutes=assumptions.max_traffic_age_min + 1)
                if gap == "stale_traffic"
                else AS_OF + timedelta(minutes=1)
            }
        )
        features = features.model_copy(
            update={"traffic": [features.traffic[0].model_copy(update=updates)]}
        )
    elif gap == "missing_rhine":
        features = features.model_copy(update={"rhine": None})
    elif gap in {"stale_rhine", "missing_rhine_trend"}:
        updates = (
            {
                "observed_at": AS_OF
                - timedelta(minutes=assumptions.max_rhine_age_min + 1)
            }
            if gap == "stale_rhine"
            else {"level_trend_cm_per_hour": None}
        )
        features = features.model_copy(
            update={"rhine": features.rhine.model_copy(update=updates)}
        )
    elif gap == "missing_weather":
        features = features.model_copy(update={"weather": None})
    elif gap in {"stale_weather", "missing_rain", "missing_wind"}:
        updates = (
            {
                "observed_at": AS_OF
                - timedelta(minutes=assumptions.max_weather_age_min + 1)
            }
            if gap == "stale_weather"
            else {
                "precipitation_mm" if gap == "missing_rain" else "wind_speed_m_s": None
            }
        )
        features = features.model_copy(
            update={"weather": features.weather.model_copy(update=updates)}
        )
    else:
        sources = sources[:-1]
    assert (
        recommend(normal_actions(), features, assumptions, sources).confidence == "LOW"
    )


@pytest.mark.parametrize("ambient", [-20, 5, 35])
def test_ambient_weather_alone_never_selects_qa_review(
    features, assumptions, sources, ambient
):
    features = features.model_copy(
        update={
            "weather": features.weather.model_copy(
                update={"air_temperature_c": ambient}
            )
        }
    )
    decision = recommend(disrupted_actions(), features, assumptions, sources)
    assert decision.action == "EXPEDITE"
    assert "QA REVIEW" not in decision.model_dump_json()
    assert "excursion" not in decision.reason.lower()


def test_sensitivity_reports_only_observed_action_switches(
    features, assumptions, sources
):
    base = recommend(normal_actions(), features, assumptions, sources)
    changed = recommend(disrupted_actions(), features, assumptions, sources)
    enhanced = with_counterfactual_changes(
        base,
        [
            ("SIMULATED input unchanged", base),
            ("SIMULATED incoming journey changed in a tested scenario", changed),
            ("SIMULATED incoming journey changed in a tested scenario", changed),
        ],
    )
    assert enhanced.would_change_if == [
        "SIMULATED incoming journey changed in a tested scenario: the paired model rerun selects EXPEDITE."
    ]
    assert base.would_change_if == []
    assert enhanced.action == "BUFFER"
