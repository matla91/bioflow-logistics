# Basel logistics frontend contract

The primary JSON contract is generated from `LogisticsFrontendResult` in
[`interfaces.py`](../pipeline/baselhack/interfaces.py):
[`logistics-frontend.schema.json`](../schemas/logistics-frontend.schema.json).
The CLI emits this compact contract by default. A frontend or explanation layer
can display the supplied recommendation without selecting an action itself.

Reproducible examples are
[`logistics-normal.json`](../output/logistics-normal.json),
[`logistics-disruption.json`](../output/logistics-disruption.json) and
[`logistics-severe.json`](../output/logistics-severe.json). Use `--detailed` to
export the validated diagnostic contract with coefficients, full source metadata
and risk drivers; those details are excluded from the primary payload.

## Payload

| Field | Meaning |
| --- | --- |
| `as_of` | Scenario cutoff with an explicit UTC offset. Future evidence is excluded from risk calculations. |
| `shipment_id` | Identifier of the simulated shipment. |
| `external_state` | Available Rhine, traffic and ambient weather features, navigation assessment and evidence warnings. Observations can be absent; missing evidence is not replaced by fabricated real observations. |
| `simulated_shipment` | Explicitly simulated shipment schedule, stock, packaging protection and action availability, with `simulated: true`. |
| `operational_impact` | Baseline mean lateness, delay frequency and ambient exposure proxy frequency before applying an action. |
| `actions` | Exactly one comparable record for each of `BUFFER`, `EXPEDITE`, `REROUTE`. |
| `recommendation` | Deterministic selected action, categorical evidence quality, reason, explanations for every alternative, demonstrated change conditions and policy detail. The action is `null` if no action is eligible. |
| `data_provenance` | Concise evidence labels with references to detailed source metadata. |
| `limitations` | Model scope, assumptions, missing evidence and the ambient-to-product guardrail. |

Action records use these dimensions consistently:

| Field | Meaning |
| --- | --- |
| `eligible` | Whether the scenario permits the action. BUFFER requires sufficient stock; transport interventions require their simulated availability and applicable route eligibility. |
| `production_continuity_probability` | Fraction of runs in which the factory meets the exact required deadline. Sufficient simulated stock makes BUFFER continuity 1.0 even if the incoming shipment is late. For shipment interventions this equals on-time arrival; ambient proxy results do not imply pharmaceutical usability. |
| `on_time_arrival_probability` | Fraction of runs in which the incoming shipment reaches the destination by the exact simulated deadline. No lateness tolerance is applied. BUFFER does not accelerate that shipment. |
| `cold_chain_exposure_proxy_risk` | Fraction of runs in which the assumed ambient degree-minute proxy exceeds its assumed budget. This is not a probability of product excursion or quality loss. |
| `predicted_delay_min` | Mean factory lateness beyond the required deadline. BUFFER can make this zero while incoming arrival remains late. |
| `predicted_arrival_delay_min` | Mean incoming shipment lateness beyond that same deadline, independently of factory stock coverage. |
| `assessment`, `reason` | Deterministic explanations of the action's effects and availability. |

All probability/frequency fields are finite numbers in `[0, 1]`; minute estimates
are nonnegative. Ineligible actions remain visible with explanatory reasons and
hypothetical scenario timing/exposure estimates; the recommendation never selects
them. Route closure estimates use an explicitly assumed finite modelling horizon
and cannot establish an arrival forecast.

Baseline `delay_risk` is the fraction of runs whose lateness exceeds
`delay_threshold_min`, which is an assumed warning tolerance. This differs from
the exact-deadline definition of action on-time arrival and production continuity.

The exposure proxy is:

```text
prior simulated degree-minutes
  + ambient degrees outside the assumed reference band
    × max(journey minutes − assumed protection minutes, 0)
```

The snapshot ambient temperature is held constant over the future journey. The
reference band, packaging autonomy and proxy budget are assumptions, not validated
product response or QA limits. This required limitation is always preserved:

> Ambient weather observations alone do not establish actual product-temperature excursion, pharmaceutical quality, or QA release status.

## Deterministic recommendation

The policy uses explicit priorities rather than a weighted score. Its default
service targets are assumptions exposed in `recommendation.policy_detail` and
the detailed coefficients, not statistical calibration or pharmaceutical limits.

1. Exclude ineligible actions. Qualifying actions have production continuity at
   least `target_production_continuity` (default 0.95).
2. Prefer qualifying BUFFER when its incoming on-time arrival is at least
   `target_on_time_arrival` (default 0.90) and incoming exposure proxy risk is at
   most `max_exposure_proxy_risk` (default 0.10).
3. Otherwise compare qualifying EXPEDITE/REROUTE by lower exposure proxy risk,
   then lower incoming mean lateness, then higher on-time arrival. Exact remaining
   ties prefer EXPEDITE.
4. If no shipment intervention qualifies, use qualifying BUFFER to preserve
   factory continuity while explicitly explaining the incoming shipment risks.
5. If none qualifies, select the eligible action with greatest production
   continuity, then lower exposure proxy risk, then lower incoming mean lateness.
   Remaining ties use BUFFER, EXPEDITE, REROUTE in that order. State that the
   target is unmet. If none is eligible, return `action: null` and LOW evidence
   quality with a reassessment explanation.

`why_not` contains every unselected action exactly once, including ineligible
alternatives. `would_change_if` contains only changes demonstrated by paired model
reruns with the same random seed: stock availability, remaining journey time,
protection autonomy or an expedite assumption. Empty means no evaluated change
altered the decision. These are tested counterfactual values, not interpolated
thresholds or universal guarantees. No raw inputs are sent to an LLM.

This layer does not issue QA REVIEW. An ambient temperature outside the assumed
reference band does not create a logger excursion or another quality event. A
future QA-review rule would need an explicitly defined package/logger signal or
quality-relevant event with its own provenance; none is inferred here.

## Confidence and provenance

`recommendation.confidence` is an evidence-quality category, not a calibrated
probability. The contract supports HIGH/MEDIUM/LOW; this prototype never produces
HIGH because shipment/factory inputs are simulated and coefficients are assumed.

MEDIUM requires usable fresh traffic anomalies with sufficient baselines, current
Rhine level/discharge and both trends, ambient weather with precipitation/wind,
declared source coverage for Basel 100006/100089 and MeteoSwiss BAS, and no
feature/snapshot/navigation warnings. Missing, stale, future, incomplete or
unlinked inputs lower it to LOW. Complete observations do not validate the assumed
transport or thermal relationships.

| Provenance kind | Usage |
| --- | --- |
| `REAL` | Current features with matching declared observation sources. Provider and observation time are retained. Metadata alone does not establish a current observation. |
| `OFFICIAL_FORECAST` | A supplied, valid, identified official forecast/status adapter input. The offline examples contain none. |
| `MODEL` | Traffic historical statistical anomaly detection, bounded observation slopes and Monte Carlo scenario frequencies. No learned traffic model is fitted. |
| `SIMULATED` | Shipment, factory stock, schedule and protection state. |
| `ASSUMED` | Coefficients, service targets, proxy budget and navigation fallback. |

`source_indices` are zero-based references into the detailed result's
`real_data_sources` array. Providers, URLs, licences, retrieval timestamps and
checksums remain there without URL duplication in the primary contract.
Observation timestamps are not retrieval times. Missing current feature entries
are omitted from provenance, while warnings and nullable fields remain visible.
Derived feature summaries remain MODEL even when their input observations are REAL.

## Rhine navigation adapter boundary

`external_state.navigation` reports state `NORMAL`, `WATCH`, `RESTRICTED`, `SEVERE`
or `UNKNOWN`, route eligibility, delay contribution, reasons and warnings.
`kind` describes status provenance; `delay_kind` independently describes delay
provenance. The provenance section exposes both `rhine_navigation` and
`rhine_navigation_delay` to preserve that distinction.

No official feed is added by this refinement. Without a valid adapter input, the
state and minute addition are ASSUMED. The largest level/discharge trend penalty
is used, capped by an assumed scenario coefficient; correlated hydrological
signals are not summed. State bands refer to assumed delay minutes, not invented
official water-level or discharge thresholds. Missing usable trends yield UNKNOWN.

`OfficialNavigationSignal` prepares the future adapter boundary: identified
provider/source, issue time, validity window, official state and explicit route
eligibility. A supplied official delay replaces the assumed relationship. If an
official status lacks a delay estimate, the delay remains an ASSUMED fallback;
it never acquires official provenance from the status alone. Invalid or future
signals are excluded with a warning. No BAFU/navigation thresholds are fabricated.

When official status makes the normal route ineligible, the simulation uses the
larger of the reported delay and the assumed finite blockage horizon.
`delay_penalty_min` reports that effective addition; `reported_delay_min` preserves
the supplied official estimate. If the horizon overrides the estimate,
`delay_kind` is ASSUMED while the official state's `kind` is retained. An
ineligible normal route cannot produce on-time arrival, even if the finite
scenario addition fits a distant deadline.

## Compatibility and reproducibility

Python retains deprecated read/input aliases `thermal_exposure_risk` and
`shipment_thermal_exposure_risk`; serialized JSON uses only
`cold_chain_exposure_proxy_risk`. The detailed result retains deprecated
`success_probability` and `action_success_probabilities` for existing consumers:
BUFFER uses sufficient stock, while EXPEDITE/REROUTE use joint lateness within
the warning tolerance **and** proxy within budget (zero when ineligible). These
legacy events differ between actions and never enter recommendation selection.
Neither appears as a field in the primary frontend contract. Legacy journey
artifacts remain separate from this snapshot layer.

The examples reuse the unchanged cached real observations. Only transparent
SIMULATED/ASSUMED shipment and scenario coefficients vary. All runs are offline and
seeded; scenario names never force the selected action.

```sh
.venv/bin/python -m baselhack.logistics demo --scenario normal --output output/logistics-normal.json
.venv/bin/python -m baselhack.logistics demo --scenario disruption --output output/logistics-disruption.json
.venv/bin/python -m baselhack.logistics demo --scenario severe --output output/logistics-severe.json
```

These scenarios demonstrate BUFFER, EXPEDITE and REROUTE respectively. Their
simulated shipment states live in `scenarios/logistics/`; assumption overrides
live in `config/logistics_scenarios/`. They demonstrate decisions under stated
assumptions and do not establish deployment performance.
