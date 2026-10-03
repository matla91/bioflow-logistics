# Smartflow — Laravel implementation brief

## Starting point

Use `feat/build-integration` in https://github.com/cfpramod/current-affairs. The assembled Laravel app lives in the dashboard directory. It has shipment overview/console pages, role-based decisions and a separate logistics analysis page at `/integration`. Smartflow is the product name; keep the repository URL and external dataset IDs.

Read [BUILD_INTEGRATION.md](BUILD_INTEGRATION.md) and [LOCAL_APP.md](LOCAL_APP.md). Preserve the stored-data connection and branding. Initial integration passed 58 Laravel tests (two skipped), Vue type checks, production build and browser login/live analysis checks. Dependency locks are generated. Startup fixes include unique simulated lot IDs with external references and production-only HTTPS forcing.

## Implement next

1. Import [synthetic operations](../data/examples/operations/README.md) using a repeatable seeder/import command. Retain integer primary keys and store stable fixture IDs as unique external references. Add materials, batches, incoming supply plans, inventory lots, stock reservations and shipment readings. Resolve relationships from external references, not record order.
2. Support `planned` shipments and nullable actual departure/arrival. Keep planned and actual milestones separate. Reactor and charge time belong to the batch; a shipment may supply several batches.
3. Build batch list/detail pages showing quantity/deadline, incoming shipments, released reserved stock, shortfall and QA availability separately. Show the latest linked assessment, or pending when unavailable. Seeded workflow status is not an ML readiness verdict.
4. Import the ML builder's batch-linked results idempotently by assessment hash and external batch/shipment IDs once its additive contract exists. Preserve full evidence. Record operator/logistics/QA decisions against that exact assessment, with reasons for overrides. Preserve current role checks and decision history.

## Boundaries

- Laravel owns its app migrations/database. Keep it separate from the engine database: current shipment tables conflict. Never run Laravel migrations against the engine database.
- Collection and analysis scheduling stay in Python workers. Page loads read stored results through `DATA_ENGINE_URL`, default port 8002.
- Named logistics scenarios are not operational batch assessments. Never attach them by guessed IDs.
- Ambient exposure proxy risk is not product-temperature excursion probability; do not insert it into `p_excursion` or authorize QA release from it.
- Supply plans are prospective coverage, not released inventory. Pending-QA stock and released stock reserved to another batch cannot cover this batch.
- Display retrospective assessments explicitly, preserving null action and the limitation on historical reservation/QA state. A sufficient snapshot quantity does not establish readiness at a past charge time. Null sampled excursion with retained readings means no usable interpolation interval, not zero excursion.

## Acceptance cases

Use the reference time 2026-10-03 12:00 UTC. IDs have prefix `operations-demo-v1-`:

| Batch | Screen evidence |
| --- | --- |
| batch-001 | Arrived shipment and 50 kg snapshot reservation; charge at 10:00 precedes cutoff, so retrospective assessment with null action |
| batch-002 | Heat-exposed shipment; 30 kg reservation and 20 kg shortfall |
| batch-003 | Delayed shipment, no released reservation |
| batch-004 | Future planned shipment, no actual milestones/readings |

The released lot totals 80 kg, reserved as 50 + 30. The separate 100 kg pending-QA lot must not fill a shortfall. Check competing reservations and repeat imports without duplicates. Before batch ML exists, show pending outcomes honestly.

## Checks and handback

Run Laravel tests, PHP formatting, Vue types and frontend build. Demonstrate all four batches plus an approval/override tied to immutable assessment evidence. Preserve locks through package managers. Coordinate the canonical interface with ML; changes require a decision line and regenerated schemas/types. Return the branch/commit, validation results and remaining limitations. Do not merge without explicit approval.
