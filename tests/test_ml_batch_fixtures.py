import csv
import hashlib
import json
import zipfile

from baselhack.data_engine.ml_fixtures import FAMILIES, build_group, export
from baselhack.data_engine.operations import validate_operations
from baselhack.interfaces import OperationalDataset
from baselhack.storage import read_yaml


def test_group_snapshots_are_causal_and_conserve_material():
    settings = read_yaml("config/ml_batch_tests.yaml")
    for index in range(60):
        dataset, features, labels, metadata, truth = build_group(settings, index)
        validate_operations(dataset)
        assert len(features) == len(labels) == len(metadata) == 2
        assert all(r.at <= dataset.reference_at for r in dataset.readings)
        for shipment in dataset.shipments:
            if shipment.status == "planned":
                assert (
                    shipment.actual_departure_at is shipment.actual_arrival_at is None
                )
                assert not any(r.shipment_id == shipment.id for r in dataset.readings)
            if shipment.actual_arrival_at:
                assert shipment.actual_arrival_at <= dataset.reference_at
        assert all(
            label["synthetic_usable_coverage_kg"] <= batch.required_quantity_kg
            for label, batch in zip(labels, dataset.batches, strict=True)
        )
        assert {t["shipment_id"] for t in truth} == {s.id for s in dataset.shipments}


def test_expected_stock_and_evidence_cases():
    settings = read_yaml("config/ml_batch_tests.yaml")
    cases = {name: build_group(settings, index) for index, name in enumerate(FAMILIES)}
    assert [l["synthetic_ready_by_deadline"] for l in cases["released_stock"][2]] == [
        1,
        1,
    ]
    assert [
        l["synthetic_ready_by_deadline"] for l in cases["stock_competition"][2]
    ] == [1, 0]
    for name in (
        "pending_qa",
        "quarantined_stock",
        "stock_supply_overlap",
        "partial_supply",
    ):
        assert [l["synthetic_ready_by_deadline"] for l in cases[name][2]] == [0, 0]
    for name in ("future_planned", "missing_readings", "stale_readings"):
        assert all(
            l["temperature_evidence_status"] == "unknown" for l in cases[name][2]
        )
    assert all(
        l["synthetic_final_excursion_exceeded"] == 1
        for l in cases["thermal_excursion"][2]
    )
    assert all(l["incoming_all_on_time"] == 0 for l in cases["late_arrival"][2])
    # All planned incoming quantity plus a partial same-lot reservation would
    # misleadingly imply readiness if added. The physical lot only covers 60%.
    _dataset, features, labels, *_ = cases["stock_supply_overlap"]
    for feature, label in zip(features, labels, strict=True):
        assert (
            feature["planned_incoming_kg"] + feature["reserved_released_kg"]
            > feature["required_quantity_kg"]
        )
        assert label["synthetic_usable_coverage_kg"] < feature["required_quantity_kg"]
    assert len(cases["split_delivery"][0].shipments) == 2


def test_exports_are_reproducible_and_splits_have_no_shared_resources(tmp_path):
    settings = {**read_yaml("config/ml_batch_tests.yaml"), "groups": 60}
    destination = tmp_path / "batch-data"
    manifest = export(settings, destination)
    first = destination.with_suffix(".zip").read_bytes()
    assert export(settings, destination) == manifest
    assert destination.with_suffix(".zip").read_bytes() == first
    with zipfile.ZipFile(destination.with_suffix(".zip")) as archive:
        assert archive.testzip() is None
        for name, info in manifest["files"].items():
            assert hashlib.sha256(archive.read(name)).hexdigest() == info["sha256"]
    rows = list(csv.DictReader((destination / "case_index.csv").open()))
    groups = {}
    dates = {split: [] for split in ("train", "validation", "test")}
    for row in rows:
        assert groups.setdefault(row["group_id"], row["split"]) == row["split"]
        dates[row["split"]].append(row["cutoff"])
    assert max(dates["train"]) < min(dates["validation"])
    assert max(dates["validation"]) < min(dates["test"])
    assert "scenario_family" not in manifest["feature_columns"]
    assert not set(manifest["labels"]) & set(manifest["feature_columns"])
    resources = set()
    for line in (destination / "snapshots.jsonl").read_text().splitlines():
        dataset = OperationalDataset.model_validate_json(line)
        ids = {r.id for r in dataset.shipments + dataset.batches + dataset.inventory}
        assert not ids & resources
        resources.update(ids)
    assert json.loads((destination / "manifest.json").read_text()) == manifest
