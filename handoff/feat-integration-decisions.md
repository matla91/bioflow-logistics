# Named logistics human decisions

## State

Status: done. Implemented and validated on `matla91/bioflow-logistics:feat/demo-polish`, starting at b59486a. Scope and behavior are documented in [INTEGRATION_DECISIONS.md](../docs/INTEGRATION_DECISIONS.md). The feature is ready for a single reviewed commit on this branch; no PR or merge is authorized.

## Done

- Added external-hash decision persistence and fresh API validation without Laravel shipment linkage.
- Reused existing action roles, verdict dialog and shared human-decision log presentation.
- Added exact-hash isolation, required reasons and restricted demo reopening.
- Added backend and frontend regressions, including source failure, mismatched evidence, role rejection, duplicate submission, new-hash history and demo reset.

## Validation

- Full Laravel suite: 120 tests, 118 passed, 747 assertions, two existing feature-disabled skips.
- Frontend: all 39 tests passed. TypeScript, scoped frontend formatting/lint, PHPStan level 8, scoped Pint and the production build passed.
- Browser rehearsal at 1366×768 and 1440×900: Normal BUFFER approval, Disruption EXPEDITE approval and REROUTE override, Severe REROUTE approval, reload persistence, scenario isolation and reset all passed. Operator controls were above the fold. Dark shell, no horizontal overflow, Batch assessment and shipment-console approval/override/reset were verified; no browser errors or warnings were observed.
- Browser validation used an isolated Laravel rehearsal database and a read-only HTTP replay of the unchanged committed logistics/batch results. The available engine database had no logistics assessment records, so live populated-engine validation remains outside this rehearsal. No scientific calculation or engine record was changed to populate the test.
- Documentation drift and `git diff --check` passed; staged and pre-push privacy checks are required before publishing.

## Next

- Apply the additive migration to the Laravel database and rebuild the dashboard when running this branch in another environment. Keep the integration read API running.
- Rehearse with Operator for BUFFER and Logistics for EXPEDITE/REROUTE; reopen with the recorded role. A new assessment hash receives no inherited decision. The read API does not expose a unique latest revision ordering for equal scenario cutoffs, so existing explicit record selection is preserved.

## Exact changed files

Backend and configuration:

- `dashboard/app/Actions/Integration/ReadStoredAssessment.php`
- `dashboard/app/Actions/Integration/RecordIntegrationDecision.php`
- `dashboard/app/Actions/Integration/ReopenIntegrationDecision.php`
- `dashboard/app/Actions/Shipments/BuildShipmentConsole.php`
- `dashboard/app/Data/HumanDecisionData.php` (renamed and generalized from `ShipmentDecisionData.php`)
- `dashboard/app/Data/IntegrationAssessmentData.php`
- `dashboard/app/Data/IntegrationDecisionInputData.php`
- `dashboard/app/Data/ShipmentConsoleData.php`
- `dashboard/app/Data/ShipmentListItemData.php`
- `dashboard/app/Http/Controllers/IntegrationController.php`
- `dashboard/app/Http/Controllers/IntegrationDecisionController.php`
- `dashboard/app/Http/Requests/StoreIntegrationDecisionRequest.php`
- `dashboard/app/Models/IntegrationDecision.php`
- `dashboard/config/integration.php`
- `dashboard/database/migrations/2026_10_04_000000_create_integration_decisions_table.php`
- `dashboard/routes/web.php`

Frontend and tests:

- `dashboard/resources/js/components/console/DecisionLog.vue`
- `dashboard/resources/js/components/console/IntegrationDecisionPanel.vue`
- `dashboard/resources/js/components/console/VerdictDialog.vue`
- `dashboard/resources/js/lib/integration-decisions.ts`
- `dashboard/resources/js/pages/Integration.vue`
- `dashboard/resources/js/types/console.ts`
- `dashboard/resources/js/types/integration-decisions.ts`
- `dashboard/tests/Feature/IntegrationDecisionTest.php`
- `dashboard/tests/Frontend/integration-decisions.test.mjs`

Documentation:

- `docs/BUILD_INTEGRATION.md`
- `docs/DATA_FLOW.md`
- `docs/INTEGRATION_DECISIONS.md`
- `docs/decisions.md`
- `docs/design.md`
- `docs/implementation-laravel.md`
- `handoff/feat-integration-decisions.md`

## Boundaries

Python calculations, generated contracts, stored engine records, batch assessment logic, proxy/QA semantics and shipment decisions are unchanged. Full API snapshots are retained for audit; hashes stay verbatim. Migration applies only to Laravel. No PR or merge is authorized.
