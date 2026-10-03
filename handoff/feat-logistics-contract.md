# Logistics frontend contract refinement

Status: complete, local changes only
Owner: @matla91
Branch: feat/basel-logistics-layer

## Result
- Separate production continuity, exact-deadline arrival and ambient exposure proxy dimensions for every action.
- Canonical cold_chain_exposure_proxy_risk in JSON; deprecated read/input aliases and legacy success metrics remain in detailed output only.
- Deterministic policy, explanations for every alternative and demonstrated paired-seed sensitivity changes.
- Concise REAL/OFFICIAL_FORECAST/MODEL/SIMULATED/ASSUMED provenance; evidence quality capped at MEDIUM and reduced to LOW with gaps or warnings.
- Navigation adapter boundary with no new official feed; assumed fallback uses the maximum correlated level/discharge component.
- Effective blocked-route delay matches its exported provenance; reported official delay is retained separately.
- Primary frontend contract and detailed diagnostics; regenerated JSON schemas and TypeScript.
- Normal/disruption/severe demonstrate BUFFER/EXPEDITE/REROUTE without forcing outcomes by scenario name.
- Unchanged cached real observations; scenario differences are exclusively SIMULATED/ASSUMED.

## Validation
- Complete suite: 222 passed, 7 failed, one existing Starlette deprecation warning (11.82 seconds).
- The seven failures are unchanged verification gates: navigation_bands, basel_high_water, traffic_stations, river_history, licence, data_licences, september_start.
- 97 new targeted cases in four test files cover comparable dimensions, recommendations, alternatives, sensitivity, confidence, provenance, navigation, ambient-only QA guardrails, terminology and offline reproducibility.
- Ruff lint/format, generated-contract check, strict doc-check and git diff --check pass.
- Six named demo primary/detailed JSON files validate against their schemas.
- HEAD remains 3020ca5; nothing staged, committed or pushed.

## Reproduce
Run from the repository root:

```sh
.venv/bin/python -m baselhack.logistics demo --scenario normal --output output/logistics-normal.json
.venv/bin/python -m baselhack.logistics demo --scenario disruption --output output/logistics-disruption.json
.venv/bin/python -m baselhack.logistics demo --scenario severe --output output/logistics-severe.json
```

Add --detailed and choose a different output path for full source metadata, coefficients and risk drivers.
The schema is schemas/logistics-frontend.schema.json. docs/LOGISTICS_CONTRACT.md is the contract and policy reference.

## Limits and next work
No official navigation forecast/status feed is integrated. No learned traffic model is fitted.
Ambient weather observations alone do not establish actual product-temperature excursion, pharmaceutical quality, or QA release status.
The prototype assumes packaging autonomy and transport relationships; it does not establish deployment performance.
Resolve verification gates only with separate evidence-driven work. Do not commit or push without a new explicit instruction.

## Changed files
- `README.md`
- `config/logistics.yaml`
- `config/logistics_scenarios/disruption.yaml`
- `config/logistics_scenarios/normal.yaml`
- `config/logistics_scenarios/severe.yaml`
- `docs/LOGISTICS_CONTRACT.md`
- `docs/SOURCES.md`
- `docs/decisions.md`
- `docs/design.md`
- `handoff/feat-logistics-contract.md`
- `output/logistics-demo.detailed.json`
- `output/logistics-demo.json`
- `output/logistics-disruption.detailed.json`
- `output/logistics-disruption.json`
- `output/logistics-normal.detailed.json`
- `output/logistics-normal.json`
- `output/logistics-severe.detailed.json`
- `output/logistics-severe.json`
- `pipeline/baselhack/interfaces.py`
- `pipeline/baselhack/logistics.py`
- `pipeline/baselhack/output/__init__.py`
- `pipeline/baselhack/output/frontend.py`
- `pipeline/baselhack/simulation/__init__.py`
- `pipeline/baselhack/simulation/delay.py`
- `pipeline/baselhack/simulation/navigation.py`
- `pipeline/baselhack/simulation/recommendation.py`
- `pipeline/baselhack/simulation/shipment.py`
- `pixi.toml`
- `scenarios/logistics/disruption.json`
- `scenarios/logistics/normal.json`
- `scenarios/logistics/severe.json`
- `schemas/logistics-assumptions.schema.json`
- `schemas/logistics-frontend.schema.json`
- `schemas/logistics.schema.json`
- `schemas/shipment-state.schema.json`
- `tests/test_logistics_demos.py`
- `tests/test_logistics_dimensions.py`
- `tests/test_logistics_frontend.py`
- `tests/test_logistics_output.py`
- `tests/test_logistics_recommendation.py`
- `tests/test_logistics_simulation.py`
- `web/src/interfaces.ts`
