# Batch-linked assessments

Status: done · Repository: matla91/bioflow-logistics · Branch: feat/batch-linked-assessments · Updated: 2026-10-03

## State

Corrective work extends the existing batch implementation at
51aa295f58d0cb7f9784e6f33476a9f867613f88, preserving its history and canonical
contracts. Calculation version is batch-stored-evidence-v2. The reviewable scope
is the personal branch; no main/team merge or dashboard redesign is included.

## Corrections and review

- Reached charge deadlines, including exact equality with cutoff, produce null
  action and no forward logistics alternatives or simulation. Released stock,
  arrived shipment facts and measured temperature evidence remain available.
- Retrospective reservation evidence explicitly describes the operational snapshot;
  it cannot reconstruct reservation/QA state at the exact historical charge time.
- Before the deadline, sufficient released reservations can still support BUFFER,
  with human approval and incoming QA evidence retained separately.
- A single sample or only excessive interpolation gaps yields unavailable/null
  duration while retaining individual temperatures and source-reported totals.
  A zero within usable sampled intervals remains valid evidence, including batch 003;
  it does not establish whole-journey compliance. QA release stays unauthorized.
- Reviewed normalized supply/reservation joins, quantity conservation and competition,
  material/QA/availability constraints, future evidence and known_at filtering,
  stale/overdue timing, evidence identity/immutability and read-only API behavior.
  No further confirmed correctness issue required architectural changes.
- Regenerated and compared all four demo records: quantities, arrival evidence,
  product-temperature evidence, assumptions and sources match the prior checkpoint.
  Batch 001 now has a retrospective null action. Full reference results and
  command/API details live in [BATCH_ASSESSMENTS.md](../docs/BATCH_ASSESSMENTS.md).
- Ran the canonical contract generator: schemas and TypeScript remain identical;
  no generated contract or dashboard implementation is changed.

## Verification

- Python 3.12; direct Python dependencies used here match the committed Pixi lock.
  Pixi is unavailable in the execution environment, so commands used the project's
  isolated virtual environment and existing declared dependencies.
- Full regression command: pytest -q tests -m 'not verification'. Result:
  319 passed, seven deselected, one existing Starlette/httpx deprecation warning.
- Also ran pytest -q tests without deselection: 319 passed and only the seven
  original verification gates failed. Their false flags and test definitions
  are unchanged.
- Batch assessment/database/temperature plus integration tests pass. New regressions
  exercise past/equal/future deadlines, preserved facts, blocked forward calls,
  unknown duration and immutable versioned records/latest ordering.
- Scoped Ruff passes for batch, database, interfaces and integration code/tests;
  full Python Ruff format passes (86 files). Generated-contract verification,
  strict documentation checks and git diff whitespace checks pass.
- Repository-wide Ruff has 20 pre-existing diagnostics in unchanged
  ingestion/simulation/output files and logistics tests, down from 27 initially
  because seven diagnostics in touched batch files were corrected. The global
  lint task is not green; no unrelated style refactor or rule weakening is included.
- Offline ingestion fixtures construct httpx clients; proxy environment variables
  were removed only for pytest because this environment advertises a SOCKS proxy
  without socksio. Provider/network guards in batch analysis tests remain active.
- Seven original verification gates remain false and unchanged:
  navigation_bands, basel_high_water, traffic_stations, river_history, licence,
  data_licences, september_start. No new domain/licence evidence resolves them.

## Integration and remaining limits

The correction is ready for review on the personal branch. The team repository
cfpramod/current-affairs returned 404 through the current GitHub connection;
its present state and cherry-pick conflict behavior could not be verified.
The teammate should fetch the personal branch into a clean checkout and apply the
corrective commit only after checking that the batch implementation is present.
If absent, first review/apply its implementation commit
51aa295f58d0cb7f9784e6f33476a9f867613f88, then the corrective commit. Re-run tests
and regenerate stored batch assessments under v2. Never overwrite v1 records.

Laravel still needs stable external references, batch-result display through HTTP
and human traces tied to immutable assessment IDs. Engine and Laravel databases
stay separate. Synthetic operations, uncalibrated coefficients, September-stale
provider measurements at the October cutoff, absent historical QA/reservation
capture, sparse product temperatures and unsupported aggregate multi-shipment
decisions remain explicit limits. There are no training or performance claims.
