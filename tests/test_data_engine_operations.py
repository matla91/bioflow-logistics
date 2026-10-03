"""Reproducible synthetic schedules, heat exposure and stock competition."""

from datetime import timedelta

import pytest
from baselhack.data_engine.operations import generate, validate_operations
from baselhack.interfaces import OperationalDataset
from baselhack.storage import read_yaml


@pytest.fixture
def dataset():
    return generate(read_yaml("config/operations_demo.yaml"))


def test_generation_is_deterministic_and_schema_valid(dataset):
    again = generate(read_yaml("config/operations_demo.yaml"))
    assert dataset.model_dump_json() == again.model_dump_json()
    assert OperationalDataset.model_validate_json(dataset.model_dump_json()) == dataset
    assert len(dataset.shipments) == 12
    assert len(dataset.batches) == 18
    assert any(
        batch.planned_charge_at > dataset.reference_at for batch in dataset.batches
    )
    assert any(
        shipment.planned_departure_at > dataset.reference_at
        for shipment in dataset.shipments
    )


def test_planned_shipments_have_no_future_sensor_readings_or_actuals(dataset):
    planned = {
        shipment.id for shipment in dataset.shipments if shipment.status == "planned"
    }
    assert planned
    assert not any(reading.shipment_id in planned for reading in dataset.readings)
    assert all(reading.at <= dataset.reference_at for reading in dataset.readings)
    assert all(
        shipment.actual_departure_at is None
        for shipment in dataset.shipments
        if shipment.id in planned
    )


def test_heat_has_visible_thermal_history_and_delay_has_not_arrived(dataset):
    heat = {
        shipment.id for shipment in dataset.shipments if shipment.scenario == "heat"
    }
    assert any(
        reading.product_c > 8 and reading.excursion_min > 0
        for reading in dataset.readings
        if reading.shipment_id in heat
    )
    assert all(
        shipment.actual_arrival_at is None
        for shipment in dataset.shipments
        if shipment.scenario == "delay"
    )


def test_stock_competition_and_pending_qa_inventory(dataset):
    assert [r.quantity_kg for r in dataset.reservations] == [50, 30]
    assert sum(r.quantity_kg for r in dataset.reservations) == 80
    pending = {lot.id for lot in dataset.inventory if lot.qa_status == "pending"}
    assert pending
    assert not any(
        reservation.inventory_lot_id in pending for reservation in dataset.reservations
    )
    dataset.reservations[1].quantity_kg = 50
    with pytest.raises(ValueError, match="beyond availability"):
        validate_operations(dataset)


def test_future_reading_and_qa_reservation_rejected(dataset):
    dataset.readings[0].at = dataset.reference_at + timedelta(hours=1)
    with pytest.raises(ValueError, match="future"):
        validate_operations(dataset)
    dataset = generate(read_yaml("config/operations_demo.yaml"))
    dataset.reservations[0].inventory_lot_id = next(
        lot.id for lot in dataset.inventory if lot.qa_status == "pending"
    )
    with pytest.raises(ValueError, match="released"):
        validate_operations(dataset)


def test_supply_quantity_and_material_matching(dataset):
    dataset.supply_plans[0].quantity_kg = 1000
    with pytest.raises(ValueError, match="shipment quantity"):
        validate_operations(dataset)
