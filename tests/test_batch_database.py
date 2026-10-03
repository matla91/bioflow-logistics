"""Cutoff-safe normalized joins and immutable batch evidence persistence."""

import json
import sqlite3
from datetime import timedelta

import pytest
from baselhack.data_engine.database import Database, digest, utc
from baselhack.data_engine.operations import generate
from baselhack.interfaces import BatchAnalysisProfile, StoredBatchAssessment
from baselhack.logistics import load_demo
from baselhack.storage import read_yaml


@pytest.fixture
def operations(tmp_path):
    database = Database(tmp_path / "batch.sqlite3")
    database.initialize()
    dataset = generate(read_yaml("config/operations_demo.yaml"))
    database.store_operations(dataset)
    return database, dataset


def snapshot(operations, as_of=None):
    database, dataset = operations
    return database.batch_snapshot(
        dataset.dataset_id, dataset.batches[0].id, as_of or dataset.reference_at
    )


def test_normalized_snapshot_ignores_generator_labels_and_dataset_json(operations):
    database, dataset = operations
    original = snapshot(operations)
    with database.connect() as connection:
        shipment = connection.execute(
            "SELECT shipment_json FROM shipments WHERE id=?",
            (dataset.shipments[0].id,),
        ).fetchone()
        payload = json.loads(shipment[0])
        payload.update(scenario="heat", quantity_kg=9999)
        connection.execute(
            "UPDATE shipments SET shipment_json=? WHERE id=?",
            (json.dumps(payload), dataset.shipments[0].id),
        )
        connection.execute("UPDATE operational_datasets SET dataset_json='{}'")
    current = snapshot(operations)
    assert current == original
    assert "scenario" not in current.shipments[0].model_dump()
    assert len(current.reservations) == len(dataset.reservations)
    assert {lot.id for lot in current.inventory} == {
        lot.id for lot in dataset.inventory
    }


def test_cutoff_removes_future_milestones_readings_and_incoming_lots(operations):
    _, dataset = operations
    shipment = dataset.shipments[0]
    before_departure = snapshot(
        operations, shipment.actual_departure_at - timedelta(minutes=1)
    )
    assert before_departure.shipments[0].actual_departure_at is None
    assert before_departure.shipments[0].actual_arrival_at is None
    assert before_departure.shipments[0].readings == []
    assert not any(lot.shipment_id for lot in before_departure.inventory)
    during = snapshot(operations, shipment.actual_departure_at + timedelta(minutes=45))
    assert during.shipments[0].actual_arrival_at is None
    assert len(during.shipments[0].readings) == 2
    assert all(reading.at <= during.as_of for reading in during.shipments[0].readings)
    assert not any(lot.shipment_id for lot in during.inventory)


def test_mutable_batch_plan_cannot_exceed_batch_demand(operations):
    database, dataset = operations
    with database.connect() as connection:
        connection.execute(
            "UPDATE batch_supply_plans SET quantity_kg=? WHERE batch_id=?",
            (dataset.batches[0].required_quantity_kg + 1, dataset.batches[0].id),
        )
    with pytest.raises(ValueError, match="batch requirement"):
        snapshot(operations)


def test_competing_plans_cannot_exceed_shipment_quantity(operations):
    database, dataset = operations
    with database.connect() as connection:
        connection.execute(
            "UPDATE shipments SET quantity_kg=99 WHERE id=?",
            (dataset.shipments[0].id,),
        )
    with pytest.raises(ValueError, match="shipment quantity"):
        snapshot(operations)


@pytest.mark.parametrize("field", ["material_id", "dataset_id"])
def test_competing_plan_matches_material_and_dataset(operations, field):
    database, dataset = operations
    other = generate(
        {**read_yaml("config/operations_demo.yaml"), "dataset_id": "other"}
    )
    database.store_operations(other)
    replacement = other.materials[0].id if field == "material_id" else other.dataset_id
    with database.connect() as connection:
        connection.execute(
            f"UPDATE batches SET {field}=? WHERE id=?",
            (replacement, dataset.batches[12].id),
        )
    with pytest.raises(ValueError, match="Competing supply plan"):
        snapshot(operations)


@pytest.mark.parametrize("actual", [False, True])
def test_normalized_shipment_milestones_are_chronological(operations, actual):
    database, dataset = operations
    field = "actual_arrival_at" if actual else "planned_arrival_at"
    arrival = (
        dataset.shipments[0].actual_departure_at - timedelta(minutes=1)
        if actual
        else dataset.shipments[0].planned_departure_at
    )
    with database.connect() as connection:
        connection.execute(
            f"UPDATE shipments SET {field}=? WHERE id=?",
            (utc(arrival), dataset.shipments[0].id),
        )
    with pytest.raises(ValueError, match="departure"):
        snapshot(operations)


@pytest.mark.parametrize("field", ["quantity_kg", "available_at"])
def test_normalized_incoming_lot_matches_arrived_quantity_and_time(operations, field):
    database, dataset = operations
    shipment = dataset.shipments[0]
    value = (
        shipment.quantity_kg + 1
        if field == "quantity_kg"
        else utc(shipment.actual_arrival_at - timedelta(minutes=1))
    )
    with database.connect() as connection:
        connection.execute(
            f"UPDATE inventory_lots SET {field}=? WHERE id=?",
            (value, shipment.lot_id),
        )
    with pytest.raises(ValueError, match="Incoming inventory"):
        snapshot(operations)


@pytest.fixture
def profile():
    _, _, assumptions = load_demo("normal")
    return BatchAnalysisProfile(profile_id="database-test-v1", logistics=assumptions)


def test_named_profile_is_immutable_and_idempotent(operations, profile):
    database, _ = operations
    assert database.store_batch_profile(profile)
    assert not database.store_batch_profile(profile)
    assert database.batch_profile(profile.profile_id) == profile
    with pytest.raises(ValueError, match="different inputs"):
        database.store_batch_profile(profile.model_copy(update={"handling_min": 1}))
    with pytest.raises(ValueError, match="not found"):
        database.batch_profile("missing")
    with database.connect() as connection:
        for sql in (
            "UPDATE batch_analysis_profiles SET payload_json='{}'",
            "DELETE FROM batch_analysis_profiles",
            "INSERT OR REPLACE INTO batch_analysis_profiles SELECT * FROM batch_analysis_profiles",
        ):
            with pytest.raises(sqlite3.IntegrityError, match="immutable"):
                connection.execute(sql)


def record_and_evidence(operations, profile):
    selected = snapshot(operations)
    inputs = {"operations": selected.model_dump(mode="json"), "test_model": "v1"}
    body = {
        "dataset_id": selected.dataset_id,
        "batch_id": selected.batch.id,
        "shipment_ids": [shipment.id for shipment in selected.shipments],
        "as_of": selected.as_of,
        "known_at": None,
        "input_sha256": digest(inputs),
        "model_version": "persistence-test-v1",
        "production_readiness": {
            "planned_charge_at": selected.batch.planned_charge_at,
            "required_quantity_kg": 50,
            "released_reserved_quantity_kg": 0,
            "reservation_shortfall_kg": 50,
            "incoming_dependency_kg": 50,
            "uncovered_quantity_kg": 0,
            "status": "INCOMING_DEPENDENT",
            "stock_evidence": [],
        },
        "incoming_shipments": [],
        "product_temperature": [],
        "recommendation": {
            "action": None,
            "reason": "Persistence-only record",
            "requires_approval_by": "operator",
            "qa_review_required": False,
            "alternatives": [],
        },
        "provenance": [],
        "real_data_sources": [],
        "assumptions": profile,
        "limitations": ["Persistence-only test"],
    }
    record = StoredBatchAssessment(assessment_id="a" * 64, **body)
    return record, {"inputs": inputs}


def test_assessment_digest_collision_and_sql_immutability(operations, profile):
    database, dataset = operations
    record, evidence = record_and_evidence(operations, profile)
    assert database.store_batch_assessment(record, evidence)
    assert not database.store_batch_assessment(record, evidence)
    assert database.batch_assessment(record.assessment_id) == record
    assert database.batch_assessment("missing") is None
    assert database.batch_assessments(dataset.dataset_id, record.batch_id) == [record]
    assert database.batch_assessments(as_of=record.as_of - timedelta(seconds=1)) == []
    with pytest.raises(ValueError, match="input digest"):
        database.store_batch_assessment(record, {"inputs": {"tampered": True}})
    with pytest.raises(ValueError, match="different content"):
        database.store_batch_assessment(
            record.model_copy(update={"limitations": ["changed"]}), evidence
        )
    with pytest.raises(ValueError, match="different content"):
        database.store_batch_assessment(record, {**evidence, "extra": "changed"})
    with database.connect() as connection:
        stored = connection.execute(
            "SELECT evidence_json FROM batch_assessments"
        ).fetchone()
        assert digest(json.loads(stored[0])["inputs"]) == record.input_sha256
        for sql in (
            "UPDATE batch_assessments SET payload_json='{}'",
            "DELETE FROM batch_assessments",
            "INSERT OR REPLACE INTO batch_assessments SELECT * FROM batch_assessments",
        ):
            with pytest.raises(sqlite3.IntegrityError, match="immutable"):
                connection.execute(sql)
