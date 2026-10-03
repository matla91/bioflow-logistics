# Batch dashboard integration

Status: done; corrected v2 runtime and four-case presentation verified
Branch: feat/batch-dashboard-integration
HEAD/base: e80c57af142038d5ce8f5034751f4f024dbcf69a

## Scope

Read-only Smartflow batch dashboard with production readiness, incoming shipment,
product-temperature/QA, provenance and collapsed audit details. Existing layout
retained. Laravel reads FastAPI server-side and passes the canonical stored
assessment unchanged. No commits, pushes, staging or merges performed.

The feature branch originally pointed at 51aa295 and the local review database
contained four v1 assessments. This caused retrospective batch 001 to display its
stored BUFFER action. The corrected commit was fetched from the personal origin,
and the unpublished feature branch was aligned to it after a verified backup of
all 14 working files at /tmp/batch-dashboard-e80-backup. UI changes were restored
and documentation reconciled with the corrected base.

Backend recommendation policy, Monte Carlo, SQLite schema, model version and
canonical/generated contracts match e80c57a exactly. No frontend action override
or duration inference was added. Generic supported action labels remain intact.

## Runtime refresh

Existing database: /tmp/batch-dashboard-review.sqlite3.
The existing configure-batches and analyze-batch CLI commands persisted the
configured batch-default-v1 profile and appended v2 records for batches 001–004
at 2026-10-03T12:00:00Z. All four original v1 payload/evidence hashes remain
unchanged. The database now contains four v1 plus four v2 records.

Actual API: http://127.0.0.1:8002.
All four /api/integration/batches/{batch_id}/assessments/latest endpoints return
batch-stored-evidence-v2, the requested cutoff, and recommendation.action=null.
Batch 001 assessment ID:
9f13b9ca0e9f703cc19fd7caf06958b56f42f4a799055ad8705c522d98a83067.

The original port 8002 request found no listening service; the previous dashboard
review API was on 8012. The review API was restarted on 8002 against that same
existing database, and Laravel on 8010 now uses DATA_ENGINE_URL pointing to 8002.
Original .env was not changed and Laravel's database was not reseeded.

## Temperature display

Main card and audit consume ProductTemperatureEvidence.observed_excursion_min
directly. Null stays Unavailable/—, zero displays 0 min observed beside Journey
incomplete, and positive values show their observed duration. Source-reported
cumulative excursion remains separate in audit details. First/last samples and
unobserved bounded intervals do not claim continuous whole-journey coverage.

The earlier report claiming the contract lacked observed duration was incorrect;
the canonical Python and generated TypeScript contracts contain the field.

## Four displayed cases

- 001: retrospective; 50 kg snapshot released reservations; shipment arrived;
  99.5 min observed; no forward action; QA review required. The snapshot does not
  establish historical QA/reservation state at the past charge time.
- 002: 30 kg reserved, 20 kg shortfall; 147.7 min observed, demo budget exceeded;
  journey incomplete; timing unavailable; no forward action; QA review required.
- 003: 0 min observed in usable intervals, journey incomplete; explicitly no
  whole-journey compliance claim; timing unavailable; no forward action; QA review.
- 004: no readings, observed excursion null and main card —; future shipment with
  no actual departure at cutoff; timing unavailable; no forward action; QA review.

## Validation

- git merge-base --is-ancestor e80c57af142038d5ce8f5034751f4f024dbcf69a HEAD:
  passed (CORRECT_BASE). Required grep checks locate v2, reached-deadline logic
  and observed_excursion_min in both canonical/generated contracts.
- php artisan test tests/Feature/IntegrationTest.php: 12 passed, 210 assertions.
- node dashboard/tests/Frontend/batch-display.test.mjs: 15 passed, no failures.
- npm run types:check (dashboard): passed, vue-tsc --noEmit.
- Scoped vp check on BatchAssessment.vue, Integration.vue, AppSidebar.vue,
  batch-display.ts and batch-display.test.mjs: all formatted, no warnings/errors.
- npm run build (dashboard): passed, 3383 modules, 9.76 seconds.
- Scoped Pint --test for controller/routes/integration tests: passed.
- Controller PHPStan --debug: passed, zero errors.
- Browser: all four batches at 1366x768 and 1440x900; expected stored states,
  no horizontal overflow, QA status visible, audit collapsed by default.
  Expanded batch 001 audit confirms v2, observed 99.5 min and separately reported
  99.8 min. No browser warnings or errors observed.
- Actual API payload projection requested by user explicitly checked on port8002;
  all four latest records saved locally. Original four v1 records hash-verified.
- git diff --check: passed. No staged files.

## Local review

Review URL: http://127.0.0.1:8010/integration/batches.
Persistent review servers are API exec session 35575 and Laravel session 60187.
If restart is needed, from repository root:

```sh
PYTHONPATH=pipeline .venv/bin/python -m baselhack.integration serve --database /tmp/batch-dashboard-review.sqlite3 --port 8002
cd dashboard
DATA_ENGINE_URL=http://127.0.0.1:8002 php artisan serve --no-reload --host=127.0.0.1 --port=8010
```

Ignored local evidence in .runtime/batch-dashboard-review/ includes CLI and API
v2 payloads for 001–004, four 1366 screenshots and v2-browser-checks.json.
No automatic QA release or batch approval is implemented.

## Resume

Review the uncommitted dashboard changes on the corrected branch. Preserve the
stored backend decisions and canonical contracts. Do not commit or push without
subsequent authorization; do not merge without explicit approval for that PR.
