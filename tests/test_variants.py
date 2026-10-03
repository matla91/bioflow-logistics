from baselhack.storage import ROOT, read_json


def test_offline_controls_preserve_real_observations():
    for config in (ROOT / "scenarios").glob("*.yaml"):
        scene = config.stem
        baseline = read_json(f"snapshots/{scene}/scenario.json")
        controls = read_json(f"snapshots/{scene}/variants.json")
        assert {"ambient", "ambient-cold", "handover", "river", "drift", "stock"} <= {
            c["id"] for c in controls
        }
        for control in controls:
            assert control["ready"], control.get("error")
            variant = read_json(
                f"snapshots/{scene}/variants/{control['id']}/scenario.json"
            )
            assert variant["ambient"] == baseline["ambient"]
            assert variant["rhine"] == baseline["rhine"]
            assert "ASSUMED" in control["source"]
            risk = read_json(f"snapshots/{scene}/variants/{control['id']}/risk.json")
            assert risk["n_runs"] == baseline["thresholds"]["monte_carlo_runs"]


def test_early_heat_unload_avoids_quarantine_under_configured_model():
    scene = "s2_heat_2026-07-30"
    baseline = read_json(f"snapshots/{scene}/risk.json")
    early = read_json(f"snapshots/{scene}/variants/early-unload/risk.json")
    decision = read_json(f"snapshots/{scene}/variants/early-unload/decision.json")
    assert early["p_excursion"] < baseline["p_excursion"]
    assert decision["recommended"] == "RUN_AS_PLANNED"
