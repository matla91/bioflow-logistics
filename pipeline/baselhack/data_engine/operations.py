"""Seeded operational schedules and thermal histories, not ML training rows."""

from collections import defaultdict
from datetime import datetime, timedelta

import numpy as np

from baselhack.interfaces import (
    OperationalDataset,
    OperationalShipment,
    ShipmentReading,
)
from baselhack.simulator.thermal import advance


def generate(settings: dict) -> OperationalDataset:
    reference = datetime.fromisoformat(settings["reference_at"])
    if reference.utcoffset() is None:
        raise ValueError("Reference time must be timezone-aware")
    if settings["shipments"] < 4 or settings["batches"] < 2:
        raise ValueError(
            "Generate at least four shipments and two batches for the demo cases"
        )
    if settings["reading_interval_min"] <= 0 or settings["batch_spacing_hours"] <= 0:
        raise ValueError("Reading and batch intervals must be positive")
    prefix = settings["dataset_id"]
    random = np.random.default_rng(settings["seed"])
    material_id = f"{prefix}-material"
    shipments, readings = [], []
    for index in range(settings["shipments"]):
        scenario = ("normal", "heat", "delay", "planned")[index % 4]
        offset = settings["departure_offsets_hours"][
            0 if scenario == "normal" else 2 if scenario == "planned" else 1
        ]
        departure = reference + timedelta(hours=offset)
        planned_arrival = departure + timedelta(hours=settings["route_duration_hours"])
        arrival = planned_arrival + timedelta(
            hours=settings["delay_hours"] if scenario == "delay" else 0
        )
        actual_departure = departure if departure <= reference else None
        actual_arrival = arrival if actual_departure and arrival <= reference else None
        shipment = OperationalShipment(
            id=f"{prefix}-shipment-{index + 1:03d}",
            material_id=material_id,
            lot_id=f"{prefix}-lot-{index + 1:03d}",
            quantity_kg=settings["shipment_quantity_kg"],
            route_mode="river",
            origin=settings["origin"],
            destination=settings["destination"],
            planned_departure_at=departure,
            planned_arrival_at=planned_arrival,
            actual_departure_at=actual_departure,
            actual_arrival_at=actual_arrival,
            status="arrived"
            if actual_arrival
            else "in_transit"
            if actual_departure
            else "planned",
            scenario=scenario,
        )
        shipments.append(shipment)
        if actual_departure:
            ambient = (
                settings["heat_ambient_c"]
                if scenario == "heat"
                else settings["normal_ambient_c"]
            )
            # Seeded initial variation, followed by the existing exact thermal law.
            temperature = round(
                settings["setpoint_c"] + float(random.uniform(-0.2, 0.2)), 6
            )
            excursion = 0.0
            at, end = departure, min(reference, arrival)
            exposure_start = arrival - timedelta(
                hours=settings["heat_exposure_final_hours"]
                if scenario == "heat"
                else settings["exposure_final_hours"]
            )
            while True:
                refrigerated = at < exposure_start
                readings.append(
                    ShipmentReading(
                        shipment_id=shipment.id,
                        at=at,
                        product_c=round(temperature, 6),
                        ambient_c=ambient,
                        refrigerated=refrigerated,
                        excursion_min=round(excursion, 6),
                    )
                )
                if at == end:
                    break
                next_at = min(
                    at + timedelta(minutes=settings["reading_interval_min"]), end
                )
                if at < exposure_start < next_at:
                    next_at = exposure_start
                target = settings["setpoint_c"] if refrigerated else ambient
                tau = (
                    settings["tau_reefer_min"]
                    if refrigerated
                    else settings["tau_exposed_min"]
                )
                temperature, outside = advance(
                    temperature,
                    target,
                    (next_at - at).total_seconds() / 60,
                    tau,
                    settings["range_c"],
                )
                excursion += outside
                at = next_at
    batches, supply, reservations = [], [], []
    stock_id = f"{prefix}-stock-released"
    remaining_stock = settings["released_stock_kg"]
    for index in range(settings["batches"]):
        batch_id = f"{prefix}-batch-{index + 1:03d}"
        charge = reference + timedelta(
            hours=settings["batch_first_offset_hours"]
            + index * settings["batch_spacing_hours"]
        )
        batches.append(
            {
                "id": batch_id,
                "reactor": settings["reactors"][index % len(settings["reactors"])],
                "material_id": material_id,
                "required_quantity_kg": settings["batch_quantity_kg"],
                "planned_charge_at": charge,
                "status": "waiting_material" if charge < reference else "planned",
            }
        )
        supply.append(
            {
                "batch_id": batch_id,
                "shipment_id": shipments[index % len(shipments)].id,
                "quantity_kg": settings["batch_quantity_kg"],
            }
        )
        quantity = min(remaining_stock, settings["batch_quantity_kg"])
        if quantity > 0:
            reservations.append(
                {
                    "batch_id": batch_id,
                    "inventory_lot_id": stock_id,
                    "quantity_kg": quantity,
                }
            )
            remaining_stock -= quantity
    inventory = [
        {
            "id": stock_id,
            "material_id": material_id,
            "quantity_kg": settings["released_stock_kg"],
            "available_at": reference - timedelta(days=7),
            "qa_status": "released",
        },
        {
            "id": f"{prefix}-stock-pending",
            "material_id": material_id,
            "quantity_kg": settings["pending_stock_kg"],
            "available_at": reference - timedelta(days=1),
            "qa_status": "pending",
        },
    ]
    inventory.extend(
        {
            "id": shipment.lot_id,
            "material_id": material_id,
            "quantity_kg": shipment.quantity_kg,
            "available_at": shipment.actual_arrival_at,
            "qa_status": "pending",
            "shipment_id": shipment.id,
        }
        for shipment in shipments
        if shipment.actual_arrival_at
    )
    dataset = OperationalDataset(
        dataset_id=prefix,
        seed=settings["seed"],
        reference_at=reference,
        materials=[
            {
                "id": material_id,
                "name": settings["material_name"],
                "quantity_unit": settings["quantity_unit"],
                "range_c": settings["range_c"],
                "budget_min": settings["budget_min"],
            }
        ],
        shipments=shipments,
        batches=batches,
        supply_plans=supply,
        inventory=inventory,
        reservations=reservations,
        readings=readings,
        assumptions=settings,
    )
    validate_operations(dataset)
    return dataset


def validate_operations(dataset: OperationalDataset):
    """Validate cross-record quantities, identities, QA gates and causal timestamps."""

    def index(records):
        values = {record.id: record for record in records}
        if len(values) != len(records):
            raise ValueError("Duplicate operational IDs")
        return values

    materials = index(dataset.materials)
    shipments = index(dataset.shipments)
    batches = index(dataset.batches)
    lots = index(dataset.inventory)
    for item in [*shipments.values(), *batches.values(), *lots.values()]:
        if item.material_id not in materials:
            raise ValueError("Unknown material reference")
    for shipment in shipments.values():
        if any(
            at and at > dataset.reference_at
            for at in (shipment.actual_departure_at, shipment.actual_arrival_at)
        ):
            raise ValueError("Actual shipment milestones cannot be in the future")
    for lot in lots.values():
        if lot.available_at > dataset.reference_at:
            raise ValueError("On-site inventory cannot arrive in the future")
        if lot.shipment_id:
            shipment = shipments[lot.shipment_id]
            if (
                lot.material_id != shipment.material_id
                or lot.id != shipment.lot_id
                or lot.quantity_kg > shipment.quantity_kg
                or shipment.actual_arrival_at is None
                or lot.available_at < shipment.actual_arrival_at
            ):
                raise ValueError(
                    "Incoming inventory must match an arrived shipment lot"
                )
    planned = defaultdict(float)
    batch_supply = defaultdict(float)
    for plan in dataset.supply_plans:
        batch, shipment = batches[plan.batch_id], shipments[plan.shipment_id]
        if batch.material_id != shipment.material_id:
            raise ValueError("Batch and shipment materials differ")
        planned[shipment.id] += plan.quantity_kg
        batch_supply[batch.id] += plan.quantity_kg
    if any(quantity > shipments[key].quantity_kg for key, quantity in planned.items()):
        raise ValueError("Planned supply exceeds shipment quantity")
    if any(
        quantity > batches[key].required_quantity_kg
        for key, quantity in batch_supply.items()
    ):
        raise ValueError("Planned supply exceeds batch requirement")
    reserved = defaultdict(float)
    batch_reserved = defaultdict(float)
    for reservation in dataset.reservations:
        batch, lot = batches[reservation.batch_id], lots[reservation.inventory_lot_id]
        if lot.qa_status != "released" or lot.available_at > min(
            dataset.reference_at, batch.planned_charge_at
        ):
            raise ValueError(
                "Reserved stock must be released and available at the batch deadline"
            )
        if batch.material_id != lot.material_id:
            raise ValueError("Batch and stock materials differ")
        reserved[lot.id] += reservation.quantity_kg
        batch_reserved[batch.id] += reservation.quantity_kg
    if any(quantity > lots[key].quantity_kg for key, quantity in reserved.items()):
        raise ValueError("Stock is reserved more than once beyond availability")
    if any(
        quantity > batches[key].required_quantity_kg
        for key, quantity in batch_reserved.items()
    ):
        raise ValueError("Reservation exceeds batch requirement")
    for reading in dataset.readings:
        shipment = shipments[reading.shipment_id]
        if (
            shipment.actual_departure_at is None
            or not shipment.actual_departure_at <= reading.at <= dataset.reference_at
        ):
            raise ValueError(
                "Readings require actual departure and cannot be in the future"
            )
        if shipment.actual_arrival_at and reading.at > shipment.actual_arrival_at:
            raise ValueError("Shipment reading follows recorded arrival")
