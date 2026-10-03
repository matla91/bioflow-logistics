import json
import sqlite3

import httpx
import pytest
from baselhack.data_engine.database import Database, digest
from baselhack.data_engine.ingest import import_observations
from baselhack.integration import analyze_stored, create_app
from baselhack.interfaces import RealObservations
from baselhack.storage import ROOT
from fastapi.testclient import TestClient


@pytest.fixture
def database(tmp_path, monkeypatch):
    def no_network(*args, **kwargs):
        raise AssertionError("Integration must not fetch external providers")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", no_network)
    db = Database(tmp_path / "integration.sqlite3")
    db.initialize()
    import_observations(
        db,
        RealObservations.model_validate_json(
            (ROOT / "data/cache/logistics_basel.json").read_text()
        ),
    )
    from baselhack.interfaces import OperationalDataset

    db.store_operations(
        OperationalDataset.model_validate_json(
            (ROOT / "output/operations-demo.json").read_text()
        )
    )
    return db


def test_stored_data_to_api_and_immutable_evidence(database):
    records = [
        analyze_stored(database, name) for name in ("normal", "disruption", "severe")
    ]
    assert [r.result.recommendation.action for r in records] == [
        "BUFFER",
        "EXPEDITE",
        "REROUTE",
    ]
    assert analyze_stored(database, "normal") == records[0]
    with TestClient(create_app(database)) as client:
        response = client.get("/api/integration/assessments")
        assert response.status_code == 200
        assert len(response.json()) == 3
        record = client.get(
            f"/api/integration/assessments/{records[0].assessment_id}"
        ).json()
        assert record == records[0].model_dump(mode="json")
        dataset = client.get("/api/integration/operations").json()[0]
        assert len(dataset["batches"]) == 18
        planned = next(s for s in dataset["shipments"] if s["status"] == "planned")
        assert planned["actual_departure_at"] is None
        assert client.get("/api/integration/assessments/missing").status_code == 404
        assert client.post("/api/integration/assessments", json={}).status_code == 405
    with database.connect() as connection:
        row = connection.execute(
            "SELECT evidence_json FROM logistics_assessments WHERE assessment_id=?",
            (records[0].assessment_id,),
        ).fetchone()
        assert digest(json.loads(row[0])["inputs"]) == records[0].input_sha256
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute("UPDATE logistics_assessments SET scenario='severe'")
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute("DELETE FROM logistics_assessments")


def test_empty_store_has_no_fabricated_assessment(tmp_path):
    db = Database(tmp_path / "empty.sqlite3")
    db.initialize()
    with pytest.raises(ValueError, match="observations"):
        analyze_stored(db, "normal")
    with TestClient(create_app(db)) as client:
        assert client.get("/api/integration/assessments").json() == []
        assert client.get("/api/integration/operations").json() == []
