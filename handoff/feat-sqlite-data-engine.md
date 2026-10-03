# Central ingestion and synthetic operations

Status: done, ready for review · Updated: 2026-10-03 · Branch: feat/sqlite-data-engine · Owner: @cfpramod

## Goal and state

Centralize external collection in SQLite and generate linked synthetic shipment/batch/stock records. ML and Laravel consume stored data. Builds on the teammate's logistics branch and provider adapters; private backup is separate. Laravel migration details were requested; database contract remains provisional pending alignment.

## Done

- Additive OperationalDataset models and SQLite history/store.
- Central ingest/import/export and interval worker with retries, overlap, independent provider reporting and collector lock.
- Seeded generator with current/future plans, thermal histories, batch demand, incoming supply and released/pending-QA stock.
- Generated JSON Schema/TypeScript contract and a fixture with 12 shipments, 18 batches, five inventory lots and 261 readings.
- Offline import stored 166 real cached observations; exported them to the existing ML demo without external calls.
- Live bounded collection passed for all three providers (1 traffic, 13 Rhine, 2 weather observations). All matched cached values; receipts were recorded without duplicate observations.
- Regression suite passed 241 tests with seven existing verification gates deselected; those gates remain outside this change. Scoped lint/format, generated contracts and strict documentation checks pass.

## Next

1. Review this branch against `feat/basel-logistics-layer`. The logistics branch has unrelated history to the team-setup branch; do not blindly merge those histories.
2. Align with Laravel migrations before integration. Add ML scheduling/result persistence and operator/QA decision history in subsequent integration work. No merge authorized.

## Resume

> Continue feat/sqlite-data-engine in current-affairs. Read this handoff and docs/DATA_ENGINE.md, then start with Next. Keep provider calls centralized.
