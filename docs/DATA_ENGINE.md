# Central data engine

The data engine is the only component that calls weather, Rhine and traffic providers. ML reads stored observations/operations and Laravel reads operations/results and records human decisions. Existing standalone provider-fetch commands remain development utilities; they must not be independently scheduled by the app or ML worker.

This implementation extends `feat/basel-logistics-layer` and reuses its provider adapters. It adds persistence and synthetic operational fixtures. The database is provisional until its table contract is reconciled with the Laravel app's migrations. The engine currently initializes its own version-1 tables; agree one migration owner before integrating Laravel.

## Run locally

Python dependencies are already in the project manifest. No additional package is required.

```sh
pixi run data-init
pixi run data-import-cache
pixi run operations-seed
pixi run data-engine-test
```

This creates the ignored local database `.runtime/current-affairs.sqlite3`, imports the existing real provider cache without network access and writes [operations-demo.json](../output/operations-demo.json). The fixture is reproducible with the same [settings](../config/operations_demo.yaml): 12 shipments, 18 batches, five inventory lots and separate incoming supply plans/stock reservations. Future shipments have planned milestones but no actual departures, arrivals or sensor readings. Heat, delayed transport, insufficient released stock, pending-QA inventory and future demand are explicit synthetic cases. Arrived incoming lots enter pending-QA stock, not automatically released stock.

For live collection:

```sh
pixi run data-ingest
pixi run data-watch
```

`data-watch` runs one ingestion cycle at a time, then waits 60 minutes by default. Stop it with Ctrl-C. A process lock rejects overlapping CLI collectors for the same database and is released by the OS when a process exits. The worker runs independently of browser requests. Collection scheduling is implemented here; scheduling ML analysis and storing analysis/decision records is separate integration work.

The provider window/bootstrap, overlap, retry policy and selected traffic stations are in [config/data_engine.yaml](../config/data_engine.yaml). Default bootstrap is 24 hours, not sufficient to establish multi-week traffic baselines. For earlier weekday/hour history, request an explicit backfill. Basel API requests are chunked to stay within provider limits; MeteoSwiss assets are fetched once for the requested span. Coverage depends on provider availability; ingestion success does not certify complete measurement cadence.

```sh
pixi run python -m baselhack.data_engine ingest --start 2026-09-01T00:00:00+00:00 --end 2026-09-30T12:00:00+00:00
```

Provider failure does not block other streams. Failed/partial/empty runs are recorded and do not advance their stream checkpoint. Valid earlier chunks remain available. Overlapping refreshes deduplicate unchanged values and append revisions rather than overwriting history. Optional missing measurements remain missing; real data is never replaced with synthetic values. A changed traffic-station selection gets its own checkpoint. Raw provider payloads are not archived by this store: it retains validated normalized observations and the adapters' source metadata/checksums.

## Data contracts

Canonical models are in [interfaces.py](../pipeline/baselhack/interfaces.py). `OperationalDataset` is generated into [operational-dataset.schema.json](../schemas/operational-dataset.schema.json) and the existing generated TypeScript file. SQL table/index/trigger definitions are in [schema.sql](../pipeline/baselhack/data_engine/schema.sql).

- `ingestion_runs`, `observation_sources`, `external_observations`, `observation_receipts`: provider runs, provenance, immutable revisions and retrieval history.
- `operational_datasets`, `materials`, `shipments`, `batches`: synthetic fixtures and planned/actual operations.
- `batch_supply_plans`: planned incoming supply, not released-stock reservations.
- `inventory_lots`, `stock_reservations`, `available_inventory`: QA state and quantity conservation. The view exposes reserved/unreserved amounts; consumers also check QA state and availability time.
- `shipment_readings`: synthetic product/ambient histories and cumulative excursion minutes, separated from real external observations.

Quantities use kg, temperatures °C and durations minutes. Database timestamps use UTC with fixed microsecond precision. IDs include the dataset ID. Re-running the same fixture is a no-op. Reusing its ID with different inputs is rejected to preserve evidence; choose a new dataset ID for another fixture.

Reservations cannot exceed released stock or batch requirements. Validation rejects mismatched materials, future actuals/readings and unreleased stock. SQL insert/update guards reject invalid reservation writes. Incoming supply plans are alternatives to stock coverage: do not double-count them as extra demand or physically available stock. This initializer is not yet the production inventory/QA mutation workflow.

## ML reads from stored data

```python
from datetime import datetime
from baselhack.data_engine.database import Database

db = Database(".runtime/current-affairs.sqlite3")
observations = db.observations(datetime.fromisoformat("2026-09-30T12:00:00+00:00"))
# Existing RealObservations contract for the feature builder; no provider calls.
```

`observations(as_of, known_at=None)` excludes measurements after the observation cutoff and chooses latest stored revisions. Supply `known_at` to replay only revisions retrieved by that time; retrospective imports cannot reconstruct knowledge never captured. Exports retain provenance.

For ML consumers expecting JSON:

```sh
pixi run python -m baselhack.data_engine export-observations --as-of 2026-09-30T12:00:00+00:00 --output .runtime/stored-observations.json
pixi run python -m baselhack.logistics demo --observations .runtime/stored-observations.json --scenario normal
```

This consumes SQLite without external calls and preserves the existing ML output contract. Operational fixtures and named ML scenarios currently remain separate inputs. Mapping batch/stock records into each assessment is subsequent integration work.

## SQLite operation and ownership

Run the collector and Laravel on the same host/local filesystem. WAL supports readers alongside one writer; write transactions are short and HTTP calls occur outside them. Connections enable foreign keys and a five-second busy timeout. Database/journal/lock files stay local; publish fixtures/schema, not runtime history or human decisions. Laravel migrations can later own this schema without changing collection ownership.

- Integrator: collection, database lifecycle, synthetic operations and later scheduling/result persistence.
- ML owner: features/models/simulation; consume stored data without independently scheduled provider calls.
- Laravel owner: app/decision workflows; coordinate schema/migrations with the integrator.

Provider terms and simulation caveats live in [SOURCES.md](SOURCES.md). Operational records are distinct from the 3,000-shipment feature CSV contribution on the dataset branch. Thermal constants and QA stock flags are demonstration assumptions, not release policy.
