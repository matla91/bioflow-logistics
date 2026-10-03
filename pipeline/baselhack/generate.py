"""Generate JSON schemas and TypeScript from the single Pydantic source."""

import argparse
import json

from baselhack.interfaces import ARTIFACT_MODELS
from baselhack.storage import ROOT


def typescript(schema):
    if "$ref" in schema:
        return schema["$ref"].rsplit("/", 1)[-1]
    if "enum" in schema:
        return " | ".join(json.dumps(v) for v in schema["enum"])
    if "const" in schema:
        return json.dumps(schema["const"])
    if "anyOf" in schema:
        return " | ".join(typescript(part) for part in schema["anyOf"])
    kind = schema.get("type")
    if kind == "array":
        if "prefixItems" in schema:
            return "[" + ", ".join(typescript(p) for p in schema["prefixItems"]) + "]"
        return "(" + typescript(schema.get("items", {})) + ")[]"
    if kind == "object":
        props = schema.get("properties", {})
        if not props:
            return (
                "Record<string, "
                + typescript(schema.get("additionalProperties", {}))
                + ">"
            )
        required = schema.get("required", [])
        return (
            "{ "
            + "; ".join(
                json.dumps(k) + ("" if k in required else "?") + ": " + typescript(v)
                for k, v in props.items()
            )
            + " }"
        )
    return {
        "integer": "number",
        "number": "number",
        "string": "string",
        "boolean": "boolean",
        "null": "null",
    }.get(kind, "unknown")


def generated_files():
    result = {}
    definitions = {}
    roots = []
    for kind, model in ARTIFACT_MODELS.items():
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            **model.model_json_schema(),
        }
        result[ROOT / "schemas" / f"{kind}.schema.json"] = (
            json.dumps(schema, indent=2, sort_keys=True) + "\n"
        )
        definitions.update(schema.get("$defs", {}))
        roots.append((model.__name__, schema))
    types = [
        "// GENERATED from pipeline/baselhack/interfaces.py via Pydantic JSON Schema. Do not edit."
    ]
    for name, schema in sorted(definitions.items()):
        types.append(f"export type {name} = {typescript(schema)};")
    for name, schema in roots:
        if name not in definitions:
            types.append(f"export type {name} = {typescript(schema)};")
    types.append('export type Role = Decision["requires_approval_by"];')
    result[ROOT / "web" / "src" / "interfaces.ts"] = "\n".join(types) + "\n"
    return result


def generate(check=False):
    for path, content in generated_files().items():
        if check:
            if not path.exists() or path.read_text() != content:
                raise ValueError(
                    f"Generated contract drift: {path.relative_to(ROOT)}; run pixi run contracts"
                )
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    generate(parser.parse_args().check)
