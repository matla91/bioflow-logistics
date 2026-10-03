"""End-to-end guarantees using provider observations and a separate demo state."""

import inspect
import json
import socket

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from pydantic import ValidationError

from baselhack.features import build_features
from baselhack.interfaces import (
    LogisticsFeatureBuilder,
    LogisticsResult,
    LogisticsSimulation,
    RealObservations,
    ShipmentState,
)
from baselhack.logistics import evaluate, load_inputs, main
from baselhack.output import dumps
from baselhack.simulation import simulate
from baselhack.storage import ROOT


@pytest.mark.parametrize(
    "implementation,contract",
    [(build_features, LogisticsFeatureBuilder), (simulate, LogisticsSimulation)],
)
def test_shared_part_signatures(implementation, contract):
    actual = inspect.signature(implementation)
    expected = inspect.signature(contract.__call__)
    assert list(actual.parameters) == [
        name for name in expected.parameters if name != "self"
    ]
    assert actual.return_annotation == expected.return_annotation


@pytest.fixture
def inputs():
    return load_inputs(
        ROOT / "data/cache/logistics_basel.json",
        ROOT / "scenarios/logistics_demo.json",
        ROOT / "config/logistics.yaml",
    )


def test_real_demo_feature_values_and_separation(inputs):
    observations, shipment, assumptions = inputs
    result = evaluate(observations, shipment, assumptions, ["402"])
    traffic = result.features.traffic[0]
    assert traffic.observed_count == 1262
    assert traffic.baseline_sample_count == 13
    assert traffic.baseline_mean == pytest.approx(1269.1538461538462)
    assert traffic.baseline_sd == pytest.approx(39.85775991749945)
    assert traffic.z_score == pytest.approx(-0.17948440074539437)
    assert result.features.rhine.level_masl == 244.815
    assert result.features.rhine.discharge_m3_s == 365.218
    assert result.features.weather.air_temperature_c == 26.4
    assert result.features.warnings == []
    assert {source.dataset for source in observations.sources} == {
        "100006",
        "100089",
        "SwissMetNet BAS hourly observations",
    }
    assert all(source.real_data for source in observations.sources)
    assert shipment.simulated and assumptions.assumed
    with pytest.raises(ValidationError):
        RealObservations.model_validate(
            {**observations.model_dump(), "shipment": shipment.model_dump()}
        )
    with pytest.raises(ValidationError):
        ShipmentState.model_validate({**shipment.model_dump(), "simulated": False})


def test_demo_is_offline_reproducible_and_schema_valid(inputs, monkeypatch, tmp_path):
    def no_network(*args, **kwargs):
        raise AssertionError("Offline demo attempted a network connection")

    monkeypatch.setattr(socket, "create_connection", no_network)
    first = evaluate(*inputs, ["402"])
    second = evaluate(*inputs, ["402"])
    assert dumps(first) == dumps(second)
    payload = json.loads(dumps(first))
    schema = json.loads((ROOT / "schemas/logistics.schema.json").read_text())
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(payload)
    assert LogisticsResult.model_validate(payload) == first
    for index in (1, 2):
        assert main(["demo", "--output", str(tmp_path / f"demo{index}.json")]) == 0
    assert (tmp_path / "demo1.json").read_bytes() == (
        tmp_path / "demo2.json"
    ).read_bytes()
    assert "actual product-temperature excursions" in " ".join(first.limitations)


def test_result_rejects_mismatched_action_probabilities(inputs):
    payload = evaluate(*inputs, ["402"]).model_dump()
    payload["action_success_probabilities"]["BUFFER"] = 0
    with pytest.raises(ValidationError, match="must agree"):
        LogisticsResult.model_validate(payload)


def test_output_revalidates_copied_and_nested_models(inputs):
    result = evaluate(*inputs, ["402"])
    with pytest.raises(ValidationError):
        dumps(result.model_copy(update={"delay_risk": 2}))
    broken_actions = [
        result.actions[0].model_copy(update={"shipment_thermal_exposure_risk": -1}),
        *result.actions[1:],
    ]
    with pytest.raises(ValidationError):
        dumps(result.model_copy(update={"actions": broken_actions}))


def test_missing_weather_fails_without_writing_output(inputs, tmp_path):
    observations, _, _ = inputs
    empty_weather = observations.model_copy(update={"weather": []})
    input_path = tmp_path / "without-weather.json"
    input_path.write_text(empty_weather.model_dump_json())
    output = tmp_path / "risk.json"
    assert (
        main(["demo", "--observations", str(input_path), "--output", str(output)]) == 1
    )
    assert not output.exists()


def test_fetch_preserves_existing_evidence(tmp_path):
    existing = tmp_path / "evidence.json"
    existing.write_text("preserved")
    assert main(["fetch", "--output", str(existing)]) == 1
    assert existing.read_text() == "preserved"
