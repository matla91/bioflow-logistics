# Build integration and next builder inputs

The review branch `feat/build-integration` assembles the central data engine and logistics simulation with the Laravel app from `origin/dashboard` at ec9a145. Only the Laravel app directory was imported; unrelated branch histories and the archived dashboard were not imported. The fetched `origin/ML` at 74e4179 contains the original scaffold, with no additional ML implementation. The working logistics implementation is already in the engine's ancestry.

See the [data flow diagrams](DATA_FLOW.md) for the product flow, ERP stand-in and current physical stores.

## Current connection

Stored provider observations → scheduled logistics analysis → immutable SQLite assessment/evidence → local read API → Laravel `/integration` page. The page also shows stored operational dataset counts. Existing Laravel shipment decisions remain in Laravel's own database. Do not point Laravel migrations at the engine database: both currently define incompatible `shipments` tables.

```sh
pixi run data-init
pixi run data-import-cache
pixi run operations-seed
pixi run integration-analyze
pixi run integration-api
```

The API listens on localhost port 8002. The dashboard now has a project-local Pixi runtime and generated Composer/npm lockfiles. Local setup and restart commands are in [LOCAL_APP.md](LOCAL_APP.md). Configure `DATA_ENGINE_URL=http://127.0.0.1:8002` in its local environment; Laravel retains its own database. Visit `/integration` after signing in. The app reads stored results; page loads never collect providers or run simulations. `pixi run integration-watch` repeats analysis hourly; collection remains the separate `data-watch` process. Runtime files remain ignored.

The read API exposes `/api/integration/operations`, `/api/integration/assessments` and `/api/integration/assessments/{assessment_id}`. Contracts are generated from [interfaces.py](../pipeline/baselhack/interfaces.py), including [the assessment schema](../schemas/stored-logistics-assessment.schema.json). The worker preserves full normalized observations, scenario, assumptions, station selection, model version and detailed result in immutable evidence. Repeated identical analysis is idempotent; new inputs produce a new assessment ID. Bump the model version when calculation behavior changes.

These are the three retrospective named logistics scenarios, not assessments of the 18 operational batches. They remain probabilities under simulation assumptions. Ambient exposure is not a measured product-temperature excursion. Do not map it into the shipment console's `p_excursion` field or authorize QA release from it. The model has missing-data/proxy warnings and seven existing verification gates remain open.

## Builder implementation briefs

- [Laravel implementation](implementation-laravel.md): batch screens, imports, inventory/QA display and human decisions.
- [ML implementation](implementation-ml.md): stored-data batch-linked assessments, evidence and evaluation.

## Validation and remaining work

Python integration tests exercise stored observations → model → immutable persistence → API, idempotency, fixture export and empty/missing results without network access. The project-local PHP/Composer setup now runs successfully. Laravel tests passed (58 passed, two skipped), Vue type checks and production build passed, and browser login plus the live integration page were verified. This branch is a reviewable connection, not a completed batch workflow or an approved merge.
