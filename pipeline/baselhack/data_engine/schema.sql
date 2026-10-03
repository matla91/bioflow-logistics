-- Provisional integration schema v1; reconcile with Laravel migrations before use.
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS data_engine_schema (
    version INTEGER PRIMARY KEY CHECK (version = 1)
);
INSERT OR IGNORE INTO data_engine_schema VALUES (1);
CREATE TABLE IF NOT EXISTS logistics_assessments (
    assessment_id TEXT PRIMARY KEY,
    scenario TEXT NOT NULL,
    as_of TEXT NOT NULL,
    stored_at TEXT NOT NULL,
    payload_json TEXT NOT NULL CHECK (json_valid(payload_json)),
    evidence_json TEXT NOT NULL CHECK (json_valid(evidence_json))
);
CREATE TRIGGER IF NOT EXISTS immutable_logistics_assessments_update
BEFORE UPDATE ON logistics_assessments BEGIN
    SELECT RAISE(ABORT, 'Assessment evidence is immutable');
END;
CREATE TRIGGER IF NOT EXISTS immutable_logistics_assessments_delete
BEFORE DELETE ON logistics_assessments BEGIN
    SELECT RAISE(ABORT, 'Assessment evidence is immutable');
END;
CREATE TABLE IF NOT EXISTS ingestion_runs (
    id TEXT PRIMARY KEY,
    stream TEXT NOT NULL,
    requested_start TEXT NOT NULL,
    requested_end TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL CHECK (status IN ('running','success','partial','failed','no_data')),
    records_received INTEGER NOT NULL DEFAULT 0,
    records_added INTEGER NOT NULL DEFAULT 0,
    error TEXT
);
CREATE INDEX IF NOT EXISTS ingestion_stream_time ON ingestion_runs(stream, requested_end);
CREATE TABLE IF NOT EXISTS observation_sources (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    dataset TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    source_json TEXT NOT NULL CHECK (json_valid(source_json))
);
CREATE TABLE IF NOT EXISTS external_observations (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('traffic','rhine','weather')),
    station_id TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    observation_json TEXT NOT NULL CHECK (json_valid(observation_json))
);
CREATE INDEX IF NOT EXISTS external_observation_lookup ON external_observations(kind, station_id, observed_at);
CREATE TABLE IF NOT EXISTS observation_receipts (
    observation_id TEXT NOT NULL REFERENCES external_observations(id),
    source_id TEXT NOT NULL REFERENCES observation_sources(id),
    run_id TEXT NOT NULL REFERENCES ingestion_runs(id),
    PRIMARY KEY (observation_id, source_id, run_id)
);
CREATE TABLE IF NOT EXISTS operational_datasets (
    id TEXT PRIMARY KEY,
    seed INTEGER NOT NULL,
    reference_at TEXT NOT NULL,
    dataset_sha256 TEXT NOT NULL,
    dataset_json TEXT NOT NULL CHECK (json_valid(dataset_json)),
    simulated INTEGER NOT NULL CHECK (simulated = 1)
);
CREATE TABLE IF NOT EXISTS materials (
    id TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL REFERENCES operational_datasets(id),
    name TEXT NOT NULL,
    quantity_unit TEXT NOT NULL CHECK (quantity_unit = 'kg'),
    min_temp_c REAL NOT NULL,
    max_temp_c REAL NOT NULL,
    budget_min REAL NOT NULL CHECK (budget_min > 0)
);
CREATE TABLE IF NOT EXISTS shipments (
    id TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL REFERENCES operational_datasets(id),
    material_id TEXT NOT NULL REFERENCES materials(id),
    lot_id TEXT NOT NULL UNIQUE,
    quantity_kg REAL NOT NULL CHECK (quantity_kg > 0),
    status TEXT NOT NULL,
    planned_departure_at TEXT NOT NULL,
    planned_arrival_at TEXT NOT NULL,
    actual_departure_at TEXT,
    actual_arrival_at TEXT,
    shipment_json TEXT NOT NULL CHECK (json_valid(shipment_json)),
    simulated INTEGER NOT NULL CHECK (simulated = 1)
);
CREATE TABLE IF NOT EXISTS batches (
    id TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL REFERENCES operational_datasets(id),
    reactor TEXT NOT NULL,
    material_id TEXT NOT NULL REFERENCES materials(id),
    required_quantity_kg REAL NOT NULL CHECK (required_quantity_kg > 0),
    planned_charge_at TEXT NOT NULL,
    status TEXT NOT NULL,
    simulated INTEGER NOT NULL CHECK (simulated = 1)
);
CREATE TABLE IF NOT EXISTS batch_supply_plans (
    batch_id TEXT NOT NULL REFERENCES batches(id),
    shipment_id TEXT NOT NULL REFERENCES shipments(id),
    quantity_kg REAL NOT NULL CHECK (quantity_kg > 0),
    PRIMARY KEY (batch_id, shipment_id)
);
CREATE TABLE IF NOT EXISTS inventory_lots (
    id TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL REFERENCES operational_datasets(id),
    material_id TEXT NOT NULL REFERENCES materials(id),
    quantity_kg REAL NOT NULL CHECK (quantity_kg >= 0),
    available_at TEXT NOT NULL,
    qa_status TEXT NOT NULL CHECK (qa_status IN ('released','pending','quarantined')),
    shipment_id TEXT REFERENCES shipments(id),
    simulated INTEGER NOT NULL CHECK (simulated = 1)
);
CREATE TABLE IF NOT EXISTS stock_reservations (
    batch_id TEXT NOT NULL REFERENCES batches(id),
    inventory_lot_id TEXT NOT NULL REFERENCES inventory_lots(id),
    quantity_kg REAL NOT NULL CHECK (quantity_kg > 0),
    PRIMARY KEY (batch_id, inventory_lot_id)
);
CREATE TABLE IF NOT EXISTS shipment_readings (
    shipment_id TEXT NOT NULL REFERENCES shipments(id),
    observed_at TEXT NOT NULL,
    product_c REAL NOT NULL,
    ambient_c REAL NOT NULL,
    refrigerated INTEGER NOT NULL CHECK (refrigerated IN (0,1)),
    excursion_min REAL NOT NULL CHECK (excursion_min >= 0),
    simulated INTEGER NOT NULL CHECK (simulated = 1),
    PRIMARY KEY (shipment_id, observed_at)
);
CREATE VIEW IF NOT EXISTS available_inventory AS
SELECT lots.id, lots.material_id, lots.dataset_id, lots.qa_status, lots.available_at,
       lots.quantity_kg,
       COALESCE(SUM(reservations.quantity_kg), 0) AS reserved_quantity_kg,
       lots.quantity_kg - COALESCE(SUM(reservations.quantity_kg), 0) AS unreserved_quantity_kg
FROM inventory_lots AS lots
LEFT JOIN stock_reservations AS reservations ON reservations.inventory_lot_id = lots.id
GROUP BY lots.id;

CREATE TRIGGER IF NOT EXISTS reservation_insert_guard
BEFORE INSERT ON stock_reservations
BEGIN
    SELECT CASE WHEN
        (SELECT qa_status FROM inventory_lots WHERE id=NEW.inventory_lot_id) != 'released'
        OR (SELECT available_at FROM inventory_lots WHERE id=NEW.inventory_lot_id) > (SELECT planned_charge_at FROM batches WHERE id=NEW.batch_id)
        OR (SELECT material_id FROM inventory_lots WHERE id=NEW.inventory_lot_id) != (SELECT material_id FROM batches WHERE id=NEW.batch_id)
        OR NEW.quantity_kg + COALESCE((SELECT SUM(quantity_kg) FROM stock_reservations WHERE inventory_lot_id=NEW.inventory_lot_id),0) > (SELECT quantity_kg FROM inventory_lots WHERE id=NEW.inventory_lot_id)
        OR NEW.quantity_kg + COALESCE((SELECT SUM(quantity_kg) FROM stock_reservations WHERE batch_id=NEW.batch_id),0) > (SELECT required_quantity_kg FROM batches WHERE id=NEW.batch_id)
        THEN RAISE(ABORT, 'Stock reservation exceeds available released material or batch demand') END;
END;
CREATE TRIGGER IF NOT EXISTS reservation_update_guard
BEFORE UPDATE ON stock_reservations
BEGIN
    SELECT CASE WHEN
        (SELECT qa_status FROM inventory_lots WHERE id=NEW.inventory_lot_id) != 'released'
        OR (SELECT available_at FROM inventory_lots WHERE id=NEW.inventory_lot_id) > (SELECT planned_charge_at FROM batches WHERE id=NEW.batch_id)
        OR (SELECT material_id FROM inventory_lots WHERE id=NEW.inventory_lot_id) != (SELECT material_id FROM batches WHERE id=NEW.batch_id)
        OR NEW.quantity_kg + COALESCE((SELECT SUM(quantity_kg) FROM stock_reservations WHERE inventory_lot_id=NEW.inventory_lot_id AND NOT (batch_id=OLD.batch_id AND inventory_lot_id=OLD.inventory_lot_id)),0) > (SELECT quantity_kg FROM inventory_lots WHERE id=NEW.inventory_lot_id)
        OR NEW.quantity_kg + COALESCE((SELECT SUM(quantity_kg) FROM stock_reservations WHERE batch_id=NEW.batch_id AND NOT (batch_id=OLD.batch_id AND inventory_lot_id=OLD.inventory_lot_id)),0) > (SELECT required_quantity_kg FROM batches WHERE id=NEW.batch_id)
        THEN RAISE(ABORT, 'Stock reservation exceeds available released material or batch demand') END;
END;

-- Additive batch integration storage. Operational fixture tables retain v1.
CREATE TABLE IF NOT EXISTS batch_analysis_profiles (
    profile_id TEXT PRIMARY KEY,
    stored_at TEXT NOT NULL,
    payload_json TEXT NOT NULL CHECK (json_valid(payload_json))
);
CREATE TRIGGER IF NOT EXISTS immutable_batch_analysis_profiles_replace
BEFORE INSERT ON batch_analysis_profiles
WHEN EXISTS (SELECT 1 FROM batch_analysis_profiles WHERE profile_id=NEW.profile_id) BEGIN
    SELECT RAISE(ABORT, 'Batch analysis profile is immutable');
END;
CREATE TRIGGER IF NOT EXISTS immutable_batch_analysis_profiles_update
BEFORE UPDATE ON batch_analysis_profiles BEGIN
    SELECT RAISE(ABORT, 'Batch analysis profile is immutable');
END;
CREATE TRIGGER IF NOT EXISTS immutable_batch_analysis_profiles_delete
BEFORE DELETE ON batch_analysis_profiles BEGIN
    SELECT RAISE(ABORT, 'Batch analysis profile is immutable');
END;
CREATE TABLE IF NOT EXISTS batch_assessments (
    assessment_id TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL REFERENCES operational_datasets(id),
    batch_id TEXT NOT NULL REFERENCES batches(id),
    as_of TEXT NOT NULL,
    stored_at TEXT NOT NULL,
    payload_json TEXT NOT NULL CHECK (json_valid(payload_json)),
    evidence_json TEXT NOT NULL CHECK (json_valid(evidence_json))
);
CREATE INDEX IF NOT EXISTS batch_assessment_lookup
ON batch_assessments(dataset_id, batch_id, as_of DESC, stored_at DESC, assessment_id DESC);
CREATE TRIGGER IF NOT EXISTS batch_assessment_dataset_guard
BEFORE INSERT ON batch_assessments
WHEN (SELECT dataset_id FROM batches WHERE id=NEW.batch_id) != NEW.dataset_id BEGIN
    SELECT RAISE(ABORT, 'Assessment batch belongs to a different dataset');
END;
CREATE TRIGGER IF NOT EXISTS immutable_batch_assessments_replace
BEFORE INSERT ON batch_assessments
WHEN EXISTS (SELECT 1 FROM batch_assessments WHERE assessment_id=NEW.assessment_id) BEGIN
    SELECT RAISE(ABORT, 'Batch assessment evidence is immutable');
END;
CREATE TRIGGER IF NOT EXISTS immutable_batch_assessments_update
BEFORE UPDATE ON batch_assessments BEGIN
    SELECT RAISE(ABORT, 'Batch assessment evidence is immutable');
END;
CREATE TRIGGER IF NOT EXISTS immutable_batch_assessments_delete
BEFORE DELETE ON batch_assessments BEGIN
    SELECT RAISE(ABORT, 'Batch assessment evidence is immutable');
END;
