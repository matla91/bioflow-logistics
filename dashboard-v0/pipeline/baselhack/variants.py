"""Precompute independent bounded demo controls, preserving real observations."""

from copy import deepcopy
from datetime import datetime, timedelta

from baselhack.explain import explain
from baselhack.ml.decision_analysis import analyze
from baselhack.rules.engine import decide
from baselhack.simulator.journey import simulate
from baselhack.storage import ROOT, read_json, read_yaml, save


def compute_variant(scene, variant, scenario):
    location = f"{scene}/variants/{variant}"
    scenario["sources"]["control"] = (
        "ASSUMED config/demo_variants.yaml precomputed sensitivity; real observations unchanged"
    )
    save("scenario", location, scenario)
    timeline = save("timeline", location, simulate(scenario, scenario["seed"]))
    risk = save("risk", location, analyze(scenario))
    decision = decide(scenario, timeline, risk)
    decision["explanation"] = explain(decision)
    save("decision", location, decision)
    return decision


def generate(scene):
    baseline = read_json(f"snapshots/{scene}/scenario.json")
    config = read_yaml("config/demo_variants.yaml")
    manifest = []
    for control in config["controls"]:
        scenario = deepcopy(baseline)
        value = control["value"]
        if control.get("field"):
            # For the short low-water snapshot, a different still-suspended sensitivity
            # value avoids extrapolating future weather outside verified cache coverage.
            if baseline["simulated_kaub_cm"] is None:
                value = config["lowriver_sensitivity_cm"]
            scenario[control["field"]] = value
            scenario["sources"]["simulated_kaub_cm"] = (
                "ASSUMED config/demo_variants.yaml simulated river sensitivity; not a measurement"
            )
        elif control.get("site_field"):
            scenario["site"][control["site_field"]] = value
        else:
            scenario["overrides"][control["override"]] = value
        entry = {
            "id": control["id"],
            "label": control["label"],
            "value": value,
            "unit": control["unit"],
        }
        try:
            decision = compute_variant(scene, control["id"], scenario)
            entry["recommended"] = decision["recommended"]
            entry["ready"] = True
        except ValueError as error:
            entry["ready"] = False
            entry["error"] = str(error)
        manifest.append(entry)
        print(
            f"{scene}/{control['id']}: {entry.get('recommended', entry.get('error'))}",
            flush=True,
        )
    if baseline.get("basel_unload_at"):
        scenario = deepcopy(baseline)
        shift = timedelta(hours=config["early_unload_shift_hours"])
        scenario["start_at"] = (
            datetime.fromisoformat(scenario["start_at"]) + shift
        ).isoformat()
        scenario["basel_unload_at"] = (
            datetime.fromisoformat(scenario["basel_unload_at"]) + shift
        ).isoformat()
        decision = compute_variant(scene, "early-unload", scenario)
        manifest.append(
            {
                "id": "early-unload",
                "label": "Unload before 10:00 Basel",
                "value": config["early_unload_shift_hours"],
                "unit": "hour shift",
                "recommended": decision["recommended"],
                "ready": True,
            }
        )
    for entry in manifest:
        entry["source"] = "ASSUMED config/demo_variants.yaml"
    save("variants", scene, manifest)


if __name__ == "__main__":
    for scene in sorted((ROOT / "scenarios").glob("*.yaml")):
        generate(scene.stem)
