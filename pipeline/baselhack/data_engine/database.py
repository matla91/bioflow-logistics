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
    ObservationSource,
    OperationalDataset,
    RealObservations,
    RhineObservation,
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
