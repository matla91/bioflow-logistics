import json

import pytest
from baselhack.storage import ROOT, validate
from jsonschema import Draft202012Validator, ValidationError
from pydantic import ValidationError as ModelValidationError


def test_schema_definitions():
    for path in (ROOT / "schemas").glob("*.schema.json"):
        Draft202012Validator.check_schema(json.loads(path.read_text()))


def test_every_output_validates():
    paths = list((ROOT / "snapshots").rglob("*.json"))
    assert paths, "Generate cached outputs before testing"
    for path in paths:
        validate(path.stem, json.loads(path.read_text()))


def test_reject_offsetless_time_and_override_without_action():
    entry = {
        "decision_id": "D-test",
        "by": "operator",
        "verdict": "OVERRIDE",
        "reason": "stock checked",
        "at": "2026-10-01T06:00:00",
        "decision_snapshot_sha256": "0" * 64,
    }
    with pytest.raises((ValidationError, ModelValidationError)):
        validate("log", [entry])
    entry["at"] += "+02:00"
    with pytest.raises((ValidationError, ModelValidationError)):
        validate("log", [entry])
