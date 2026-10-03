"""Linked batch test snapshots with hidden outcomes and leakage-safe input features."""

import argparse
import csv
import hashlib
import io
import json
import zipfile
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

from baselhack.data_engine.operations import validate_operations
from baselhack.interfaces import OperationalDataset
from baselhack.simulator.thermal import advance
from baselhack.storage import ROOT, canonical, read_yaml

FAMILIES = (
    "released_stock",
    "late_arrival",
    "thermal_excursion",
    "future_planned",
    "partial_supply",
    "stock_competition",
    "pending_qa",
    "quarantined_stock",
    "split_delivery",
    "missing_readings",
    "stale_readings",
    "stock_supply_overlap",
)
MATERIALS = ((2, 8, 120), (15, 25, 90), (-20, -10, 60))


def build_group(settings, index):
    """One independent shared-resource group; never split its two batches."""
    rng = np.random.default_rng(np.random.SeedSequence([settings["seed"], index]))
    prefix = f"{settings['dataset_id']}-g{index:04d}"
    cutoff = datetime.fromisoformat(settings["first_cutoff"]) + timedelta(days=index)
    if cutoff.utcoffset() is None:
        raise ValueError("Cutoff must be timezone-aware")
    family = FAMILIES[index % len(FAMILIES)]
    low, high, budget = MATERIALS[int(rng.integers(len(MATERIALS)))]
    material_id = prefix + "-material"
    demand = float(rng.choice([25, 40, 50, 75, 100]))
    deadline = cutoff + timedelta(hours=float(rng.uniform(2, 16)))
    batches = [
        {
            "id": f"{prefix}-b{n}",
            "reactor": f"R{n + 1}",
            "material_id": material_id,
            "required_quantity_kg": demand,
            "planned_charge_at": deadline + timedelta(hours=2 * n),
            "status": "planned",
        }
        for n in range(2)
    ]
    shipments, readings, plans, inventory, reservations, truth = [], [], [], [], [], []
    stock = (
        2 * demand
        if family == "released_stock"
        else 1.2 * demand
        if family == "stock_supply_overlap"
        else demand
        if family in {"stock_competition", "pending_qa", "quarantined_stock"}
        else 0.0
    )
    stock_state = (
        "pending"
        if family == "pending_qa"
        else "quarantined"
        if family == "quarantined_stock"
        else "released"
    )
    stock_id = prefix + "-stock"
    if stock > 0:
        inventory.append(
            {
                "id": stock_id,
                "material_id": material_id,
                "quantity_kg": stock,
                "available_at": cutoff - timedelta(days=2),
                "qa_status": stock_state,
            }
        )
    if family in {"released_stock", "stock_supply_overlap"}:
        reservations = [
            {
                "batch_id": b["id"],
                "inventory_lot_id": stock_id,
                "quantity_kg": demand if family == "released_stock" else 0.6 * demand,
            }
            for b in batches
        ]
    elif family == "stock_competition":
        reservations = [
            {
                "batch_id": batches[0]["id"],
                "inventory_lot_id": stock_id,
                "quantity_kg": demand,
            }
        ]
    count = 2 if family == "split_delivery" else 1
    for n in range(count):
        shipment_id = f"{prefix}-s{n}"
        planned = cutoff + timedelta(hours=float(rng.uniform(1, 6)))
        departure = cutoff - timedelta(hours=float(rng.uniform(12, 24)))
        actual = planned + timedelta(hours=float(rng.uniform(-2, 2)))
        if (
            family in {"late_arrival", "stock_competition"}
            or family == "split_delivery"
            and n == 1
        ):
            actual = deadline + timedelta(hours=float(rng.uniform(5, 20)))
        if family in {
            "released_stock",
            "pending_qa",
            "quarantined_stock",
            "stock_supply_overlap",
        }:
            actual = cutoff - timedelta(hours=float(rng.uniform(1, 5)))
        if family == "future_planned":
            departure = cutoff + timedelta(hours=2)
            planned = departure + timedelta(hours=float(rng.uniform(12, 24)))
            actual = planned + timedelta(hours=float(rng.uniform(-1, 8)))
        arrived = actual <= cutoff
        quantity = demand * (
            0.5
            if count == 2
            else 0.6
            if family in {"partial_supply", "stock_supply_overlap"}
            else 1
        )
        lot_id = stock_id if family == "stock_supply_overlap" else f"{prefix}-lot{n}"
        shipments.append(
            {
                "id": shipment_id,
                "material_id": material_id,
                "lot_id": lot_id,
                "quantity_kg": 2 * quantity,
                "route_mode": "road" if index % 2 else "river",
                "origin": "Synthetic origin",
                "destination": "Synthetic production site",
                "planned_departure_at": departure,
                "planned_arrival_at": planned,
                "actual_departure_at": departure if departure <= cutoff else None,
                "actual_arrival_at": actual if arrived else None,
                "status": "arrived"
                if arrived
                else "in_transit"
                if departure <= cutoff
                else "planned",
                "scenario": "planned"
                if family == "future_planned"
                else "heat"
                if family == "thermal_excursion"
                else "delay"
                if actual > deadline
                else "normal",
            }
        )
        plans.extend(
            {"batch_id": b["id"], "shipment_id": shipment_id, "quantity_kg": quantity}
            for b in batches
        )
        if arrived:
            if family == "stock_supply_overlap":
                inventory[0].update(shipment_id=shipment_id, available_at=actual)
            else:
                inventory.append(
                    {
                        "id": lot_id,
                        "material_id": material_id,
                        "quantity_kg": 2 * quantity,
                        "available_at": actual,
                        "qa_status": "quarantined"
                        if family == "quarantined_stock"
                        else "pending",
                        "shipment_id": shipment_id,
                    }
                )
        temperature = (low + high) / 2 + float(rng.uniform(-0.5, 0.5))
        excursion = 0.0
        at = departure
        # Full future thermal history is computed only for the separate truth labels.
        while at <= actual:
            hot = family == "thermal_excursion"
            ambient = high + float(rng.uniform(12, 22)) if hot else (low + high) / 2
            if (
                departure <= cutoff
                and at <= cutoff
                and family != "missing_readings"
                and not (
                    family == "stale_readings" and at > cutoff - timedelta(hours=6)
                )
            ):
                readings.append(
                    {
                        "shipment_id": shipment_id,
                        "at": at,
                        "product_c": round(temperature, 6),
                        "ambient_c": round(ambient, 6),
                        "refrigerated": not hot,
                        "excursion_min": round(excursion, 6),
                    }
                )
            if at == actual:
                break
            next_at = min(
                at + timedelta(minutes=settings["reading_interval_min"]), actual
            )
            temperature, outside = advance(
                temperature,
                ambient,
                (next_at - at).total_seconds() / 60,
                360,
                (low, high),
            )
            excursion += outside
            at = next_at
        truth.append(
            {
                "shipment_id": shipment_id,
                "actual_arrival_at": actual,
                "qa_release_at": None
                if family in {"pending_qa", "quarantined_stock"} or excursion > budget
                else actual
                if family == "stock_supply_overlap"
                else actual + timedelta(hours=float(rng.uniform(0.5, 3))),
                "final_excursion_min": round(excursion, 6),
                "quantity_kg": quantity,
            }
        )
    dataset = OperationalDataset(
        dataset_id=prefix,
        seed=settings["seed"],
        reference_at=cutoff,
        materials=[
            {
                "id": material_id,
                "name": f"Synthetic material {low} to {high} C",
                "range_c": (low, high),
                "budget_min": budget,
            }
        ],
        batches=batches,
        shipments=shipments,
        supply_plans=plans,
        inventory=inventory,
        reservations=reservations,
        readings=readings,
        assumptions={
            "synthetic": True,
            "thermal_tau_min": 360,
            "reading_interval_min": settings["reading_interval_min"],
        },
    )
    validate_operations(dataset)
    split = (
        "train"
        if index < int(settings["groups"] * settings["train_fraction"])
        else "validation"
        if index
        < int(
            settings["groups"]
            * (settings["train_fraction"] + settings["validation_fraction"])
        )
        else "test"
    )
    features, labels, metadata = [], [], []
    for b in dataset.batches:
        reserved = sum(
            r.quantity_kg for r in dataset.reservations if r.batch_id == b.id
        )
        # Reservations and incoming supply are alternative coverage: the overlap
        # case references the same physical lot, so adding both would be incorrect.
        usable_incoming = sum(
            t["quantity_kg"]
            for t in truth
            if t["qa_release_at"] is not None
            and t["qa_release_at"] <= b.planned_charge_at
            and t["final_excursion_min"] <= budget
        )
        coverage = (
            max(reserved, usable_incoming)
            if family == "stock_supply_overlap"
            else min(demand, reserved + usable_incoming)
        )
        relevant = dataset.readings
        # Staleness is assessed at the cutoff while still moving, and at arrival
        # for a completed shipment; arrival does not make a complete history stale.
        latest_age = (
            max(
                (
                    min(cutoff, s.actual_arrival_at or cutoff)
                    - max(r.at for r in relevant if r.shipment_id == s.id)
                ).total_seconds()
                / 60
                for s in dataset.shipments
            )
            if relevant
            else None
        )
        observed_excursion = max((r.excursion_min for r in relevant), default=None)
        evidence_status = (
            "unknown"
            if not relevant or latest_age > settings["stale_after_min"]
            else "exceeded_budget"
            if observed_excursion > budget
            else "within_observed_budget"
        )
        features.append(
            {
                "batch_id": b.id,
                "required_quantity_kg": demand,
                "hours_to_charge": (b.planned_charge_at - cutoff).total_seconds()
                / 3600,
                "material_low_c": low,
                "material_high_c": high,
                "excursion_budget_min": budget,
                "reserved_released_kg": reserved,
                "unreserved_released_kg": stock
                - sum(r.quantity_kg for r in dataset.reservations)
                if stock_state == "released"
                else 0,
                "pending_stock_kg": sum(
                    l.quantity_kg for l in dataset.inventory if l.qa_status == "pending"
                ),
                "quarantined_stock_kg": sum(
                    l.quantity_kg
                    for l in dataset.inventory
                    if l.qa_status == "quarantined"
                ),
                "planned_incoming_kg": sum(
                    p.quantity_kg for p in dataset.supply_plans if p.batch_id == b.id
                ),
                "shipment_count": len(dataset.shipments),
                "planned_shipments": sum(
                    s.status == "planned" for s in dataset.shipments
                ),
                "arrived_shipments": sum(
                    s.status == "arrived" for s in dataset.shipments
                ),
                "planned_latest_arrival_hours": max(
                    (s.planned_arrival_at - cutoff).total_seconds() / 3600
                    for s in dataset.shipments
                ),
                "reading_count": len(relevant),
                "latest_reading_age_min": latest_age,
                "observed_excursion_min": observed_excursion,
            }
        )
        labels.append(
            {
                "batch_id": b.id,
                "split": split,
                "synthetic_ready_by_deadline": int(coverage >= demand - 1e-6),
                "incoming_all_on_time": int(
                    all(t["actual_arrival_at"] <= b.planned_charge_at for t in truth)
                ),
                "synthetic_final_excursion_exceeded": int(
                    any(t["final_excursion_min"] > budget for t in truth)
                ),
                "temperature_evidence_status": evidence_status,
                "released_reservation_shortfall_kg": max(0, demand - reserved),
                "synthetic_usable_coverage_kg": round(coverage, 6),
            }
        )
        metadata.append(
            {
                "batch_id": b.id,
                "group_id": prefix,
                "cutoff": cutoff.isoformat(),
                "split": split,
                "scenario_family": family,
            }
        )
    return dataset, features, labels, metadata, truth


def encode_csv(records):
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(records[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(
        {
            key: round(value, 6) if isinstance(value, float) else value
            for key, value in row.items()
        }
        for row in records
    )
    return buffer.getvalue()


def export(settings, destination):
    if (
        settings["groups"] < 12
        or settings["reading_interval_min"] <= 0
        or not 0
        < settings["train_fraction"]
        < settings["train_fraction"] + settings["validation_fraction"]
        < 1
    ):
        raise ValueError(
            "Need at least 12 groups, a positive cadence and valid split fractions"
        )
    snapshots, features, labels, metadata, outcomes = [], [], [], [], []
    counts = Counter()
    for index in range(settings["groups"]):
        dataset, f, l, m, truth = build_group(settings, index)
        snapshots.append(canonical(dataset.model_dump(mode="json")))
        features.extend(f)
        labels.extend(l)
        metadata.extend(m)
        outcomes.append(
            canonical(
                {
                    "group_id": dataset.dataset_id,
                    "shipments": [
                        {
                            **t,
                            "actual_arrival_at": t["actual_arrival_at"].isoformat(),
                            "qa_release_at": t["qa_release_at"].isoformat()
                            if t["qa_release_at"]
                            else None,
                        }
                        for t in truth
                    ],
                }
            )
        )
        counts.update(
            shipments=len(dataset.shipments),
            readings=len(dataset.readings),
            batches=len(dataset.batches),
        )
    destination.mkdir(parents=True, exist_ok=True)
    contents = {
        "snapshots.jsonl": "\n".join(snapshots) + "\n",
        "features.csv": encode_csv(features),
        "labels.csv": encode_csv(labels),
        "case_index.csv": encode_csv(metadata),
        "hidden_outcomes.jsonl": "\n".join(outcomes) + "\n",
    }
    templates = Path(__file__).with_name("ml_fixture_templates")
    for name in ("README.md", "quickstart.py"):
        contents[name] = (templates / name).read_text(encoding="utf-8")
    manifest = {
        "dataset_id": settings["dataset_id"],
        "simulated": True,
        "seed": settings["seed"],
        "generation_settings": settings,
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "groups": settings["groups"],
        "counts": dict(counts),
        "splits": dict(Counter(m["split"] for m in metadata)),
        "families": dict(Counter(m["scenario_family"] for m in metadata)),
        "labels": {
            key: dict(Counter(str(l[key]) for l in labels))
            for key in [
                "synthetic_ready_by_deadline",
                "incoming_all_on_time",
                "synthetic_final_excursion_exceeded",
                "temperature_evidence_status",
            ]
        },
        "feature_columns": [key for key in features[0] if key != "batch_id"],
        "files": {
            name: {"sha256": hashlib.sha256(value.encode()).hexdigest()}
            for name, value in contents.items()
        },
    }
    contents["manifest.json"] = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    for name, value in contents.items():
        (destination / name).write_text(value, encoding="utf-8")
    # Fixed zip metadata makes the delivery artifact reproducible too.
    with zipfile.ZipFile(
        destination.with_suffix(".zip"), "w", compression=zipfile.ZIP_DEFLATED
    ) as archive:
        for name, value in sorted(contents.items()):
            entry = zipfile.ZipInfo(name, date_time=(2026, 10, 3, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, value.encode())
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--settings", default="config/ml_batch_tests.yaml")
    parser.add_argument("--output", type=Path, default=ROOT / "data/ml/batch-tests-v1")
    args = parser.parse_args(argv)
    manifest = export(read_yaml(args.settings), args.output)
    print(
        json.dumps(
            {
                k: manifest[k]
                for k in ["dataset_id", "groups", "counts", "splits", "labels"]
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
