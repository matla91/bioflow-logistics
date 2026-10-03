# Team Manux C4 design

## Concept and persona

Hack am Rhein 2026, Challenge 4: **From a Rhine Signal to Action: Manufacturing in the BioValley**. A high-value 2–8 °C pharmaceutical intermediate travels from Shanghai to a production site near Basel. The night-shift operator for reactor R2 asks: “My next batch charges at 06:00. Will the material be here, and is it still good to use?”

Real water levels and weather, plus eventually verified traffic, combine with simulated container positions, handover times, product temperature, readiness and stock. Rules pick, Monte Carlo/ML supplies probabilities, optional LLM wording only explains existing evidence, and people decide. Logistics approves Expedite/Reroute; QA alone decides quarantine or release. Operator can approve planned use or stock.

The 120-minute cumulative allowance outside 2–8 °C and every operational/thermal assumption stay in config or scenario YAML. Actual stability data and QA policy are required for real deployment. [DECISION_RULES.md](DECISION_RULES.md) is the authoritative action table and tie-break home.

## Journey and model

Shanghai → refrigerated sea (~35 days) → Rotterdam exposed repack → refrigerated truck → exposed barge transfer → Rhine barge via Kaub (~5 days × river factor) → Basel exposed unload → refrigerated last mile → exposed site dock → cold store / R2.

Route durations and triangular/normal distributions are in config/route.yaml. Scene start is Rotterdam; a historical simulated sea leg ends there. Coarse position anchors are model inputs, not actual vessel tracking. Scene YAML may specify a refrigerated Basel port appointment wait; the simulator accounts for elapsed thermal time while waiting.

Seeded numpy RNG drives durations and reactor readiness. Same seed, config, cache and installed dependency versions produce byte-identical canonical timeline JSON. The recorded cadence is 5 minutes, or 1 hour at sea; exposed integration also splits at UTC-hour boundaries.

Thermal law: T_next = target + (T − target) × exp(−dt / tau). Both tau_reefer and tau_exposed are **360 minutes, ASSUMED**, with configured 5 °C refrigerated setpoint. Exposed targets use exact real hourly ambient at the place and time plus any explicitly simulated offset. Normalize timestamps to UTC; lookups zero minutes, seconds and microseconds. **A missing hour raises an error**, with no fallback or stale-value carry-forward. MeteoSwiss hourly values identify interval endings; this demonstration follows the supplied reference's timestamp-hour lookup convention.

Exact threshold-crossing integration accumulates only minutes strictly outside the configured band. Refrigerated recovery still counts. After docking, simulate cold-store recovery until the product returns to the band or the configured horizon is reached. Physical ETA remains dock completion; post-arrival thermal history remains evidence for QA.

At barge departure use the latest preceding Kaub reading unless the scenario supplies an explicitly simulated river sensitivity value. Configured bands apply; a suspended barge has null ETA. A configured finite delay cap supports action comparison without inventing an arrival. Basel high-water stop and real traffic factors remain verification gates. Reactor readiness is the charge time plus seeded drift; BUFFER consumes configured batch stock.

EXPEDITE reduces exposed handover/dock waits by the configured factor and uses the next truck-slot wait. REROUTE substitutes a sampled truck and exposed extra handover. BUFFER serves the slot from stock while the incoming lot continues; QUARANTINE removes the lot from use, with stock potentially covering the batch.

## Shared contracts and layers

**The sole contract source is [interfaces.py](../pipeline/baselhack/interfaces.py)**: Pydantic models, action vocabulary and part signatures. `pixi run contracts` generates JSON Schemas in schemas/ and TypeScript in web/src/interfaces.ts. Neither generated output is edited by hand. Contract changes get a line in decisions.md in the same commit.

Cached real data + configs → scenario.json → timeline.json → risk.json → decision.json → human decision → log.json. All artifact files live in snapshots/<scene_id>/; real cache lives in data/cache/. Artifacts carry sources, and decision reasons/rejections carry both source and time. Simulated river sensitivity lives outside observed gauge arrays. Optional outputs that are not evaluated remain empty and explicitly described.

The local FastAPI server serves built web assets and snapshots JSON only, with append-only log POSTs. Approval/override checks the role label, rejects stale decision IDs, requires reasons and an override action, and hashes canonical decision JSON. It saves the whole scenario/timeline/risk/decision evidence set under that hash before appending. Hash collisions with different evidence are rejected. Runtime rehearsal logs and evidence copies stay local; production auth and release workflows are future work.

## Four views

1. Operator: journey scrubber/position, product trace with shaded handovers and 2–8 °C band, excursion bar and decision card.
2. Decision: recommendation, rejected options, numbered cited evidence, change conditions, approve/override with reason and required role.
3. Scenario controls: scene picker and bounded precomputed sensitivity variants; demo controls select a baseline or an independently precomputed sensitivity snapshot. Ambient, dock delay, Kaub sensitivity, reactor drift and stock controls are bounded; they do not combine arbitrarily. The early-unload button shifts the simulated shipment appointment and compares the same heat-day observations. No external request or implied live rerun occurs.
4. QA: lot, full simulated thermal history, recommendation and evidence-linked log.

Basel-local timestamps are displayed with explicit timezone formatting; artifacts stay UTC internally. A shared neutral theme is in web/src/theme.css. Demo mode uses local files and localhost log writes only, with no external network/CDN/LLM calls. Template explanation is always available. Browser roles are demo labels, not authentication.

Work boundaries and people live in [../TEAM.md](../TEAM.md). Tasks, ML priorities, scenes and checkpoints live in [plan.md](plan.md). Provider evidence, licences and caveats live in [SOURCES.md](SOURCES.md).
