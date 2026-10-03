# Dashboard readability pass

Status: done
Branch: feat/dashboard-json-integration

## Goal
Improve the existing BioFlow Vue dashboard's first-screen hierarchy and explanation formatting for the jury demo, using only the supplied logistics result. No decision/model/schema/output/dependency/authentication changes and no commit or push.

## State
The revised dashboard is implemented and open in a local Laravel preview on port 8080. No dependency installations or toolchain changes were needed.

## Done
- Confirmed NORMAL selects BUFFER, DISRUPTION selects EXPEDITE and SEVERE selects REROUTE.
- Kept incoming mean lateness separate from factory lateness and evidence quality separate from simulation frequencies.
- Identified remaining journey time as the correct meaning of planned_remaining_min.
- Added selected-action operational KPIs, compact signals and prominent action comparison.
- Collapsed provenance, limitations and policy; original explanation and counterfactual strings remain available under policy details.
- Added deterministic display helpers with exact known-format parsing and unchanged-text fallback.
- Nine formatter tests pass. pnpm check, pnpm types:check, pnpm build and all three Dashboard feature tests pass.
- Browser verification confirmed NORMAL → BUFFER, DISRUPTION → EXPEDITE and SEVERE → REROUTE with the selected action's metrics.
- At 1366 × 768, the action comparison begins on the first screen. At 390 × 844, the page has no horizontal overflow. Temporary viewport overrides were reset.
- Audit sections are closed by default; expanding evidence exposes all four provenance kinds. No browser console errors were observed.
- All supplied explanation/counterfactual strings match the deterministic formatter; none required the unchanged-text fallback. Original strings remain available in the policy audit.

## Validation
- `pnpm run check`: pass, 83 files formatted, no lint warnings or errors in 72 files.
- `pnpm run types:check`: pass.
- `pnpm run build`: pass.
- `php artisan test tests/Feature/DashboardTest.php`: pass, 3 tests / 30 assertions.
- `node tests/Frontend/logistics-display.test.mjs`: pass, 9 tests.
- pnpm commands used execution-only `--config.verify-deps-before-run=false` to use the existing dependencies without pnpm 11 attempting an automatic install. No dependencies or configuration were changed.

## Review
- Local preview: http://127.0.0.1:8080/dashboard (Laravel server left running).
- Changed files: Dashboard.vue, logistics-display.ts, its frontend tests and this handoff.
- No remaining known UX or semantic blocker. Incoming lateness remains distinct from factory lateness; counterfactuals describe tested examples rather than universal thresholds.
- All changes remain uncommitted. No commit or push was performed.
