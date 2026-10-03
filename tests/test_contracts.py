"""Adapt kit contract tests to function-shaped parts and single-source models."""

import inspect

import pytest
from baselhack import interfaces
from baselhack.generate import generate
from baselhack.ml.decision_analysis import analyze
from baselhack.rules.engine import decide
from baselhack.scenario import build
from baselhack.simulator.journey import simulate
from baselhack.storage import ROOT, read_json

IMPLEMENTATIONS = [
    (build, interfaces.ScenarioBuilder),
    (simulate, interfaces.Simulator),
    (analyze, interfaces.DecisionAnalysis),
    (decide, interfaces.RuleEngine),
]


@pytest.mark.parametrize("implementation,contract", IMPLEMENTATIONS)
def test_part_signature(implementation, contract):
    actual = [
        (p.name, p.kind) for p in inspect.signature(implementation).parameters.values()
    ]
    expected = [
        (p.name, p.kind)
        for p in inspect.signature(contract.__call__).parameters.values()
        if p.name != "self"
    ]
    assert actual == expected


def test_generated_contracts_are_current():
    generate(check=True)


def test_artifacts_validate_against_single_source():
    for scene in sorted((ROOT / "scenarios").glob("*.yaml")):
        for kind, model in interfaces.ARTIFACT_MODELS.items():
            if kind != "log":
                model.model_validate(read_json(f"snapshots/{scene.stem}/{kind}.json"))
