# Stored batch assessments

This additive SQLite-only worker preserves the three named logistics scenarios.
It joins operations and observations at an explicit cutoff, never calls providers,
and never authorizes QA release. Laravel uses HTTP and its separate database.

## Run and regenerate

Import operations and observations as in [BUILD_INTEGRATION.md](BUILD_INTEGRATION.md), then:

```sh
pixi run batch-configure
pixi run batch-analyze --dataset-id operations-demo-v1 --batch-id operations-demo-v1-batch-001 --as-of 2026-10-03T12:00:00Z
pixi run contracts
```

Repeat analysis for batch-002 through batch-004. Configuration separately persists
[batch_assessment.yaml](../config/batch_assessment.yaml) and existing logistics
coefficients. Analysis then consumes only SQLite. Changed settings require a new
immutable profile ID. CLI options include `--database`, `--profile-id`, `--known-at`.
Scheduling stays outside HTTP through worker invocations with explicit cutoffs.

The corrected calculation version is `batch-stored-evidence-v2`. Re-run batch
analysis to append v2 records; deployment does not rewrite existing v1 assessments.
Exact record IDs still retrieve their original version and evidence. The canonical
fields and generated contracts are unchanged.

Canonical models live in [interfaces.py](../pipeline/baselhack/interfaces.py).
The generator produces [the schema](../schemas/stored-batch-assessment.schema.json)
and both existing TypeScript outputs; generated contracts are never hand-edited.

## Contract and data flow

`StoredBatchAssessment` contains assessment/dataset/batch/shipment IDs, `as_of`,
optional `known_at`, `input_sha256`, `model_version`, `production_readiness`,
`incoming_shipments`, `product_temperature`, `recommendation`, provenance,
external sources, persisted assumptions and limitations.

1. `Database.batch_snapshot` joins batch → plans → shipments/material/readings
   and batch → reservations → inventory, retaining competing reservations.
   Normalized columns provide live quantities/times/QA; existing shipment JSON
   supplies route descriptors. Generator scenario labels are excluded.
2. `analyze_batch` reads the immutable profile and observations. It excludes
   later measurements/readings/actual milestones and unarrived incoming inventory.
   `known_at` filters external receipts; knowledge before the operational snapshot
   reference is rejected. Operational change/capture history is unavailable.
3. Released coverage uses this batch's reservations available by cutoff and charge.
   Released + incoming dependency + uncovered quantity equals demand. Unreleased,
   free or competing stock cannot hide shortages. Released delivered lots require
   reservations; their original incoming plans cannot count a second time.
4. Supported departed shipments reuse features, paired Monte Carlo and transparent
   deterministic recommendations. Remaining journey is planned duration minus
   elapsed time since actual departure. Recorded arrival needs no forward model.
   Stale/missing weather, future departures, unsupported corridors, reached deadlines
   and exhausted planned duration produce unavailable timing. Baseline arrival
   probability and ETA percentiles use identical seeded draws; ambient exposure
   remains a separate proxy.
5. Actual `product_c` samples are compared with material limits using explicitly
   assumed linear interpolation. Long gaps are skipped; no temperature is
   extrapolated. Supplied cumulative excursion stays separately visible. Missing
   readings, a single sample or exclusively over-limit gaps mean null excursion
   duration and unavailable status; individual temperatures and reported totals
   remain visible. Sampled within-budget status cannot establish
   whole-journey compliance, pharmaceutical quality or release.
6. Results and exact inputs are appended to `batch_assessments`. Input identity
   includes profile/cutoff/observations/model version; assessment identity also
   includes results. Exact reruns are idempotent. SQL prevents update/delete/
   replacement; persistence checks evidence hashes and collisions. Calculation
   changes require a model-version bump.

When `planned_charge_at <= as_of`, the assessment is retrospective: action is
null, forward alternatives are empty, and no forward logistics simulation runs.
Recorded arrivals, stock quantities and sampled product temperatures are retained.
Snapshot reservation/QA state and an availability timestamp do not prove the
reservation or QA state at the exact historical charge time; that history cannot
be reconstructed. Quantity sufficiency describes the persisted snapshot.

Before the charge deadline, BUFFER requires sufficient released reservations.
Single-shipment comparisons reuse the existing policy; multiple dependent shipments
have no aggregate action
comparison. Logistics approves transport interventions; operators approve BUFFER.
`qa_review_required` separately preserves incoming review. Release authorization
always remains false; ambient proxies never trigger automatic quarantine.

## Acceptance at 2026-10-03 12:00 UTC

[Four reproducible records](../output/batch-assessments-demo.json) use unchanged
operations and provider cache. Each batch demands 50 kg.

| Batch suffix | Released reserved kg | Shortfall / dependency kg | Incoming evidence | Sampled excursion min | Recommendation |
| --- | ---: | ---: | --- | ---: | --- |
| batch-001 | 50 | 0 / 0 | Arrived Oct 2 06:00; exact on-time indicator 1 | 99.496664, below 120 | null; retrospective, QA review required |
| batch-002 | 30 | 20 / 20 | Planned Oct 3 18:00 after 16:00 charge; model unavailable | 147.698443, exceeds 120 | null; review, QA required |
| batch-003 | 0 | 50 / 50 | Planned Oct 3 18:00 before 22:00 charge; model unavailable | 0 in sampled intervals; incomplete | null; review, QA required |
| batch-004 | 0 | 50 / 50 | Future departure Oct 4 12:00 after 04:00 charge; no model | Unavailable, null | null; review, QA evidence missing |

Batch 001's 10:00 UTC charge precedes the 12:00 UTC cutoff. Its 50 kg reservation
is a snapshot fact, not proof of historical reservation/QA state at 10:00, and
cannot support a new forward BUFFER recommendation.

Real cached measurements end September 30 12:00: 4,320 minutes stale at cutoff.
Existing weather safeguards prevent probabilities for batches 002–003. Batch 003's
delayed future arrival is not stored; its label cannot establish lateness. Fresh
stored observations are required. Tests exercise Monte Carlo with explicitly
synthetic data, without shifting or relabelling the real cache.

Sample totals differ slightly from supplied cumulative values (99.769820 and
147.784928 minutes): the fixture used physical thermal integration; this calculation
interpolates sample points. Batch 001's last temperature exceeds the band despite
total sampled excursion below budget, retaining the requirement for human QA review.

## Read API and Laravel handoff

- `GET /api/integration/batch-assessments`: optional `dataset_id`, `batch_id`,
  `as_of`; newest applicable stored records first.
- `GET /api/integration/batch-assessments/{assessment_id}`: immutable exact record.
- `GET /api/integration/batches/{batch_id}/assessments/latest`: optional
  `dataset_id`, `as_of`; newest stored cutoff at or before filter. Ties use stored
  time then assessment ID. Missing records return 404.

Offset-free cutoff queries return 422. Latest refers to analysis cutoff, not
historical record availability or a guarantee of the latest deployed model.

Laravel's authenticated `/integration/batches` view consumes the stored list and
selected latest endpoint server-side and passes the existing generated contract
unchanged to Vue. Three compact cards show production quantities, incoming
milestones/timing and sampled product-temperature/QA evidence. Null excursion and
timing remain unavailable; zero observed excursion remains paired with incomplete
journey status. The corrected v2 batch 001 displays its recorded null action as
no forward action, with the retrospective snapshot-history limitation visible.
Audit details retain the immutable ID, digest, version, source metadata and
limitations. No batch decision or QA release is written by this view.

The observed product excursion duration comes directly from
`ProductTemperatureEvidence.observed_excursion_min`: it estimates time outside
the material range over usable sampled intervals. It is distinct from the sample
window, bounded unobserved intervals and source-reported cumulative excursion.
When no usable sampled interval exists, duration remains null, not zero; zero
bounded gaps do not prove complete observation of an unfinished journey. The UI
formats these supplied fields without calculating another duration or changing
recommendations.

Stable operational imports and human traces tied to exact assessment identity
remain future work. Never map ambient proxy to product excursion or target engine
SQLite with Laravel migrations. Pages/decision storage are unchanged in this slice.

## Limits and verification

Operations are synthetic and coefficients uncalibrated. QA/reservation/capture
history is unavailable. Stock sufficiency describes the snapshot and availability
timestamps; it cannot prove what was known or done at a past charge. Earlier-cutoff
snapshot stock is not credited. External replay relies on retained retrieval history.
No training or performance claims are introduced; seven verification gates stay open.

Run `pytest -q tests -m 'not verification'`, scoped Ruff, and
`python -m baselhack.generate --check`. Tests cover joins, quantities, competition,
QA, cutoffs/future exclusions, missing samples, lateness, deterministic probabilities,
immutable evidence and read APIs with provider fetches blocked.

The correction checkpoint passes 319 regression tests with seven verification
gates deselected and unresolved. Scoped Ruff passes for batch and integration
files; repository-wide Ruff reports 20 pre-existing diagnostics in unchanged
ingestion/simulation/output files and logistics tests. Full Python formatting,
generated-contract verification, strict doc checks and whitespace checks pass.
