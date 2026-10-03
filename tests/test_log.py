import json

import pytest
from baselhack import api
from baselhack.storage import ROOT, snapshot_sha256


@pytest.fixture
def scene_root(tmp_path, monkeypatch):
    scene = "s3_lowriver_2026-10-01"
    (tmp_path / "scenarios").mkdir()
    (tmp_path / "scenarios" / (scene + ".yaml")).write_text("scenario_id: " + scene)
    output = tmp_path / "snapshots" / scene
    output.mkdir(parents=True)
    for kind in ("scenario", "timeline", "risk", "decision"):
        (output / (kind + ".json")).write_bytes(
            (ROOT / "snapshots" / scene / (kind + ".json")).read_bytes()
        )
    monkeypatch.setattr(api, "ROOT", tmp_path)
    return scene, output


def test_append_and_evidence_snapshot(scene_root):
    scene, output = scene_root
    d = json.loads((output / "decision.json").read_text())
    request = {
        "decision_id": d["decision_id"],
        "by": "operator",
        "verdict": "APPROVE",
        "reason": "Stock confirmed",
    }
    assert len(api.append_log(scene, request)) == 1
    assert len(api.append_log(scene, request)) == 2
    evidence = output / "evidence" / snapshot_sha256(d)
    assert json.loads((evidence / "decision.json").read_text()) == d
    assert all(
        (evidence / (kind + ".json")).exists()
        for kind in ("scenario", "timeline", "risk")
    )


def test_role_reason_and_stale_decision_rejected(scene_root):
    scene, output = scene_root
    d = json.loads((output / "decision.json").read_text())
    valid = {
        "decision_id": d["decision_id"],
        "by": "operator",
        "verdict": "OVERRIDE",
        "reason": "Review required",
        "chosen_action": "QUARANTINE",
    }
    with pytest.raises(ValueError, match="QA"):
        api.append_log(scene, valid)
    valid.update(by="QA", reason=" ")
    with pytest.raises(ValueError, match="reason"):
        api.append_log(scene, valid)
    valid.update(reason="Review required", decision_id="stale")
    with pytest.raises(ValueError, match="changed"):
        api.append_log(scene, valid)
