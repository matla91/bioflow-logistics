# Basel data and logistics simulation

Status: done
Owner: @matla91

## Goal
Add real Basel Rhine 100089, traffic 100006 and MeteoSwiss BAS ingestion,
historical features and explainable Monte Carlo shipment/action risk output.

## Done
- Inspected existing scaffold; preserve existing journey artifacts and consumers.
- Added shared observation, feature, shipment, assumption and result contracts.
- Provider audit identifies a common historical window on 30 September 2026.
- Local Git setup and privacy hooks enabled; no remote or upload requested.
- Ingestion, feature and paired Monte Carlo implementations are present.
- Cached real provider subsets and separate simulated demo/config now run end to end.
- JSON output includes provenance, feature evidence and explicit proxy limitations.
- Added 98 focused tests covering ingestion, features, simulation and JSON boundary.
- Full regression: 125 passed, 7 existing verification gates deselected.
- Ruff, generated-contract checks and strict documentation check pass.
- Two independent CLI runs produced byte-identical demo JSON.
- Live traffic query confirms the demo station total; source metadata/units audited.
- Independent review fixes output revalidation and partial-coverage limitations.

## Next
- No required implementation work remains for this request.
- Optional follow-up: validate coefficients/route representation and packaging
  assumptions with the domain team before claiming operational prediction quality.
- Existing policy/licence/navigation verification gates remain open in the original
  verification config. They were preserved and are outside this layer's completion.
- Work is local only; no remote, push, pull request or merge requested.

## Decisions and limits
- Additive contracts; new result is separate from existing Risk artifact.
- Thermal output is ambient degree-minute exposure after assumed protection expires;
  it does not establish actual product temperature or product excursions.
- BUFFER serves the factory from assumed stock; incoming shipment exposure continues.
- Source cache is retrospective: provider publication-time history is unavailable.
- Native pixi was unavailable here; the declared package extras were installed into
  a local virtual environment using the preinstalled scientific stack. Validation
  ran with Python 3.14.6 and NumPy 2.4.6; pixi remains the project's pinned setup.
- The existing API tests require a test run outside sandbox restrictions in this
  environment; the full non-verification suite passed in that context.

## Run
`pixi run logistics-demo` writes output/logistics-demo.json. Locally verified:
`.venv/bin/python -m baselhack.logistics demo --output output/logistics-demo.json`.
`pixi run logistics-test` runs the new focused tests. Full regression:
`.venv/bin/python -m pytest -q -m 'not verification'`.

## Demo results under assumptions
- Mean factory lateness: 24.701954253897927 minutes.
- Delay risk beyond 15-minute tolerance: 0.5925.
- Ambient exposure proxy risk: 0.8265.
- BUFFER/EXPEDITE/REROUTE success: 1.0 / 0.9235 / 0.354.
- BUFFER assumes sufficient stock and does not reduce incoming shipment exposure.

## Resume
Read this handoff, interfaces.py, config/logistics.yaml and docs/SOURCES.md. The
requested layer is complete; reproduce the offline demo or extend it without
changing the existing journey artifacts. Never relabel scenario assumptions as
observations or ambient exposure as actual product-temperature excursions.
