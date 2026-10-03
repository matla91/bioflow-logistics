"""Local offline file server and append-only demo decision log; no external calls.

Demo roles are labels, not authentication. Production auth and QA release workflows
must be designed before deployment. This server binds to loopback only.
"""

import argparse
import json
import threading
from datetime import datetime, timezone
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from jsonschema import ValidationError as SchemaValidationError

from baselhack.storage import ROOT, canonical, snapshot_sha256, validate

LOCK = threading.Lock()


def snapshot_directory(scene, variant=""):
    if (
        not isinstance(scene, str)
        or Path(scene).name != scene
        or not (ROOT / "scenarios" / f"{scene}.yaml").is_file()
    ):
        raise ValueError("Unknown scene")
    base = ROOT / "snapshots" / scene
    if variant:
        if not isinstance(variant, str) or Path(variant).name != variant:
            raise ValueError("Unknown variant")
        manifest = json.loads((base / "variants.json").read_text())
        if not any(v["id"] == variant and v["ready"] for v in manifest):
            raise ValueError("Unknown variant")
        return base / "variants" / variant
    return base


def append_log(scene, request):
    if (
        not (ROOT / "scenarios" / f"{scene}.yaml").is_file()
        or Path(scene).name != scene
    ):
        raise ValueError("Unknown scene")
    with LOCK:
        base = ROOT / "snapshots" / scene
        directory = snapshot_directory(scene, request.get("variant", ""))
        decision = json.loads((directory / "decision.json").read_text())
        if request.get("decision_id") != decision["decision_id"]:
            raise ValueError("Decision changed; reload the evidence before approving")
        verdict = request.get("verdict")
        action = (
            request.get("chosen_action")
            if verdict == "OVERRIDE"
            else decision["recommended"]
        )
        role = (
            "QA"
            if decision["recommended"] == "QUARANTINE" or action == "QUARANTINE"
            else "logistics"
            if action in ("EXPEDITE", "REROUTE")
            else "operator"
        )
        if request.get("by") != role:
            raise ValueError(f"This action requires {role}")
        reason = request.get("reason", "").strip()
        if not reason:
            raise ValueError("A nonempty reason is required")
        entry = {
            "decision_id": decision["decision_id"],
            "by": request["by"],
            "verdict": verdict,
            "reason": reason,
            "at": datetime.now(timezone.utc).isoformat(),
            "decision_snapshot_sha256": snapshot_sha256(decision),
        }
        entry["chosen_action"] = action
        validate("log", [entry])
        path = base / "log.json"
        existing = json.loads(path.read_text()) if path.exists() else []
        history = existing + [entry]
        validate("log", history)
        evidence = base / "evidence" / entry["decision_snapshot_sha256"]
        evidence.mkdir(parents=True, exist_ok=True)
        for kind in ("scenario", "timeline", "risk", "decision"):
            value = json.loads((directory / f"{kind}.json").read_text())
            destination = evidence / f"{kind}.json"
            encoded = canonical(value) + "\n"
            if destination.exists() and destination.read_text() != encoded:
                raise ValueError("Immutable evidence snapshot conflict")
            destination.write_text(encoded)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(canonical(history) + "\n")
        temporary.replace(path)
        return history


app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


@app.get("/api/scenes")
def scenes():
    return [
        {
            "id": p.stem,
            "ready": (ROOT / "snapshots" / p.stem / "decision.json").is_file(),
        }
        for p in sorted((ROOT / "scenarios").glob("*.yaml"))
    ]


@app.post("/api/log", status_code=201)
def log_entry(payload: dict):
    try:
        scene = payload.pop("scenario_id", "")
        return append_log(scene, payload)
    except (ValueError, KeyError, TypeError, SchemaValidationError) as error:
        return JSONResponse({"error": str(error)}, status_code=400)
    except FileNotFoundError:
        return JSONResponse(
            {"error": "Scene evidence unavailable; regenerate snapshots"},
            status_code=409,
        )


@app.get("/snapshots/{relative:path}")
def snapshot_file(relative: str):
    base = (ROOT / "snapshots").resolve()
    target = (base / relative).resolve()
    if not target.is_relative_to(base) or target.suffix != ".json":
        return JSONResponse({"error": "Forbidden"}, status_code=403)
    if not target.exists() and target.name == "log.json":
        return JSONResponse([])
    if not target.is_file():
        return JSONResponse({"error": "Scene snapshot unavailable"}, status_code=404)
    return FileResponse(target)


@app.get("/{relative:path}")
def web_asset(relative: str):
    base = (ROOT / "web" / "dist").resolve()
    target = (base / (relative or "index.html")).resolve()
    if not target.is_relative_to(base):
        return JSONResponse({"error": "Forbidden"}, status_code=403)
    if not target.is_file():
        return JSONResponse(
            {"error": "Web asset unavailable; run pixi setup and build"},
            status_code=404,
        )
    return FileResponse(target)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scene", default="s1_normal_2026-05-10")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    print(f"Offline demo: http://127.0.0.1:{args.port}/?scene={args.scene}", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=args.port)
