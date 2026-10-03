"""Canonical presentation fields and truthful, compact evidence summaries."""

import json
from datetime import timedelta

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from pydantic import ValidationError

from baselhack.interfaces import LogisticsFrontendResult, ProvenanceSummary
from baselhack.logistics import evaluate, load_inputs
from baselhack.output.frontend import (
    dumps_frontend,
    provenance_summary,
    to_frontend,
    write_frontend,
)
from baselhack.storage import ROOT


@pytest.fixture
def result():
    inputs = load_inputs(
        ROOT / "data/cache/logistics_basel.json",
        ROOT / "scenarios/logistics_demo.json",
        ROOT / "config/logistics.yaml",
    )
    return evaluate(*inputs, ["402"])


def test_compact_payload_uses_only_canonical_frontend_contract(result):
    payload = json.loads(dumps_frontend(result))
    assert set(payload) == {
        "as_of",
        "shipment_id",
        "external_state",
        "simulated_shipment",
        "operational_impact",
        "actions",
        "recommendation",
        "data_provenance",
        "limitations",
    }
    assert set(payload["operational_impact"]) == {
        "predicted_delay_min",
        "delay_risk",
        "cold_chain_exposure_proxy_risk",
    }
    for action in payload["actions"]:
        assert set(action) == {
            "action",
            "eligible",
            "production_continuity_probability",
            "on_time_arrival_probability",
            "cold_chain_exposure_proxy_risk",
            "predicted_delay_min",
            "predicted_arrival_delay_min",
            "assessment",
            "reason",
        }

    def all_keys(value):
        if isinstance(value, dict):
            return set(value).union(*(all_keys(child) for child in value.values()))
        if isinstance(value, list):
            return set().union(*(all_keys(child) for child in value))
        return set()

    keys = all_keys(payload)
    assert "success_probability" not in keys
    assert "thermal_exposure_risk" not in keys
    assert "shipment_thermal_exposure_risk" not in keys
    assert "real_data_sources" not in payload
    assert "assumptions" not in payload
    assert "url" not in keys
    assert payload["simulated_shipment"]["simulated"] is True
    assert "success_probability" not in dumps_frontend(result)
    assert any(
        limitation.startswith("Deprecated success_probability")
        for limitation in result.limitations
    )


def test_frontend_schema_and_saved_roundtrip(result, tmp_path):
    payload = json.loads(dumps_frontend(result))
    schema = json.loads((ROOT / "schemas/logistics-frontend.schema.json").read_text())
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(payload)
    assert LogisticsFrontendResult.model_validate(payload) == to_frontend(result)
    target = write_frontend(result, tmp_path / "frontend.json")
    assert target.read_text() == dumps_frontend(result)
    assert dumps_frontend(result) == dumps_frontend(result)


def test_frontend_preserves_metrics_recommendation_and_ambient_guardrail(result):
    frontend = to_frontend(result)
    assert frontend.operational_impact.predicted_delay_min == result.predicted_delay_min
    assert (
        frontend.operational_impact.cold_chain_exposure_proxy_risk
        == result.cold_chain_exposure_proxy_risk
    )
    assert frontend.recommendation == result.recommendation
    for detailed, compact in zip(result.actions, frontend.actions, strict=True):
        for key, value in compact.model_dump().items():
            assert getattr(detailed, key) == value
    assert (
        "Ambient weather observations alone do not establish actual product-temperature excursion, "
        "pharmaceutical quality, or QA release status."
    ) in frontend.limitations


def test_frontend_boundary_revalidates_bad_copied_models(result, tmp_path):
    invalid = result.model_copy(update={"delay_risk": 2})
    with pytest.raises(ValidationError):
        dumps_frontend(invalid)
    target = tmp_path / "invalid.json"
    with pytest.raises(ValidationError):
        write_frontend(invalid, target)
    assert not target.exists()


def test_frontend_schema_rejects_deprecated_action_fields(result):
    payload = to_frontend(result).model_dump()
    payload["actions"][0]["success_probability"] = 1
    with pytest.raises(ValidationError):
        LogisticsFrontendResult.model_validate(payload)


def test_real_provenance_preserves_provider_observation_time_and_source_references(
    result,
):
    provenance = result.data_provenance
    expected = {
        "traffic_current": "100006",
        "rhine_current": "100089",
        "weather_current": "SwissMetNet BAS hourly observations",
    }
    for signal, dataset in expected.items():
        summary = provenance[signal]
        assert summary.kind == "REAL"
        assert summary.observed_at is not None
        assert summary.source_indices
        assert {
            result.real_data_sources[index].dataset for index in summary.source_indices
        } == {dataset}
        assert summary.provider
    assert provenance["weather_current"].provider == "MeteoSwiss"
    assert provenance["rhine_current"].observed_at == result.features.rhine.observed_at
    assert (
        provenance["weather_current"].observed_at == result.features.weather.observed_at
    )
    assert provenance["traffic_current"].observed_at == max(
        feature.interval_end for feature in result.features.traffic
    )


def test_transformed_features_and_assumptions_have_distinct_provenance(result):
    provenance = result.data_provenance
    assert provenance["shipment_state"].kind == "SIMULATED"
    assert provenance["model_coefficients"].kind == "ASSUMED"
    assert provenance["delay_simulation"].kind == "MODEL"
    assert provenance["traffic_anomaly"].kind == "MODEL"
    assert provenance["rhine_trends"].kind == "MODEL"
    assert provenance["weather_trend"].kind == "MODEL"
    assert (
        "historical statistical anomaly detection"
        in provenance["traffic_anomaly"].detail.lower()
    )
    assert provenance["rhine_navigation"].kind == "ASSUMED"
    assert provenance["rhine_navigation_delay"].kind == "ASSUMED"
    assert not any(
        summary.kind == "OFFICIAL_FORECAST" for summary in provenance.values()
    )


@pytest.mark.parametrize("missing", ["traffic", "rhine", "weather"])
def test_source_metadata_without_current_features_never_claims_current_real_evidence(
    result, missing
):
    features = result.features.model_copy(
        update={missing: [] if missing == "traffic" else None}
    )
    provenance = provenance_summary(
        features,
        result.simulated_shipment,
        result.assumptions,
        result.real_data_sources,
        result.navigation,
    )
    assert f"{missing}_current" not in provenance


def test_current_features_without_matching_source_never_claim_real_provenance(result):
    unrelated = result.real_data_sources[0].model_copy(
        update={"dataset": "unrelated", "provider": "Unrelated source"}
    )
    provenance = provenance_summary(
        result.features,
        result.simulated_shipment,
        result.assumptions,
        [unrelated],
        result.navigation,
    )
    assert not any(summary.kind == "REAL" for summary in provenance.values())
    assert provenance["traffic_anomaly"].source_indices == []
    assert provenance["rhine_trends"].source_indices == []


@pytest.mark.parametrize("signal", ["traffic", "rhine", "weather"])
@pytest.mark.parametrize("offset_min", [-10000, 1])
def test_stale_or_future_features_never_get_current_real_provenance(
    result, signal, offset_min
):
    at = result.as_of + timedelta(minutes=offset_min)
    current = getattr(result.features, signal)
    changed = (
        [feature.model_copy(update={"interval_end": at}) for feature in current]
        if signal == "traffic"
        else current.model_copy(update={"observed_at": at})
    )
    features = result.features.model_copy(update={signal: changed})
    provenance = provenance_summary(
        features,
        result.simulated_shipment,
        result.assumptions,
        result.real_data_sources,
        result.navigation,
    )
    assert f"{signal}_current" not in provenance


@pytest.mark.parametrize(
    "kind", ["REAL", "OFFICIAL_FORECAST", "MODEL", "SIMULATED", "ASSUMED"]
)
def test_provenance_contract_supports_all_five_categories(kind):
    assert (
        ProvenanceSummary(kind=kind, detail="Declared evidence category.").kind == kind
    )


def test_provenance_contract_rejects_unknown_category():
    with pytest.raises(ValidationError):
        ProvenanceSummary(kind="INFERRED_REAL", detail="Invalid category.")


def test_official_navigation_status_does_not_relabel_assumed_delay(result):
    navigation = result.navigation.model_copy(
        update={
            "kind": "OFFICIAL_FORECAST",
            "provider": "Declared official adapter",
            "observed_at": result.as_of,
            "delay_kind": "ASSUMED",
        }
    )
    provenance = provenance_summary(
        result.features,
        result.simulated_shipment,
        result.assumptions,
        result.real_data_sources,
        navigation,
    )
    assert provenance["rhine_navigation"].kind == "OFFICIAL_FORECAST"
    assert provenance["rhine_navigation"].provider == "Declared official adapter"
    assert provenance["rhine_navigation_delay"].kind == "ASSUMED"
    assert provenance["rhine_navigation_delay"].provider is None
