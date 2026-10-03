import pytest
from baselhack import api
from baselhack.storage import ROOT
from fastapi.testclient import TestClient


@pytest.fixture
def offline_client(tmp_path, monkeypatch):
    (tmp_path / "scenarios").mkdir()
    (tmp_path / "web" / "dist").mkdir(parents=True)
    (tmp_path / "web" / "dist" / "index.html").write_text("<html>Offline demo</html>")
    for scene in (ROOT / "scenarios").glob("*.yaml"):
        (tmp_path / "scenarios" / scene.name).write_text(scene.read_text())
        output = tmp_path / "snapshots" / scene.stem
        output.mkdir(parents=True)
        for kind in ("scenario", "timeline", "risk", "decision", "variants"):
            (output / f"{kind}.json").write_bytes(
                (ROOT / "snapshots" / scene.stem / f"{kind}.json").read_bytes()
            )
    monkeypatch.setattr(api, "ROOT", tmp_path)
    with TestClient(api.app) as client:
        yield client


def test_offline_views_and_persistent_qa_decision(offline_client):
    client = offline_client
    assert client.get("/").status_code == 200
    assert len(client.get("/api/scenes").json()) == 3
    scene = "s2_heat_2026-07-30"
    decision = client.get(f"/snapshots/{scene}/decision.json").json()
    for kind in ("scenario", "timeline", "risk"):
        assert client.get(f"/snapshots/{scene}/{kind}.json").status_code == 200
    request = {
        "scenario_id": scene,
        "decision_id": decision["decision_id"],
        "by": "operator",
        "verdict": "APPROVE",
        "reason": "Demo-only QA review of simulated evidence",
    }
    assert client.post("/api/log", json=request).status_code == 400
    request["by"] = "QA"
    response = client.post("/api/log", json=request)
    assert response.status_code == 201
    entries = client.get(f"/snapshots/{scene}/log.json").json()
    assert entries == response.json()
    sha = entries[0]["decision_snapshot_sha256"]
    evidence = client.get(f"/snapshots/{scene}/evidence/{sha}/decision.json").json()
    assert evidence == decision


def test_snapshot_route_cannot_read_private_files(offline_client):
    response = offline_client.get("/snapshots/%2e%2e/%2e%2e/.env")
    assert response.status_code == 403
