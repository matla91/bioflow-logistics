from datetime import datetime, timedelta, timezone

import numpy as np

from baselhack.interfaces import Action

from .reactor import readiness
from .river import barge_factor
from .thermal import advance
from .traffic import traffic_factor

WEATHER_CACHE = {}


def prepared_weather(ambient):
    key = id(ambient)
    cached = WEATHER_CACHE.get(key)
    if cached is not None and cached[0] is ambient:
        return cached[1]
    tables = {
        place: {
            datetime.fromisoformat(p["t"]).astimezone(timezone.utc): p["c"]
            for p in points
        }
        for place, points in ambient.items()
    }
    if len(WEATHER_CACHE) >= 32:
        WEATHER_CACHE.clear()
    WEATHER_CACHE[key] = (ambient, tables)
    return tables


def ambient_at(scenario, place, at, hourly=None):
    hour = at.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
    values = (
        hourly
        if hourly is not None
        else {
            datetime.fromisoformat(p["t"]).astimezone(timezone.utc): p["c"]
            for p in scenario["ambient"][place]
        }
    )
    if hour not in values:
        raise ValueError(
            f"TODO(verify): missing exact UTC hour for {place}: {hour.isoformat()}"
        )
    return values[hour] + scenario["overrides"].get("ambient_offset_c", 0)


def sample_duration(segment, rng):
    kind = segment["distribution"]
    if kind == "normal":
        return max(1.0, float(rng.normal(segment["planned_min"], segment["sd_min"])))
    if kind == "triangular":
        return float(rng.triangular(*segment["triangular_min"]))
    return float(segment["planned_min"])


def simulate(scenario, seed, action=Action.RUN_AS_PLANNED, record=True):
    rng = np.random.default_rng(seed)
    at = datetime.fromisoformat(scenario["start_at"]).astimezone(timezone.utc)
    hourly = prepared_weather(scenario["ambient"])
    ready = readiness(scenario, rng)
    material = scenario["material"]
    temp = float(material["setpoint_c"])
    excursion = 0.0
    steps = []
    status = "arrived"
    thresholds = scenario["thresholds"]
    for original in scenario["route"]:
        segment = dict(original)
        duration = scenario["overrides"].get(
            segment["id"] + "_min", sample_duration(segment, rng)
        )
        if segment["id"] == "sea":
            # Historical sea portion ends at scenario start, held at assumed reefer setpoint.
            at -= timedelta(minutes=duration)
        if action == Action.EXPEDITE and segment["kind"] == "handover":
            duration *= thresholds["expedite_wait_factor"]
        if segment["id"] == "barge":
            if action == Action.REROUTE:
                segment["id"] = "reroute_truck"
                duration = max(
                    1.0,
                    float(
                        rng.normal(
                            thresholds["reroute_truck_min"],
                            thresholds["reroute_truck_sd_min"],
                        )
                    ),
                )
                # Extra exposed handover at Rotterdam, then refrigerated truck.
                target = ambient_at(scenario, "rotterdam", at, hourly["rotterdam"])
                extra = thresholds["reroute_extra_handover_min"]
                temp, outside = advance(
                    temp,
                    target,
                    extra,
                    material["tau_exposed_min"],
                    material["range_c"],
                )
                excursion += outside
                at += timedelta(minutes=extra)
                if record:
                    steps.append(
                        {
                            "t": at.isoformat(),
                            "segment": "reroute_transfer",
                            "position": segment["position"],
                            "refrigerated": False,
                            "ambient_c": target,
                            "product_c": round(temp, 6),
                            "excursion_min": round(excursion, 6),
                            "budget_used": round(excursion / material["budget_min"], 6),
                            "source": "simulator + cached Rotterdam temperature; ASSUMED reroute handover",
                        }
                    )
            else:
                factor = barge_factor(scenario, at)
                if factor is None:
                    status = "suspended"
                    break
                duration *= factor
        if segment["id"] == "unload_basel" and scenario.get("basel_unload_at"):
            appointment = datetime.fromisoformat(
                scenario["basel_unload_at"]
            ).astimezone(timezone.utc)
            wait = max(0.0, (appointment - at).total_seconds() / 60)
            temp, outside = advance(
                temp,
                material["setpoint_c"],
                wait,
                material["tau_reefer_min"],
                material["range_c"],
            )
            excursion += outside
            at += timedelta(minutes=wait)
            if record and wait:
                steps.append(
                    {
                        "t": at.isoformat(),
                        "segment": "port_cold_wait",
                        "position": segment["position"],
                        "refrigerated": True,
                        "ambient_c": material["setpoint_c"],
                        "product_c": round(temp, 6),
                        "excursion_min": round(excursion, 6),
                        "budget_used": round(excursion / material["budget_min"], 6),
                        "source": "ASSUMED refrigerated port appointment wait in scenario YAML",
                    }
                )
        if segment["id"] == "truck_to_site":
            duration *= traffic_factor(scenario, at)
        if segment["id"] == "dock":
            duration += scenario["overrides"].get("dock_extra_min", 0)
            duration *= traffic_factor(scenario, at)
        if action == Action.EXPEDITE and segment["id"] in (
            "truck_to_site",
            "truck_to_barge",
        ):
            duration += thresholds["expedite_truck_slot_wait_min"]
        remaining = duration
        while remaining > 1e-8:
            dt = min(
                remaining,
                (60 if segment["id"] == "sea" else 5)
                if record or not segment["refrigerated"]
                else remaining,
            )
            if not segment["refrigerated"]:
                next_hour = at.replace(minute=0, second=0, microsecond=0) + timedelta(
                    hours=1
                )
                dt = min(dt, (next_hour - at).total_seconds() / 60)
            target = (
                material["setpoint_c"]
                if segment["refrigerated"]
                else ambient_at(
                    scenario, segment["place"], at, hourly[segment["place"]]
                )
            )
            tau = (
                material["tau_reefer_min"]
                if segment["refrigerated"]
                else material["tau_exposed_min"]
            )
            temp, outside = advance(temp, target, dt, tau, material["range_c"])
            excursion += outside
            at += timedelta(minutes=dt)
            remaining -= dt
            if record:
                steps.append(
                    {
                        "t": at.isoformat(),
                        "segment": segment["id"],
                        "position": segment["position"],
                        "refrigerated": segment["refrigerated"],
                        "ambient_c": target,
                        "product_c": round(temp, 6),
                        "excursion_min": round(excursion, 6),
                        "budget_used": round(excursion / material["budget_min"], 6),
                        "source": "simulator; ASSUMED reefer setpoint"
                        if segment["refrigerated"]
                        else f"simulator + {scenario['sources'][segment['place']]}",
                    }
                )
    eta = at if status == "arrived" else None
    if eta and not material["range_c"][0] <= temp <= material["range_c"][1]:
        remaining = material["recovery_horizon_min"]
        while (
            remaining > 0
            and not material["range_c"][0] <= temp <= material["range_c"][1]
        ):
            dt = min(5.0, remaining)
            temp, outside = advance(
                temp,
                material["setpoint_c"],
                dt,
                material["tau_reefer_min"],
                material["range_c"],
            )
            excursion += outside
            at += timedelta(minutes=dt)
            remaining -= dt
            if record:
                steps.append(
                    {
                        "t": at.isoformat(),
                        "segment": "cold_store_recovery",
                        "position": scenario["route"][-1]["position"],
                        "refrigerated": True,
                        "ambient_c": material["setpoint_c"],
                        "product_c": round(temp, 6),
                        "excursion_min": round(excursion, 6),
                        "budget_used": round(excursion / material["budget_min"], 6),
                        "source": "simulator; ASSUMED cold-store setpoint and tau; recovery still consumes excursion",
                    }
                )
    delay = (
        max(0.0, (eta - ready).total_seconds() / 60)
        if eta
        else thresholds["suspension_delay_min"]
    )
    stock = scenario["site"]["stock_batches"]
    required = scenario["site"]["batch_stock_required"]
    if action in (Action.BUFFER, Action.QUARANTINE):
        delay = 0.0 if stock >= required else thresholds["suspension_delay_min"]
        if stock >= required:
            stock -= required
    return {
        "scenario_id": scenario["scenario_id"],
        "seed": seed,
        "action": str(action),
        "steps": steps,
        "eta": eta.isoformat() if eta else None,
        "readiness_at": ready.isoformat(),
        "excursion_min": round(excursion, 6),
        "budget_used": round(excursion / material["budget_min"], 6),
        "status": status,
        "stock_after": stock,
        "batch_delay_min": delay,
        "sources": {
            "simulation": "seeded numpy journey; config/route.yaml + config/material.yaml + config/site.yaml",
            "ambient": "cached real observations; overrides are explicitly simulated",
            "delay_cap": "ASSUMED config/thresholds.yaml suspension_delay_min",
        },
    }
