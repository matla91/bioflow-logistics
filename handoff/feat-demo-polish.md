# Smartflow demo polish

Status: done · Updated: 2026-10-04 · Branch: feat/demo-polish · Owner: @matla91

## Goal

Polish the existing two-view Smartflow presentation: stored batch evidence and safe abstention, followed by stored logistics scenarios demonstrating supported operational actions. Leave all changes uncommitted for review.

## State

Ready for review, started from feat/batch-dashboard-integration at 7e85804. Personal origin is matla91/bioflow-logistics. No commits, staging, pushes or merges. Backend policy, Monte Carlo, canonical contracts, dependencies and source databases are unchanged.

## Done

- Confirmed hooks remain active and executable; created the requested local branch.
- Found the previous polished scenario reference on feat/dashboard-json-integration for selective reuse.
- Confirmed existing stored scenario records select BUFFER / EXPEDITE / REROUTE.
- Decoupled visible Smartflow branding from legacy environment names.
- Made QA state primary in the temperature card, with excursion budget and last-reading range comparison secondary.
- Passed 31 Laravel feature tests (325 assertions), 17 batch presentation tests, scoped Pint and middleware PHPStan.
- Built and verified all four batch views in the browser at 1366×768 and 1440×900: no horizontal overflow, QA release "No" visible above the fold, absent/partial evidence explicit, no visible legacy branding, audit collapsed initially.
- Reused the previous scenario dashboard's display explanations and card hierarchy; local buttons now select actual stored records in Normal / Disruption / Severe order. Actions remain backend-selected.
- Added the compact observations → Monte Carlo → deterministic policy → operator recommendation narrative and explicit operator responsibility.
- Verified all three scenario actions and outcome metrics in the actual API and final built browser at both requested sizes. Recommendation and metrics are above the fold; no horizontal overflow, unsafe detection labels or visible BioFlow.
- Independent review identified an unlabeled computed traffic z-score; it now shows its supplied MODEL provenance alongside the REAL traffic count.
- Final checks: 26 frontend tests (17 batch + 9 logistics), vue-tsc, scoped frontend formatting/lint, production build, 31 Laravel tests / 325 assertions, scoped Pint, middleware PHPStan, doc-check and git diff --check all pass. No browser warnings or errors observed.

## Final Batch 001 temperature

- Primary: Human QA review required.
- Observed excursion: 99.5 min observed.
- Secondary comparison: Below 120 min demo excursion budget.
- Last product temperature: 10.9 °C — outside 2–8 °C range.
- Journey complete; 37 readings; QA release authorized: No.

All labels are derived from supplied evidence and the QA flag, not the batch identifier. Other cases preserve 147.7 min / incomplete journey, 0 min / incomplete journey and missing readings / unknown excursion. The backend's null batch recommendations remain null.

## Verified scenario outputs

| Scenario | Backend action | Production continuity | On-time arrival | Mean incoming delay |
| --- | --- | --- | --- | --- |
| Normal | BUFFER | 100% | 99.7% | <0.1 min |
| Disruption | EXPEDITE | 96.6% | 96.6% | 0.3 min |
| Severe disruption | REROUTE | 99.8% | 99.8% | <0.1 min |

These are formatted supplied model frequencies, not new estimates. A mismatched scenario/action, unfavorable metrics, null action, missing action metrics and unfamiliar reasons are covered by frontend regressions; no frontend action selection policy is implemented.

## Files changed

- `dashboard/app/Http/Middleware/HandleInertiaRequests.php`: visible shared Smartflow name independent of technical APP_NAME.
- `dashboard/resources/views/app.blade.php`: initial HTML title Smartflow.
- `dashboard/resources/js/app.ts`: browser page titles Smartflow independent of legacy VITE_APP_NAME.
- `dashboard/resources/js/components/AppSidebar.vue`: Logistics scenarios navigation label.
- `dashboard/resources/css/app.css`: shared assessment color tokens.
- `dashboard/resources/js/pages/BatchAssessment.vue`: subtitle, QA-first temperature hierarchy, secondary budget and last-reading comparison.
- `dashboard/resources/js/lib/batch-display.ts`: evidence-derived temperature presentation, preserved missing/partial states.
- `dashboard/resources/js/pages/Integration.vue`: stored scenario selector, action hero, supplied outcome metrics, pipeline and collapsed evidence.
- `dashboard/resources/js/lib/logistics-display.ts`: display-only reason humanizers and supplied-action metric lookup, safe scenario labels.
- `dashboard/tests/Frontend/batch-display.test.mjs`: QA/evidence presentation regressions.
- `dashboard/tests/Frontend/logistics-display.test.mjs`: backend action preservation and safe scenario presentation regressions.
- `dashboard/tests/Feature/IntegrationTest.php`: legacy application-name branding regression.
- `docs/style-guide.md`: existing visual hierarchy and shared theme token home.
- `docs/decisions.md`: presentation-only scope decision.
- `docs/LOCAL_APP.md`: pointer to this review runtime.
- `handoff/feat-demo-polish.md`: complete review report and startup details.

## Branding changes

Sidebar/header and split authentication layouts consume the shared Smartflow name; initial HTML and client document titles use Smartflow. No visible BioFlow remains in the checked app source or rendered views. The existing Smartflow logo/favicon is retained. Repository URLs, package identifiers, database names and private environment settings retain their technical names.

## Local review runtime

Laravel: http://127.0.0.1:8010/integration/batches and `/integration`.
API: http://127.0.0.1:8002.
Database: `/tmp/demo-polish-review.sqlite3`, a separate clone of the previous batch review database. Its eight original batch rows and schema are unchanged. Three existing validated scenario rows, including their canonical inputs and detailed evidence, were copied unchanged from the prior integration test database; no simulation was rerun. Source indices and immutable hashes are retained.

```sh
PYTHONPATH=pipeline .venv/bin/python -m baselhack.integration serve --database /tmp/demo-polish-review.sqlite3 --port 8002
cd dashboard
DATA_ENGINE_URL=http://127.0.0.1:8002 php artisan serve --no-reload --host=127.0.0.1 --port=8010
```

The scenario records use observations at 2026-09-30T12:00:00Z, simulated shipment conditions, assumed coefficients and seeded Monte Carlo results. They are historical scenario comparisons, not a live disruption feed. The batch v2 cutoff remains 2026-10-03T12:00:00Z. Original environment files and source databases are untouched.

Ignored local screenshots and browser observations live in `.runtime/demo-polish-review/`.

## Remaining demo limits

Historical observations and simulated scenario conditions are explicitly distinct. These outputs demonstrate a deterministic policy under assumed coefficients, not a validated real-time incident detector or pharmaceutical QA release. Review servers must be running for both pages. No new supported batch intervention was manufactured.

## Next

Review the uncommitted working tree and local demo. Do not commit or push without subsequent authorization.

## Resume

Review the completed uncommitted presentation polish on feat/demo-polish. Read this handoff and preserve all stored/backend recommendations. No commit or push is authorized.
