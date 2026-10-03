"""Short SQLite transactions for immutable observation revisions and operations."""

import hashlib
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from baselhack.interfaces import (
    BatchAnalysisProfile,
    BatchOperationalSnapshot,
    BatchShipmentSnapshot,
    BatchSupplyPlan,
    InventoryLot,
    ObservationSource,
    OperationalDataset,
    OperationalMaterial,
    ProductionBatch,
    RealObservations,
    RhineObservation,
    ShipmentReading,
    StockReservation,
    StoredBatchAssessment,
    TrafficObservation,
    WeatherObservation,
)
from baselhack.storage import canonical

OBSERVATION_MODELS = {
    "traffic": TrafficObservation,
    "rhine": RhineObservation,
    "weather": WeatherObservation,
}


def utc(value: datetime) -> str:
    if value.utcoffset() is None:
        raise ValueError("Timestamps require an explicit UTC offset")
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds")


def digest(value) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    @contextmanager
    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=5000")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self):
        with self.connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript(Path(__file__).with_name("schema.sql").read_text())

    @contextmanager
    def collector_lock(self):
        """One CLI collector per DB; the OS releases this lock on process exit."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.with_suffix(self.path.suffix + ".ingest.lock").open(
            "a+b"
        ) as lock:
            if os.name == "nt":
                import msvcrt

                if lock.tell() == 0:
                    lock.write(b"0")
                    lock.flush()
                lock.seek(0)

                def acquire():
                    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)

                def release():
                    lock.seek(0)
                    msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                def acquire():
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)

                def release():
                    fcntl.flock(lock, fcntl.LOCK_UN)

            try:
                acquire()
            except OSError as error:
                raise RuntimeError(
                    "Another collector is already using this database"
                ) from error
            try:
                yield
            finally:
                release()

    def start_run(self, stream, start, end):
        run_id = uuid.uuid4().hex
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO ingestion_runs(id,stream,requested_start,requested_end,"
                "started_at,status) VALUES (?,?,?,?,?,'running')",
                (run_id, stream, utc(start), utc(end), utc(datetime.now(timezone.utc))),
            )
        return run_id

    def finish_run(self, run_id, status, received, added, error=None):
        with self.connect() as connection:
            connection.execute(
                "UPDATE ingestion_runs SET finished_at=?,status=?,records_received=?,"
                "records_added=?,error=? WHERE id=?",
                (
                    utc(datetime.now(timezone.utc)),
                    status,
                    received,
                    added,
                    error,
                    run_id,
                ),
            )

    def checkpoint(self, stream):
        with self.connect() as connection:
            row = connection.execute(
                "SELECT MAX(requested_end) AS cutoff FROM ingestion_runs "
                "WHERE stream=? AND status='success'",
                (stream,),
            ).fetchone()
        return datetime.fromisoformat(row["cutoff"]) if row["cutoff"] else None

    def store_observations(self, kind, observations, source, run_id):
        source = ObservationSource.model_validate(source)
        source_data = source.model_dump(mode="json")
        source_data["retrieved_at"] = utc(source.retrieved_at)
        source_id = digest(source_data)
        prepared = []
        for item in observations:
            item = OBSERVATION_MODELS[kind].model_validate(item)
            payload = item.model_dump(mode="json")
            for key, value in item.model_dump().items():
                if isinstance(value, datetime):
                    payload[key] = utc(value)
            observed_at = item.interval_end if kind == "traffic" else item.t
            identity = [kind, source.provider, source.dataset, payload]
            prepared.append(
                (
                    digest(identity),
                    kind,
                    item.station_id,
                    utc(observed_at),
                    canonical(payload),
                )
            )
        added = 0
        with self.connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO observation_sources VALUES (?,?,?,?,?)",
                (
                    source_id,
                    source.provider,
                    source.dataset,
                    utc(source.retrieved_at),
                    canonical(source_data),
                ),
            )
            for row in prepared:
                cursor = connection.execute(
                    "INSERT OR IGNORE INTO external_observations VALUES (?,?,?,?,?)",
                    row,
                )
                added += cursor.rowcount
                connection.execute(
                    "INSERT OR IGNORE INTO observation_receipts VALUES (?,?,?)",
                    (row[0], source_id, run_id),
                )
        return added

    def observations(self, as_of: datetime, known_at: datetime | None = None):
        """Latest stored revisions by observation time, optionally as known then."""
        cutoff = utc(as_of)
        knowledge_filter = "AND s.retrieved_at <= ?" if known_at else ""
        params = [cutoff, utc(known_at)] if known_at else [cutoff]
        with self.connect() as connection:
            rows = connection.execute(
                "WITH ranked AS (SELECT o.kind,o.observation_json,s.source_json,"
                "ROW_NUMBER() OVER (PARTITION BY o.kind,o.station_id,o.observed_at "
                "ORDER BY s.retrieved_at DESC,r.rowid DESC) AS rank "
                "FROM external_observations o JOIN observation_receipts r ON r.observation_id=o.id "
                "JOIN observation_sources s ON s.id=r.source_id WHERE o.observed_at <= ? "
                + knowledge_filter
                + ") SELECT kind,observation_json,source_json FROM ranked WHERE rank=1",
                params,
            ).fetchall()
        if not rows:
            raise ValueError("No stored observations available at this cutoff")
        grouped = {kind: [] for kind in OBSERVATION_MODELS}
        sources = {}
        for row in rows:
            grouped[row["kind"]].append(json.loads(row["observation_json"]))
            source = json.loads(row["source_json"])
            sources[digest(source)] = source
        return RealObservations.model_validate(
            {**grouped, "sources": list(sources.values())}
        )

    def store_operations(self, dataset: OperationalDataset):
        from .operations import validate_operations

        dataset = OperationalDataset.model_validate(dataset.model_dump())
        validate_operations(dataset)
        payload = dataset.model_dump(mode="json")
        fingerprint = digest(payload)
        with self.connect() as connection:
            previous = connection.execute(
                "SELECT dataset_sha256 FROM operational_datasets WHERE id=?",
                (dataset.dataset_id,),
            ).fetchone()
            if previous:
                if previous[0] != fingerprint:
                    raise ValueError(
                        "Dataset ID already exists with different inputs; choose a new ID"
                    )
                return False
            connection.execute(
                "INSERT INTO operational_datasets VALUES (?,?,?,?,?,1)",
                (
                    dataset.dataset_id,
                    dataset.seed,
                    utc(dataset.reference_at),
                    fingerprint,
                    canonical(payload),
                ),
            )
            for material in dataset.materials:
                connection.execute(
                    "INSERT INTO materials VALUES (?,?,?,?,?,?,?)",
                    (
                        material.id,
                        dataset.dataset_id,
                        material.name,
                        material.quantity_unit,
                        *material.range_c,
                        material.budget_min,
                    ),
                )
            for shipment in dataset.shipments:
                connection.execute(
                    "INSERT INTO shipments VALUES (?,?,?,?,?,?,?,?,?,?,?,1)",
                    (
                        shipment.id,
                        dataset.dataset_id,
                        shipment.material_id,
                        shipment.lot_id,
                        shipment.quantity_kg,
                        shipment.status,
                        utc(shipment.planned_departure_at),
                        utc(shipment.planned_arrival_at),
                        utc(shipment.actual_departure_at)
                        if shipment.actual_departure_at
                        else None,
                        utc(shipment.actual_arrival_at)
                        if shipment.actual_arrival_at
                        else None,
                        canonical(shipment.model_dump(mode="json")),
                    ),
                )
            for batch in dataset.batches:
                connection.execute(
                    "INSERT INTO batches VALUES (?,?,?,?,?,?,?,1)",
                    (
                        batch.id,
                        dataset.dataset_id,
                        batch.reactor,
                        batch.material_id,
                        batch.required_quantity_kg,
                        utc(batch.planned_charge_at),
                        batch.status,
                    ),
                )
            for lot in dataset.inventory:
                connection.execute(
                    "INSERT INTO inventory_lots VALUES (?,?,?,?,?,?,?,1)",
                    (
                        lot.id,
                        dataset.dataset_id,
                        lot.material_id,
                        lot.quantity_kg,
                        utc(lot.available_at),
                        lot.qa_status,
                        lot.shipment_id,
                    ),
                )
            for plan in dataset.supply_plans:
                connection.execute(
                    "INSERT INTO batch_supply_plans VALUES (?,?,?)",
                    (plan.batch_id, plan.shipment_id, plan.quantity_kg),
                )
            for reservation in dataset.reservations:
                connection.execute(
                    "INSERT INTO stock_reservations VALUES (?,?,?)",
                    (
                        reservation.batch_id,
                        reservation.inventory_lot_id,
                        reservation.quantity_kg,
                    ),
                )
            for reading in dataset.readings:
                connection.execute(
                    "INSERT INTO shipment_readings VALUES (?,?,?,?,?,?,1)",
                    (
                        reading.shipment_id,
                        utc(reading.at),
                        reading.product_c,
                        reading.ambient_c,
                        int(reading.refrigerated),
                        reading.excursion_min,
                    ),
                )
        return True

    def batch_snapshot(self, dataset_id: str, batch_id: str, as_of: datetime):
        """Join current operational rows and trim observed evidence to the cutoff.

        QA and reservation rows have no change history. The dataset reference
        time is retained so the worker can avoid treating them as historical QA.
        """
        cutoff = utc(as_of)
        with self.connect() as connection:
            dataset = connection.execute(
                "SELECT reference_at FROM operational_datasets WHERE id=?",
                (dataset_id,),
            ).fetchone()
            if dataset is None:
                raise ValueError("Operational dataset not found")
            batch = connection.execute(
                "SELECT b.*,m.dataset_id AS material_dataset_id,m.name,"
                "m.quantity_unit,m.min_temp_c,m.max_temp_c,m.budget_min "
                "FROM batches b JOIN materials m ON m.id=b.material_id "
                "WHERE b.id=? AND b.dataset_id=?",
                (batch_id, dataset_id),
            ).fetchone()
            if batch is None:
                raise ValueError("Batch not found in operational dataset")
            if batch["material_dataset_id"] != dataset_id:
                raise ValueError("Batch material belongs to a different dataset")
            plans, shipments = self._batch_supply(connection, batch, cutoff)
            inventory, reservations = self._batch_stock(connection, batch, cutoff)
        return BatchOperationalSnapshot(
            dataset_id=dataset_id,
            reference_at=dataset["reference_at"],
            as_of=cutoff,
            batch=ProductionBatch.model_validate(
                {field: batch[field] for field in ProductionBatch.model_fields}
            ),
            material=OperationalMaterial(
                id=batch["material_id"],
                name=batch["name"],
                quantity_unit=batch["quantity_unit"],
                range_c=(batch["min_temp_c"], batch["max_temp_c"]),
                budget_min=batch["budget_min"],
            ),
            supply_plans=plans,
            shipments=shipments,
            inventory=inventory,
            reservations=reservations,
        )

    @staticmethod
    def _batch_supply(connection, batch, cutoff):
        rows = connection.execute(
            "SELECT p.quantity_kg AS planned_quantity_kg,s.* FROM batch_supply_plans p "
            "JOIN shipments s ON s.id=p.shipment_id WHERE p.batch_id=? ORDER BY s.id",
            (batch["id"],),
        ).fetchall()
        if (
            sum(row["planned_quantity_kg"] for row in rows)
            > batch["required_quantity_kg"]
        ):
            raise ValueError("Planned supply exceeds batch requirement")
        plans, shipments = [], []
        for row in rows:
            if (
                row["dataset_id"] != batch["dataset_id"]
                or row["material_id"] != batch["material_id"]
            ):
                raise ValueError(
                    "Planned shipment must match batch material and dataset"
                )
            Database._validate_shipment_plans(connection, row)
            planned_departure = utc(datetime.fromisoformat(row["planned_departure_at"]))
            planned_arrival = utc(datetime.fromisoformat(row["planned_arrival_at"]))
            if planned_arrival <= planned_departure:
                raise ValueError("Planned shipment arrival must follow departure")
            departure = (
                utc(datetime.fromisoformat(row["actual_departure_at"]))
                if row["actual_departure_at"]
                else None
            )
            arrival = (
                utc(datetime.fromisoformat(row["actual_arrival_at"]))
                if row["actual_arrival_at"]
                else None
            )
            if arrival and (departure is None or arrival < departure):
                raise ValueError("Observed shipment arrival requires prior departure")
            departure = departure if departure and departure <= cutoff else None
            arrival = arrival if arrival and arrival <= cutoff else None
            readings = []
            if departure:
                reading_rows = connection.execute(
                    "SELECT shipment_id,observed_at AS at,product_c,ambient_c,"
                    "refrigerated,excursion_min FROM shipment_readings "
                    "WHERE shipment_id=? AND observed_at>=? AND observed_at<=? "
                    "AND (? IS NULL OR observed_at<=?) ORDER BY observed_at",
                    (row["id"], departure, cutoff, arrival, arrival),
                ).fetchall()
                readings = [
                    ShipmentReading.model_validate(dict(reading))
                    for reading in reading_rows
                ]
            # Route descriptors are immutable attributes held in shipment_json;
            # live quantities and all observed timing come from normalized rows.
            route = json.loads(row["shipment_json"])
            shipments.append(
                BatchShipmentSnapshot(
                    id=row["id"],
                    material_id=row["material_id"],
                    lot_id=row["lot_id"],
                    quantity_kg=row["quantity_kg"],
                    route_mode=route["route_mode"],
                    origin=route["origin"],
                    destination=route["destination"],
                    planned_departure_at=planned_departure,
                    planned_arrival_at=planned_arrival,
                    actual_departure_at=departure,
                    actual_arrival_at=arrival,
                    readings=readings,
                )
            )
            plans.append(
                BatchSupplyPlan(
                    batch_id=batch["id"],
                    shipment_id=row["id"],
                    quantity_kg=row["planned_quantity_kg"],
                )
            )
        return plans, shipments

    @staticmethod
    def _validate_shipment_plans(connection, shipment):
        """Competing demand must not allocate the same incoming quantity twice."""
        linked = connection.execute(
            "SELECT p.quantity_kg,b.dataset_id,b.material_id FROM batch_supply_plans p "
            "JOIN batches b ON b.id=p.batch_id WHERE p.shipment_id=? ORDER BY b.id",
            (shipment["id"],),
        ).fetchall()
        for plan in linked:
            if (
                plan["dataset_id"] != shipment["dataset_id"]
                or plan["material_id"] != shipment["material_id"]
            ):
                raise ValueError(
                    "Competing supply plan must match shipment material and dataset"
                )
        if sum(plan["quantity_kg"] for plan in linked) > shipment["quantity_kg"]:
            raise ValueError("Planned supply exceeds shipment quantity")

    @staticmethod
    def _batch_stock(connection, batch, cutoff):
        rows = connection.execute(
            "SELECT l.*,s.dataset_id AS shipment_dataset_id,"
            "s.material_id AS shipment_material_id,s.lot_id AS shipment_lot_id,"
            "s.quantity_kg AS shipment_quantity_kg,s.actual_arrival_at FROM inventory_lots l "
            "LEFT JOIN shipments s ON s.id=l.shipment_id "
            "WHERE l.dataset_id=? AND l.material_id=? ORDER BY l.id",
            (batch["dataset_id"], batch["material_id"]),
        ).fetchall()
        inventory = []
        for row in rows:
            if row["shipment_id"]:
                if (
                    row["shipment_dataset_id"] != batch["dataset_id"]
                    or row["shipment_material_id"] != batch["material_id"]
                    or row["shipment_lot_id"] != row["id"]
                ):
                    raise ValueError(
                        "Incoming inventory must match shipment and dataset"
                    )
                if row["quantity_kg"] > row["shipment_quantity_kg"]:
                    raise ValueError("Incoming inventory exceeds shipment quantity")
                if row["actual_arrival_at"] and (
                    utc(datetime.fromisoformat(row["available_at"]))
                    < utc(datetime.fromisoformat(row["actual_arrival_at"]))
                ):
                    raise ValueError(
                        "Incoming inventory availability precedes shipment arrival"
                    )
                if not row["actual_arrival_at"] or row["actual_arrival_at"] > cutoff:
                    continue
            inventory.append(
                InventoryLot.model_validate(
                    {field: row[field] for field in InventoryLot.model_fields}
                )
            )
        visible_lots = {lot.id for lot in inventory}
        reservation_rows = connection.execute(
            "SELECT r.*,b.dataset_id AS batch_dataset_id,"
            "b.material_id AS batch_material_id,l.dataset_id AS lot_dataset_id,"
            "l.material_id AS lot_material_id FROM stock_reservations r "
            "JOIN batches b ON b.id=r.batch_id "
            "JOIN inventory_lots l ON l.id=r.inventory_lot_id "
            "WHERE r.batch_id=? OR (l.dataset_id=? AND l.material_id=?) "
            "ORDER BY r.inventory_lot_id,r.batch_id",
            (batch["id"], batch["dataset_id"], batch["material_id"]),
        ).fetchall()
        reservations = []
        for row in reservation_rows:
            if (
                row["batch_dataset_id"] != batch["dataset_id"]
                or row["lot_dataset_id"] != batch["dataset_id"]
                or row["batch_material_id"] != batch["material_id"]
                or row["lot_material_id"] != batch["material_id"]
            ):
                raise ValueError(
                    "Stock reservation must match batch material and dataset"
                )
            if row["inventory_lot_id"] in visible_lots:
                reservations.append(
                    StockReservation.model_validate(
                        {field: row[field] for field in StockReservation.model_fields}
                    )
                )
        return inventory, reservations

    def store_batch_profile(self, profile: BatchAnalysisProfile):
        """Persist one immutable named worker configuration; identical retry is safe."""
        profile = BatchAnalysisProfile.model_validate(profile.model_dump())
        payload = canonical(profile.model_dump(mode="json"))
        with self.connect() as connection:
            previous = connection.execute(
                "SELECT payload_json FROM batch_analysis_profiles WHERE profile_id=?",
                (profile.profile_id,),
            ).fetchone()
            if previous:
                if canonical(json.loads(previous[0])) != payload:
                    raise ValueError("Profile ID already exists with different inputs")
                return False
            connection.execute(
                "INSERT INTO batch_analysis_profiles(profile_id,stored_at,payload_json) "
                "VALUES (?,?,?)",
                (profile.profile_id, utc(datetime.now(timezone.utc)), payload),
            )
        return True

    def batch_profile(self, profile_id: str):
        """Read persisted assumptions, without consulting scenario files."""
        with self.connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM batch_analysis_profiles WHERE profile_id=?",
                (profile_id,),
            ).fetchone()
        if row is None:
            raise ValueError("Batch analysis profile not found")
        return BatchAnalysisProfile.model_validate_json(row[0])

    def store_batch_assessment(self, record: StoredBatchAssessment, evidence: dict):
        """Preserve exact inputs and reject digest mismatches or ID collisions."""
        record = StoredBatchAssessment.model_validate(record.model_dump())
        if (
            "inputs" not in evidence
            or digest(evidence["inputs"]) != record.input_sha256
        ):
            raise ValueError("Assessment input digest does not match stored evidence")
        payload = canonical(record.model_dump(mode="json"))
        evidence_payload = canonical(evidence)
        with self.connect() as connection:
            previous = connection.execute(
                "SELECT payload_json,evidence_json FROM batch_assessments "
                "WHERE assessment_id=?",
                (record.assessment_id,),
            ).fetchone()
            if previous:
                if (
                    canonical(json.loads(previous["payload_json"])) != payload
                    or canonical(json.loads(previous["evidence_json"]))
                    != evidence_payload
                ):
                    raise ValueError(
                        "Assessment ID already exists with different content"
                    )
                return False
            batch = connection.execute(
                "SELECT material_id FROM batches WHERE id=? AND dataset_id=?",
                (record.batch_id, record.dataset_id),
            ).fetchone()
            if batch is None:
                raise ValueError("Assessment batch not found in operational dataset")
            for shipment_id in record.shipment_ids:
                shipment = connection.execute(
                    "SELECT s.material_id FROM shipments s JOIN batch_supply_plans p "
                    "ON p.shipment_id=s.id WHERE p.batch_id=? AND s.id=? AND s.dataset_id=?",
                    (record.batch_id, shipment_id, record.dataset_id),
                ).fetchone()
                if shipment is None or shipment[0] != batch["material_id"]:
                    raise ValueError(
                        "Assessment shipment must belong to batch supply plan"
                    )
            connection.execute(
                "INSERT INTO batch_assessments(assessment_id,dataset_id,batch_id,"
                "as_of,stored_at,payload_json,evidence_json) VALUES (?,?,?,?,?,?,?)",
                (
                    record.assessment_id,
                    record.dataset_id,
                    record.batch_id,
                    utc(record.as_of),
                    utc(datetime.now(timezone.utc)),
                    payload,
                    evidence_payload,
                ),
            )
        return True

    def batch_assessment(self, assessment_id: str):
        """Return one stored immutable assessment, or None when absent."""
        with self.connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM batch_assessments WHERE assessment_id=?",
                (assessment_id,),
            ).fetchone()
        return StoredBatchAssessment.model_validate_json(row[0]) if row else None

    def batch_assessments(self, dataset_id=None, batch_id=None, as_of=None):
        """Read matching records newest first, with deterministic tie breaking."""
        filters, params = [], []
        for field, value in (("dataset_id", dataset_id), ("batch_id", batch_id)):
            if value is not None:
                filters.append(f"{field}=?")
                params.append(value)
        if as_of is not None:
            filters.append("as_of<=?")
            params.append(utc(as_of))
        where = " WHERE " + " AND ".join(filters) if filters else ""
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT payload_json FROM batch_assessments"
                + where
                + " ORDER BY as_of DESC,stored_at DESC,assessment_id DESC",
                params,
            ).fetchall()
        return [StoredBatchAssessment.model_validate_json(row[0]) for row in rows]
