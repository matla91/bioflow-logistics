"""Named demos select distinct actions from metrics, never from scenario names."""

import json
import re
import socket

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from baselhack.interfaces import LogisticsResult
from baselhack.logistics import evaluate, load_demo, main
from baselhack.output import dumps_frontend
from baselhack.storage import ROOT


@pytest.mark.parametrize(
    "name,expected",
    [("normal", "BUFFER"), ("disruption", "EXPEDITE"), ("severe", "REROUTE")],
)
def test_named_demo_decisions_and_schema(name, expected, monkeypatch, tmp_path):
    def no_network(*args, **kwargs):
        raise AssertionError("Demo attempted a network connection")

    monkeypatch.setattr(socket, "create_connection", no_network)
    inputs = load_demo(name)
    first = evaluate(*inputs, ["402"])
    second = evaluate(*inputs, ["402"])
    assert first.recommendation.action == expected
    assert dumps_frontend(first) == dumps_frontend(second)
    assert set(first.recommendation.why_not) == {"BUFFER", "EXPEDITE", "REROUTE"} - {
        expected
    }
    assert first.recommendation.would_change_if
    assert first.recommendation.confidence == "MEDIUM"
    schema = json.loads((ROOT / "schemas/logistics-frontend.schema.json").read_text())
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(
        json.loads(dumps_frontend(first))
    )
    for index in (1, 2):
        assert (
            main(
                [
                    "demo",
                    "--scenario",
                    name,
                    "--output",
                    str(tmp_path / f"{index}.json"),
                ]
            )
            == 0
        )
    assert (tmp_path / "1.json").read_bytes() == (tmp_path / "2.json").read_bytes()
    assert (
        "Ambient weather observations alone do not establish actual product-temperature excursion, pharmaceutical quality, or QA release status."
        in first.limitations
    )


@pytest.mark.parametrize("name", ["normal", "disruption", "severe"])
def test_reported_change_conditions_reproduce_the_changed_decision(name):
    observations, shipment, assumptions = load_demo(name)
    baseline = evaluate(observations, shipment, assumptions, ["402"])
    for text in baseline.recommendation.would_change_if:
        match = re.fullmatch(
            r"(SIMULATED|ASSUMED) ([a-z_]+) changed from [0-9.]+ to ([0-9.]+) (?:min|units|factor): the paired model rerun selects (BUFFER|EXPEDITE|REROUTE)\.",
            text,
        )
        assert match, text
        kind, field, value, expected = match.groups()
        value = float(value) if field != "stock_available" else int(value)
        changed_shipment = (
            shipment.model_copy(update={field: value})
            if kind == "SIMULATED"
            else shipment
        )
        changed_assumptions = (
            assumptions.model_copy(update={field: value})
            if kind == "ASSUMED"
            else assumptions
        )
        rerun = evaluate(observations, changed_shipment, changed_assumptions, ["402"])
        assert rerun.recommendation.action == expected != baseline.recommendation.action


def test_scenario_names_and_identifiers_do_not_force_decisions():
    observations, shipment, assumptions = load_demo("normal")
    renamed = shipment.model_copy(update={"shipment_id": "SEVERE-REROUTE"})
    result = evaluate(observations, renamed, assumptions, ["402"])
    assert result.recommendation.action == "BUFFER"


def test_all_demo_external_observations_are_identical():
    sources = [load_demo(name)[0] for name in ("normal", "disruption", "severe")]
    assert sources[0] == sources[1] == sources[2]


def test_primary_and_detailed_cli_have_distinct_contracts(tmp_path):
    primary = tmp_path / "primary.json"
    detailed = tmp_path / "detailed.json"
    assert main(["demo", "--scenario", "normal", "--output", str(primary)]) == 0
    assert (
        main(["demo", "--scenario", "normal", "--detailed", "--output", str(detailed)])
        == 0
    )
    compact = json.loads(primary.read_text())
    internal = json.loads(detailed.read_text())
    assert "operational_impact" in compact and "assumptions" not in compact
    assert "assumptions" in internal and "real_data_sources" in internal
    assert compact["recommendation"] == internal["recommendation"]


def test_thermal_input_aliases_are_deprecated_and_never_serialized():
    result = evaluate(*load_demo("normal"), ["402"])
    payload = result.model_dump()
    payload["thermal_exposure_risk"] = payload.pop("cold_chain_exposure_proxy_risk")
    for action in payload["actions"]:
        action["shipment_thermal_exposure_risk"] = action.pop(
            "cold_chain_exposure_proxy_risk"
        )
    restored = LogisticsResult.model_validate(payload)
    assert restored.thermal_exposure_risk == result.cold_chain_exposure_proxy_risk
    assert "thermal_exposure_risk" not in restored.model_dump()
    assert all(
        "shipment_thermal_exposure_risk" not in a
        for a in restored.model_dump()["actions"]
    )
