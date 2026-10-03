# Smartflow dark application theme

Status: done · Updated: 2026-10-04 · Branch: feat/demo-polish · Owner: @matla91

## Root cause and change

Started at bf0c563. Batch assessment and Logistics scenarios already used the fixed dark assessment palette. The starter application shell still used light semantic tokens whenever its saved/system appearance resolved to light; the polish commit did not activate the existing dark context.

Authenticated HTML now emits the dark class and fixed-theme marker before first paint. AppShell maintains that context across Inertia navigation, including login/logout. Appearance handling preserves guest preferences while the authenticated shell stays dark; the resolved theme also keeps teleported menus and toast components consistent. Existing dark semantic tokens reference the unchanged assessment palette. No new color literals or parallel theme system were introduced.

Business pages, backend logic, contracts, model versions and committed evidence fixtures are unchanged.

## Files

- `dashboard/resources/views/app.blade.php`: authenticated root and initial background.
- `dashboard/resources/js/components/AppShell.vue`: persistent shell theme lifecycle.
- `dashboard/resources/js/composables/useAppearance.ts`: fixed authenticated appearance and guest restoration.
- `dashboard/resources/css/app.css`: existing dark semantic tokens reuse assessment colors.
- `dashboard/tests/Frontend/appearance.test.mjs`: seven appearance regressions.
- `docs/style-guide.md`: fixed dark shell behavior.
- `docs/decisions.md`: presentation decision.
- `handoff/fix-smartflow-dark-theme.md`: this handoff.

## Validation

- `node --test tests/Frontend/*.test.mjs`: 33 passed, including the existing 26 business presentation checks.
- `npm run types:check`: passed.
- `vp check` scoped to app.css, AppShell.vue, useAppearance.ts and appearance.test.mjs: four formatting checks and three lint checks passed without warnings.
- `php artisan test --compact tests/Feature/IntegrationTest.php tests/Feature/DashboardTest.php tests/Feature/Auth/AuthenticationTest.php`: 21 passed, 252 assertions.
- `npm run build`: passed.
- Documentation check, whitespace check and mandatory staged/push privacy guards: passed before publication.

## Browser review

Actual Laravel authentication and production frontend assets were checked in local Chromium at 1366×768 and 1440×900. The fresh checkout had no prior review database, so a local read-only HTTP replay served the unchanged committed output fixtures. No simulation or assessment model was run, and no existing evidence database was changed.

Both resolutions have a navy sidebar, dark header and canvas, readable Smartflow branding/footer, a raised cyan active navigation state, subdued inactive navigation, and no white frame or horizontal overflow. Eight screenshots cover Batch 001 and Normal/Disruption/Severe logistics scenarios at both sizes. All four batch cases were checked during navigation. QA review and release No remain visible; observed durations, missing evidence and incomplete journeys retain their existing meaning. Stored actions remain BUFFER, EXPEDITE and REROUTE, with the recommendation visible above the fold. No browser warnings/errors or loss of the authenticated dark class was observed during navigation with a light OS and saved light preference.

Screenshots and browser measurements were saved outside tracked code for review. This visual check does not independently revalidate the absent original engine database. Pull this branch and rebuild the dashboard assets before the demo. No PR or merge is part of this task.
