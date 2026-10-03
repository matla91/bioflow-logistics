# Smartflow — ML implementation brief

## Missing element

Implement **batch-linked assessments from stored operations**. The additive vertical slice is documented in [BATCH_ASSESSMENTS.md](BATCH_ASSESSMENTS.md); the original three named scenarios remain available. The requirements below describe the intended boundary and remaining limitations.

Start from `feat/build-integration` in https://github.com/cfpramod/current-affairs. Read [BUILD_INTEGRATION.md](BUILD_INTEGRATION.md), [DATA_ENGINE.md](DATA_ENGINE.md), [operations examples](../data/examples/operations/README.md) and [the canonical interface](../pipeline/baselhack/interfaces.py). Reuse logistics/thermal/rules code where its assumptions apply. The fetched ML branch contained only the original scaffold at the last check; provide the implementation on a reviewable feature branch.

## Ready-to-use ML test data

The [data branch package](https://github.com/cfpramod/current-affairs/tree/data/simulated-shipment-training/data/ml/batch-tests-v1) contains 1,200 batches in 600 independent groups, 650 shipments and 9,637 readings across 12 scenario families. Download the neighboring batch-tests-v1.zip archive or the folder and run its quickstart.py. It includes validated OperationalDataset snapshots, observable features, separate synthetic labels, hidden future outcomes, grouped chronological splits and checksums. Keep hidden outcomes and case-family/ID metadata out of model inputs. The original 18-batch demo fixture is unchanged.

Use the package for implementation/regression tests and initial synthetic experiments, not evidence of real-world performance. The generator/config/tests are on the integration branch; generated deliverables are on the data branch.

## Inputs

The engine is the only scheduled provider collector. Read stored observations and operations at an explicit cutoff; exclude later readings/measurements/actual milestones. Preserve knowledge-time/revision limitations rather than implying historical knowledge never captured.

Join batch → incoming supply plan → shipment → material/readings, and batch → reserved inventory. Validate material compatibility, quantities, availability time and QA state. Stock reserved to competing batches is unavailable. Incoming supply is prospective: do not add it to available stock or cover demand twice.

## Outputs

Provide separate answers for:

1. Production readiness at planned charge time, considering incoming coverage and released reserved stock.
2. Each incoming shipment's arrival by the batch deadline, including supported probabilities/ETA uncertainty.
3. Actual product-temperature/QA evidence against the material range and excursion budget. Planned shipments without readings have unavailable evidence, not zero-excursion verdicts. Ambient exposure stays a distinct proxy; ML never authorizes pharmaceutical release.

Compare eligible actions, explain the recommendation/alternatives and preserve provenance, assumptions and limitations. Buffer can protect production while incoming material remains exposed or late. Do not fabricate probabilities from fixture labels or special-case batch IDs.

Add an additive shared contract containing dataset/batch IDs, shipment IDs, cutoff, input/evidence hash, model version, separate outcomes/probabilities, alternatives and provenance. Keep it in the canonical interface with a decision line and generated schemas/TypeScript. Coordinate with Laravel so both builders use this contract.

Extend the integration worker and immutable persistence boundary for batch results. Preserve full inputs/results and idempotent hashes. Laravel needs results linked through stable external references. Scheduling remains outside HTTP requests; ML does not independently fetch providers.

## Acceptance cases and evaluation

Use reference time 2026-10-03 12:00 UTC. IDs carry prefix `operations-demo-v1-`:

| Batch | Evidence affecting the assessment |
| --- | --- |
| batch-001 | Normal arrived shipment; 50 kg released reservation for 50 kg demand |
| batch-002 | Heat-exposed shipment; 30 kg reservation and 20 kg shortfall |
| batch-003 | Delayed incoming shipment, no released reservation |
| batch-004 | Future planned shipment, no actual milestones/readings |

The released 80 kg lot is fully reserved to batches 001 and 002. Pending-QA lots cannot provide released coverage. Test competition, cutoff filtering, missing readings, insufficient quantities, repeat-run determinism, persistence and API retrieval.

For trained models, report held-out evaluation, leakage-safe chronological/grouped splits, baseline comparisons and synthetic-data limitations. Simulated labels do not establish real-world prediction quality. Separate measured temperature evidence from simulated future risk.

## Handback

Return the contract, branch/commit, four reproducible assessments, tests/evaluation and remaining limits. Run regressions; preserve seven existing verification gates unless separate evidence resolves them. Coordinate Laravel import once the contract is available. Do not merge without explicit approval.
