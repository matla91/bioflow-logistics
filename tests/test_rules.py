import pytest
from baselhack.ml.decision_analysis import analyze
from baselhack.rules.engine import decide
from baselhack.storage import read_json


@pytest.mark.parametrize(
    "scene,expected",
    [
        ("s1_normal_2026-05-10", "RUN_AS_PLANNED"),
        ("s2_heat_2026-07-30", "QUARANTINE"),
        ("s3_lowriver_2026-10-01", "BUFFER"),
    ],
)
def test_verified_output_recommendations(scene, expected):
    decision = read_json(f"snapshots/{scene}/decision.json")
    recomputed = decide(
        read_json(f"snapshots/{scene}/scenario.json"),
        read_json(f"snapshots/{scene}/timeline.json"),
        read_json(f"snapshots/{scene}/risk.json"),
    )
    assert recomputed["recommended"] == decision["recommended"] == expected
    assert len(decision["rejected"]) == 4
    assert all(r["source"] and r["at"] for r in decision["reasons"])


def test_quarantine_priority_even_with_stock():
    s = read_json("snapshots/s3_lowriver_2026-10-01/scenario.json")
    t = read_json("snapshots/s3_lowriver_2026-10-01/timeline.json")
    r = read_json("snapshots/s3_lowriver_2026-10-01/risk.json")
    t["budget_used"] = 1.01
    decision = decide(s, t, r)
    assert decision["recommended"] == "QUARANTINE"
    assert decision["requires_approval_by"] == "QA"


def test_stock_shortage_rejects_buffer_and_blocked_expedite():
    s = read_json("snapshots/s3_lowriver_2026-10-01/scenario.json")
    s["site"]["stock_batches"] = 0
    risk = analyze(s, 8)
    assert not risk["per_action"]["BUFFER"]["eligible"]
    assert not risk["per_action"]["EXPEDITE"]["eligible"]
