import hashlib
import json
import os
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(os.environ.get("BASELHACK_ROOT", Path(__file__).resolve().parents[2]))


def read_yaml(path):
    return yaml.safe_load((ROOT / path).read_text())


def read_json(path):
    return json.loads((ROOT / path).read_text())


def canonical(value):
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    )


def snapshot_sha256(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def validate(kind, value):
    from baselhack.interfaces import ARTIFACT_MODELS

    ARTIFACT_MODELS[kind].model_validate(value)
    schema = read_json(f"schemas/{kind}.schema.json")
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(value)


def save(kind, scene, value):
    validate(kind, value)
    path = ROOT / "snapshots" / scene / f"{kind}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical(value) + "\n")
    return value
