# Smartflow C4 plan

## ML priorities

1. **Must have:** paired seeded Monte Carlo, 2,000 journeys per action. Report expected batch delay, slot-miss probability, excursion probability and remaining stock. These are probabilities under an ASSUMED simulation, not validated real-world performance.
2. **Risk model:** gradient-boosted classifier skeleton with honest held-out accuracy/Brier score. Follow up with simulated feature/label generation and ETA quantile regression. Do not claim trained-model accuracy before evaluation.
3. **Gauge anomaly:** align discharge and Mainz/Koblenz gauges, calibrate a consistency check. Negative gauge datum alone is not an anomaly; current skeleton says unverified, not plausible_low.
4. **River forecast:** obtain longest verified history, evaluate chronologically against persistence, report both scores. A persistence-MAE helper exists; no model forecast is currently claimed. This optional priority can be explicitly omitted.

## Demo scenes and story

| Scene | Real evidence | ASSUMED scenario inputs | Expected |
| --- | --- | --- | --- |
| s1_normal_2026-05-10 | Basel 10 May hourly weather; Rotterdam around 5 May | Explicitly simulated normal river value; normal handovers | RUN_AS_PLANNED |
| s2_heat_2026-07-30 | Basel 30 July hourly weather and 39.7 °C daily maximum; Rotterdam around 25 July | Afternoon Basel unload/dock appointment; explicitly simulated river sensitivity | QUARANTINE, QA decides |
| s3_lowriver_2026-10-01 | Kaub −6 cm at 02:45 +02:00 and real hourly weather | Navigation bands suspend barge; cold-store stock covers batch | BUFFER, operator decides |

About three minutes: normal all-green scene → afternoon heat unload/dock fills excursion budget, QA approves quarantine; show an early-unload sensitivity variant → negative-gauge low river stops barge, operator approves stock with reason → close on the log and preserved evidence.

The supplied reference calibration is context, not a test oracle for exact probabilities. Report this implementation's recomputed results. Expected **actions** are enforced in tests. If an action differs, review ASSUMED scenario parameters; never special-case scene IDs in the rule selector. Rehearsal reasons contain no personal data.

## M1 · Shared working skeleton

### Foundation (in order)

#### T1 Implement v1.1 scaffold
Owner: @cfpramod
Needs: nothing
Files: pixi.toml, schemas/, pipeline/, web/, tests/, config/, scenarios/, snapshots/, kit documentation
Done when: pixi setup, contract generation, implemented tests and frontend build pass; all three scenes run with expected actions; unresolved provider/domain policies are explicit failing verification checks.
Notes: Existing shared repository root is the project root. No second nested Git repo.

### Evidence and domain work (parallel after T1)

#### T2 Audit real sources and licences
Owner: unassigned (data work package)
Needs: T1
Files: pipeline/baselhack/loaders/, data/cache/, docs/SOURCES.md
Done when: traffic stations and real-data coverage are audited, provider redistribution/attribution terms recorded, cache provenance checked, and optional long river history found or limitation documented.

#### T3 Validate operating assumptions
Owner: unassigned (domain/process work package)
Needs: T1
Files: config/, scenarios/, docs/DECISION_RULES.md
Done when: Port of Switzerland bands, Basel stop and QA/thermal assumptions have domain evidence; scene appointments and sensitivity parameters are reviewed.
Notes: Coordinate verification.yaml ownership with T2 before editing shared checks.

## M2 · Views and analysis

### Work packages (parallel after T1)

#### T4 Refine UI and offline variants
Owner: unassigned (UX/full-stack work package)
Needs: T1
Files: web/, pipeline/baselhack/api.py
Done when: four views are usable at night, controls select precomputed snapshots, approval/override role checks and persistent log work, and no external request occurs in demo mode.
Notes: UX owns theme/assets; full-stack owns app wiring. Agree file-level ownership before simultaneous edits.

#### T5 Extend ML honestly
Owner: unassigned (ML work package)
Needs: T1
Files: pipeline/baselhack/ml/
Done when: priority 1 is reviewed; priorities 2–4 report measured scores and limitations or are explicitly deferred. Interface changes require an agreed decision line.

## M3 · Acceptance and demo

### Integration (in order)

#### T6 Audit and rehearse
Owner: unassigned (demo owner)
Needs: T2, T3, T4, T5
Files: tests/, docs/plan.md, README.md
Done when: required verification gates have evidence, full pixi test passes, all three scenes work offline, two rehearsals are completed, and sources/limits can be explained.

## Team checkpoints from the brief

| Checkpoint | Done when |
| --- | --- |
| Saturday midday | pixi setup and tests pass; all scene evidence cached; app renders decision; priority 1 works on normal scene |
| Saturday evening | Normal scene chain and offline UI/log work end to end |
| Sunday by 12:00 | Three expected actions, offline mode, two rehearsals |

These are team checkpoints, not enforced deadlines. Unresolved policy/licence gates prevent claiming full acceptance. Demo owner and usernames for unassigned work await the team's handoff. Task status lives in handoff files, not this plan.
