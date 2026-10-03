# Smartflow synthetic batch tests — ML builder quick start

This package contains **1,200 batches in 600 independent resource groups**, 650 linked shipments and three synthetic material temperature bands. Each group contains two batches sharing shipments/inventory. This is test/training scaffolding under explicit assumptions, not real production history or validated pharmaceutical QA policy.

## Files and immediate use

- `snapshots.jsonl`: one canonical OperationalDataset snapshot per group. All actual milestones/readings are at or before that snapshot's reference time. Stable IDs join batches, materials, shipments, supply plans, inventory and reservations. These use the existing application contract and cross-record validation.
- `features.csv`: numerical inputs derived only from the snapshot. Empty cells mean missing evidence, not zero. Numeric CSV values use six decimal places of precision at most; raw timestamps preserve UTC offsets. Drop `batch_id` before fitting.
- `labels.csv`: separate synthetic target outcomes and deterministic evidence checks. Never include this file's columns in model inputs.
- `case_index.csv`: group/cutoff/split/scenario metadata for joining, splitting and diagnostics. Scenario family and IDs are not model features.
- `hidden_outcomes.jsonl`: future simulated shipment arrival, QA-release time and final excursion, used only to construct/evaluate targets. Never load into feature construction.
- `manifest.json`: counts, class distributions, feature allowlist and SHA-256 checksums.
- `quickstart.py`: checksum checks, data loading and a majority-class reference score; optional fitted baseline.

After unzipping, run with Python from that folder:

```sh
python quickstart.py
python quickstart.py --fit
```

The first command uses only the standard library. The optional fit needs the already-declared project NumPy/scikit-learn dependencies. Within the project, run it through Pixi with the script path. No external provider calls are made.

## Split and leakage rules

Chronological group split: **840 train, 180 validation, 180 test batches**. Shared shipment/inventory groups never cross splits. Cutoffs advance daily from 2025-02-11. Synthetic future outcomes are deliberately separate from observable snapshots. Use the manifest's feature allowlist; exclude batch/group IDs, split, scenario family and all targets. Fit preprocessing only on train; choose settings on validation and report final test metrics once. If using the existing shipment-training CSV too, do not silently join its unrelated IDs.

## Twelve scenario families

Each family has 100 batches: fully reserved released stock; late arrival; thermal excursion; future planned shipment; partial incoming quantity; competing stock reservations; pending QA; quarantined stock; split delivery with one late leg; missing readings; stale readings; and stock/supply overlap for the same physical incoming lot.

Quantities vary across 25, 40, 50, 75 and 100 kg. Material bands are synthetic 2–8, 15–25 and −20 to −10 °C with different excursion budgets. These are explicit testing assumptions. In the competition case the first batch owns the released reservation; the second may not reuse it. In the overlap case the same physical lot appears as both incoming supply and reserved inventory: these are alternative representations, not additive material.

## Label meanings

| Field | Meaning |
| --- | --- |
| synthetic_ready_by_deadline | Allocated demand is covered by existing released reservations plus incoming quantity that arrives and obtains synthetic QA release by the deadline. For the same-lot overlap, use the maximum coverage rather than adding twice. No reallocation of unreserved stock is assumed. |
| incoming_all_on_time | All linked incoming shipments arrive by this batch's deadline, even when reservations protect production. |
| synthetic_final_excursion_exceeded | At least one linked shipment's complete simulated temperature history exceeds the material's excursion-minute budget. This can depend on hidden future history. |
| temperature_evidence_status | Current evidence is unknown when absent/stale; otherwise exceeded_budget or within_observed_budget. A within-budget partial history is not a QA release or a guarantee about future excursion. |
| released_reservation_shortfall_kg | Batch demand minus its own released reservation. Incoming supply does not erase this stock-only metric. |
| synthetic_usable_coverage_kg | Coverage used by the synthetic readiness oracle, capped by batch demand. |

Readiness and incoming arrival are different targets. Missing/stale evidence can coexist with a future outcome label: the hidden simulation knows an outcome the operator does not yet know. Predicting that outcome must not turn unknown current QA evidence into a release decision.

## Evaluation and limits

Report class counts, majority baseline, balanced accuracy and Brier score for each binary target. Excursion cases are intentionally uncommon; high ordinary accuracy alone is misleading. The generator uses repeated scenario structures and known thermal/rule assumptions, so model scores show learning this synthetic generator rather than real-world performance. No public weather/river/traffic data is fabricated or mixed into this package. No real customer/person/lot data is included.

The original 18-batch demo fixture remains the stable UI acceptance set. This package is separate; importing it into the running app is optional. Generated files are published on data/simulated-shipment-training. To rebuild, use feat/build-integration and run `pixi run ml-batch-data` from the project root; configuration is in config/ml_batch_tests.yaml. The manifest records all generation settings and the generator checksum. The implementation brief is docs/implementation-ml.md in the integration branch.
