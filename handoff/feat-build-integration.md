# Build integration

Status: committed and pushed · Updated: 2026-10-03 · Branch: feat/build-integration

## State

Read the local session handover, refreshed team refs and assembled dashboard ec9a145 alongside the engine. Origin/ML at 74e4179 has no new ML implementation. No branch histories were merged. Added stored-data logistics worker, immutable input/result persistence, local read API and Laravel analysis page; existing shipment decisions remain separate. Builder inputs are separate files: docs/implementation-laravel.md and docs/implementation-ml.md, linked by docs/BUILD_INTEGRATION.md. Product branding is now Smartflow; generated transparent mark is in the dashboard and React public assets. Repository URL and data identifiers are unchanged. The local session-handover remains untracked.

## Validation

- 246 Python tests passed; seven pre-existing domain/licence verification gates deselected.
- Scoped Ruff lint/format, generated-contract check, React frontend build, strict doc-check and diff whitespace checks passed.
- Local API runs on port 8002; live requests returned three scenario assessments and one fixture containing 18 batches and 12 shipments.
- Installed project-local PHP/Composer and frontend dependencies; generated dependency locks. Laravel: 58 tests passed, two skipped; Vue type check and production build passed. Fixed duplicate simulated lot IDs and production-only HTTPS forcing. Browser login and live analysis page verified without browser errors. App runs at http://127.0.0.1:8000; API at port 8002. Restart/setup commands: docs/LOCAL_APP.md.
- Staged guard initially flagged the nested environment template and three password-rule Vue attributes. Template moved to dashboard/env.example and Composer setup updated. Externally prepared allow annotations appeared locally and were included; the staged and push guards passed.
- Full-history audit additionally flags metadata and content on fetched dashboard history. Snapshot assembly did not import those commits. No history rewritten or merge performed. Integration commit e23401a and data commit 80f9bf0 were pushed successfully.

## Branding and builder delivery

- Product renamed to Smartflow in Laravel, React demo, current project docs and local environment. Generated transparent logo is in both public asset directories, with prompt in docs/style-guide.md.
- Separate briefs: docs/implementation-laravel.md and docs/implementation-ml.md. Delivery defaults to file links in chat; no teammate message or issue was sent without a specified destination.
- Rechecked 58 Laravel tests (two skipped), 246 Python tests (seven verification gates deselected), both frontend builds, Vue types, scoped Pint and strict docs. Browser shows Logistics analysis - Smartflow with a loaded logo and no errors.
- Externally prepared allow annotations in Register.vue, ResetPassword.vue and Security.vue were included; no agent-added override was used. Staged and push guards passed. Composer lock remains local because generated dependency metadata contains real author emails; it was not hand-edited.

## Data flow diagram

Added docs/DATA_FLOW.md with the product flow and current local implementation, linked from BUILD_INTEGRATION.md. ERP is explicitly a synthetic stand-in; engine and Laravel stores remain separate. Latest batch-linked assessment selection and evidence-bound decisions are builder work.

## Next

Both branches are published at the user’s explicit request. Do not merge. Keep the local session-handover untracked. Laravel runtime checks now pass locally; maintain them as batch workflows are added. ML owner implements batch-linked assessments; Laravel owner adds operational models/pages and imports linked assessments after that contract is available. Keep engine and Laravel databases separate until migration ownership/schema alignment is agreed. No merge authorized.

## Batch ML fixtures

Generator, config, templates and tests are included on this integration branch. Generated package is published separately on data/simulated-shipment-training: 1,200 batches, 650 shipments, 9,637 readings, twelve scenario families and chronological grouped splits. Observable features and hidden outcomes are separate. Full behavior suite: 246 passed; seven existing verification gates deselected. The five-minute presentation remains a later task; the supplied review needs corrections to framework versions, action sets and batch stock availability.
