# Batch example datasets

Status: done · Updated: 2026-10-03 · Branch: feat/sqlite-data-engine · Owner: @cfpramod

## Goal and done

Provide the Laravel teammate with usable synthetic batch examples. The package under data/examples/operations contains JSON arrays and matching CSVs exported from the validated operations-demo fixture: 18 batches, 12 shipments, one material, five inventory lots, 18 incoming supply plans, two reservations and 261 temperature readings. The README documents joins, import order, four trial cases, stable IDs, nulls, units and simulated assumptions. A standard-library exporter keeps the package reproducible; the manifest records counts/checksums.

## Next

The dashboard owner can copy just the example folder into the dashboard branch and write a Laravel seeder. Align schema/IDs, add planned shipment support and distinguish batch demand from shipment records. No engine merge or shared-database wiring is needed to trial these fixtures. No merge authorized.
