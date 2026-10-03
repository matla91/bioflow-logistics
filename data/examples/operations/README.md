# Synthetic operations for the Laravel trial

Start with **batches.json**, then import the linked shipments and stock. Each JSON file is an array of records; a matching UTF-8 CSV contains the same rows. These are entirely synthetic examples with a fixed reference time of **2026-10-03 12:00 UTC**. Interpret past/current/future relative to that time, rather than the laptop clock.

| JSON / CSV name | Records | Purpose |
| --- | ---: | --- |
| materials | 1 | Material, temperature band and assumed excursion budget |
| shipments | 12 | Arrived, in-transit and future planned shipments |
| batches | 18 | Reactor, material, quantity, planned charge time and workflow status |
| batch_supply_plans | 18 | Incoming shipment quantities assigned to batches |
| inventory_lots | 5 | On-site quantities, availability times and QA state |
| stock_reservations | 2 | Released stock allocated to competing batches |
| shipment_readings | 261 | Synthetic product/ambient temperatures and excursion histories |

## Record relationships

- Match shipment, batch and inventory **material_id** to material **id**.
- Match supply-plan **batch_id** and **shipment_id** to the corresponding records.
- Match reservation **batch_id** and **inventory_lot_id** to batch and inventory records.
- Match reading **shipment_id** to shipment **id**.
- Inventory **shipment_id**, when present, identifies the shipment that delivered that lot.

IDs are stable strings beginning with the dataset ID. Laravel can retain its integer primary keys and preserve these fixture IDs as unique external references, resolving relationships during import. Suggested import order: materials, shipments, batches, inventory, supply plans, reservations, readings. The examples do not require merging the Python engine or pointing Laravel at its database.

## Four cases to put on screen

All IDs below have the prefix **operations-demo-v1-**.

| Batch | Incoming shipment | Expected example |
| --- | --- | --- |
| batch-001 | shipment-001 | Normal arrived shipment; 50 kg released stock reserved for a 50 kg batch |
| batch-002 | shipment-002 | Heat exposure in transit; only 30 kg released stock reserved, leaving a 20 kg reservation shortfall |
| batch-003 | shipment-003 | Delayed shipment, no released stock reserved for this batch |
| batch-004 | shipment-004 | Future planned shipment: no actual departure, arrival or temperature readings |

The released lot has **80 kg**, reserved as **50 + 30 kg**. The separate **100 kg pending-QA lot** is unavailable for released-stock coverage. Three arrived shipment lots are also pending QA. Incoming supply plans describe prospective coverage; do not add them to released stock or assume the whole batch demand is covered twice.

Batch status is a seeded workflow value, not an ML readiness verdict. Assess stock coverage, arrival risk and QA separately. No fresh ML assessment or operator decision is fabricated by this package.

## Fields and conventions

Quantities are kg, temperatures °C, excursion duration minutes. Timestamp strings have explicit UTC offsets. JSON null becomes an empty CSV cell; parse it as null, never as an actual milestone. CSV booleans are true/false. The material temperature band is a JSON array inside its CSV cell. Shipment **planned_departure_at/planned_arrival_at** and **actual_departure_at/actual_arrival_at** are separate; future operations must not acquire invented actual timestamps. Their status includes **planned**, which the current Laravel shipment enum still needs to support.

The current dashboard stores reactor and charge time on a shipment. With batch records, reactor and charge time belong to each batch; supply-plan links allow one shipment to supply several batches. These field names are example contracts, not an assertion that the current Laravel migrations already match them.

## Provenance and regeneration

The canonical bundle is [operations-demo.json](../../../output/operations-demo.json), validated by the operational models. [manifest.json](manifest.json) records counts and checksums. All thermal/quantity/QA assumptions are in [operations_demo.yaml](../../../config/operations_demo.yaml); these are demonstration values, not pharmaceutical release policy. The existing 3,000-shipment training CSV is a separate ML feature dataset.

After generating the canonical fixture, export these files with:

```sh
python scripts/export-operation-examples.py
```

Run from the repository root. The exporter uses only the Python standard library. Download this folder from **feat/sqlite-data-engine**, or copy only this folder into the dashboard branch for its Laravel seeder. No branch merge is needed to use the examples.
