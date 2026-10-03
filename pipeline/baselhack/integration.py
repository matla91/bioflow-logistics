"""Stored-data analysis worker and read API for the Laravel integration."""

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml
from fastapi import FastAPI, HTTPException

from baselhack.batch_assessment import DEFAULT_PROFILE_ID, analyze_batch
from baselhack.data_engine.database import Database, digest, utc
from baselhack.interfaces import (
    BatchAnalysisProfile,
    OperationalDataset,
    StoredBatchAssessment,
    StoredLogisticsAssessment,
    Timestamp,
)
from baselhack.logistics import evaluate, load_demo
from baselhack.output import to_frontend
from baselhack.storage import ROOT, canonical

MODEL_VERSION = "logistics-monte-carlo-v1"


def analyze_stored(database, scenario):
    """Never fetch providers. Scenario cutoff and assumptions remain explicit."""
    _, shipment, assumptions = load_demo(scenario)
    observations = database.observations(shipment.as_of)
    if not any((observations.traffic, observations.rhine, observations.weather)):
        raise ValueError("Import or collect observations before running analysis")
    inputs = {
        "observations": observations.model_dump(mode="json"),
        "shipment": shipment.model_dump(mode="json"),
        "assumptions": assumptions.model_dump(mode="json"),
        "station_ids": ["402"],
        "model_version": MODEL_VERSION,
    }
    detailed = evaluate(observations, shipment, assumptions, inputs["station_ids"])
    result = to_frontend(detailed)
    body = {
        "input_sha256": digest(inputs),
        "scenario": scenario,
        "model_version": MODEL_VERSION,
        "result": result.model_dump(mode="json"),
    }
    record = StoredLogisticsAssessment(assessment_id=digest(body), **body)
    evidence = canonical(
        {"inputs": inputs, "detailed": detailed.model_dump(mode="json")}
    )
    with database.connect() as connection:
        connection.execute(
            "INSERT OR IGNORE INTO logistics_assessments VALUES (?,?,?,?,?,?)",
            (
                record.assessment_id,
                scenario,
                utc(result.as_of),
                utc(datetime.now(timezone.utc)),
                record.model_dump_json(),
                evidence,
            ),
        )
    return record


def create_app(database):
    """Read-only HTTP boundary; collector/analysis scheduling stays outside requests."""
    app = FastAPI(title="Smartflow stored-data integration")

    @app.get("/api/integration/operations", response_model=list[OperationalDataset])
    def operations():
        with database.connect() as connection:
            rows = connection.execute(
                "SELECT dataset_json FROM operational_datasets ORDER BY id"
            ).fetchall()
        return [OperationalDataset.model_validate_json(row[0]) for row in rows]

    @app.get(
        "/api/integration/assessments", response_model=list[StoredLogisticsAssessment]
    )
    def assessments():
        with database.connect() as connection:
            rows = connection.execute(
                "SELECT payload_json FROM logistics_assessments ORDER BY as_of, scenario, assessment_id"
            ).fetchall()
        return [StoredLogisticsAssessment.model_validate_json(row[0]) for row in rows]

    @app.get(
        "/api/integration/assessments/{assessment_id}",
        response_model=StoredLogisticsAssessment,
    )
    def assessment(assessment_id: str):
        with database.connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM logistics_assessments WHERE assessment_id=?",
                (assessment_id,),
            ).fetchone()
        if row is None:
            raise HTTPException(404, "Assessment not found")
        return StoredLogisticsAssessment.model_validate_json(row[0])

    @app.get(
        "/api/integration/batch-assessments", response_model=list[StoredBatchAssessment]
    )
    def batch_assessments(
        dataset_id: str | None = None,
        batch_id: str | None = None,
        as_of: Timestamp | None = None,
    ):
        return database.batch_assessments(dataset_id, batch_id, as_of)

    @app.get(
        "/api/integration/batch-assessments/{assessment_id}",
        response_model=StoredBatchAssessment,
    )
    def batch_assessment(assessment_id: str):
        record = database.batch_assessment(assessment_id)
        if record is None:
            raise HTTPException(404, "Batch assessment not found")
        return record

    @app.get(
        "/api/integration/batches/{batch_id}/assessments/latest",
        response_model=StoredBatchAssessment,
    )
    def latest_batch_assessment(
        batch_id: str, dataset_id: str | None = None, as_of: Timestamp | None = None
    ):
        records = database.batch_assessments(dataset_id, batch_id, as_of)
        if not records:
            raise HTTPException(404, "No applicable batch assessment found")
        return records[0]

    return app


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=["analyze", "watch", "serve", "configure-batches", "analyze-batch"],
    )
    parser.add_argument(
        "--database", type=Path, default=ROOT / ".runtime/current-affairs.sqlite3"
    )
    parser.add_argument("--interval-min", type=float, default=60)
    parser.add_argument("--cycles", type=int)
    parser.add_argument("--port", type=int, default=8002)
    parser.add_argument("--dataset-id")
    parser.add_argument("--batch-id")
    parser.add_argument("--as-of", type=datetime.fromisoformat)
    parser.add_argument("--known-at", type=datetime.fromisoformat)
    parser.add_argument("--profile-id", default=DEFAULT_PROFILE_ID)
    parser.add_argument(
        "--profile", type=Path, default=ROOT / "config/batch_assessment.yaml"
    )
    args = parser.parse_args(argv)
    if args.interval_min <= 0 or args.cycles is not None and args.cycles < 1:
        parser.error("Interval and cycle count must be positive")
    database = Database(args.database)
    database.initialize()
    if args.command == "configure-batches":
        settings = yaml.safe_load(args.profile.read_text())
        logistics_path = args.profile.parent / settings.pop("logistics_config")
        profile = BatchAnalysisProfile.model_validate(
            {**settings, "logistics": yaml.safe_load(logistics_path.read_text())}
        )
        database.store_batch_profile(profile)
        print(profile.profile_id)
        return 0
    if args.command == "analyze-batch":
        if not all((args.dataset_id, args.batch_id, args.as_of)):
            parser.error(
                "analyze-batch requires --dataset-id, --batch-id and explicit --as-of"
            )
        try:
            record = analyze_batch(
                database,
                args.dataset_id,
                args.batch_id,
                args.as_of,
                args.profile_id,
                args.known_at,
            )
        except ValueError as error:
            parser.error(str(error))
        print(record.model_dump_json(indent=2))
        return 0
    if args.command == "serve":
        import uvicorn

        uvicorn.run(create_app(database), host="127.0.0.1", port=args.port)
        return 0
    cycles = 0
    while True:
        records = [
            analyze_stored(database, name)
            for name in ("normal", "disruption", "severe")
        ]
        print(json.dumps([r.assessment_id for r in records]), flush=True)
        cycles += 1
        if (
            args.command == "analyze"
            or args.cycles is not None
            and cycles >= args.cycles
        ):
            return 0
        time.sleep(args.interval_min * 60)


app = create_app(
    Database(
        os.environ.get(
            "CURRENT_AFFAIRS_DATABASE", ROOT / ".runtime/current-affairs.sqlite3"
        )
    )
)


if __name__ == "__main__":
    raise SystemExit(main())
