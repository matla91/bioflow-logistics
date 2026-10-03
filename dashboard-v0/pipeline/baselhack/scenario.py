from datetime import datetime, timezone

from baselhack.storage import read_json, read_yaml, save


def build(scene, overrides=None):
    config = read_yaml(f"scenarios/{scene}.yaml")
    if config["scenario_id"] != scene:
        raise ValueError("Scenario id does not match filename")
    evidence = read_json("data/cache/" + config["cache"])
    thresholds = read_yaml("config/thresholds.yaml")
    verification = list(evidence.get("verification", []))
    changes = dict(config["overrides"])
    changes.update(overrides or {})
    value = {
        "scenario_id": scene,
        "seed": config["seed"],
        "start_at": datetime.fromisoformat(config["start_at"])
        .astimezone(timezone.utc)
        .isoformat(),
        "basel_unload_at": config.get("basel_unload_at"),
        "slot": {
            "reactor": read_yaml("config/site.yaml")["reactor"],
            "charge_at": datetime.fromisoformat(config["charge_at"])
            .astimezone(timezone.utc)
            .isoformat(),
        },
        "route": read_yaml("config/route.yaml")["segments"],
        "ambient": evidence["ambient"],
        "rhine": evidence["rhine"],
        "traffic": {"factor_by_hour": evidence.get("traffic", {})},
        "site": read_yaml("config/site.yaml"),
        "material": read_yaml("config/material.yaml"),
        "thresholds": thresholds,
        "overrides": changes,
        "simulated_kaub_cm": config.get("simulated_kaub_cm"),
        "verification": verification,
        "sources": {
            **evidence["sources"],
            "route": "ASSUMED config/route.yaml",
            "material": "ASSUMED config/material.yaml",
            "site": "ASSUMED config/site.yaml",
            "thresholds": "ASSUMED config/thresholds.yaml",
            "overrides": f"ASSUMED scenarios/{scene}.yaml; user controls are simulated",
        },
    }
    if value["simulated_kaub_cm"] is not None:
        value["sources"]["simulated_kaub_cm"] = (
            f"ASSUMED scenarios/{scene}.yaml sensitivity value, not a gauge reading"
        )
    return save("scenario", scene, value)
