=== available composer commands ===

## Composer commands

- `composer pint` – Format code with Laravel Pint.
- `composer test:pint` – Check code formatting without making changes.
- `composer rector` – Apply automated code refactoring with Rector.
- `composer test:rector` – Show Rector changes without applying them.
- `composer refactor` – Run Rector, then Pint, to refactor and format code.
- `composer pest` – Run all Pest tests in parallel.
- `composer test:types` – Run PHPStan static type analysis.
- `composer test:type-coverage` – Check that type coverage is met using Pest.
- `composer test` – Run all quality checks: Pint test, Rector test, PHPStan, Pest tests.
- `composer agent:test` – Run the same quality checks with agent-friendly output (machine-readable Pint and PHPStan, no progress bars). Prefer this over `composer test` when running the suite yourself; its sub-commands are `agent:pint`, `agent:rector`, `agent:types`, `agent:type-coverage` and `agent:pest`.

After writing PHP code, run `composer refactor` to apply formatting and code quality rules.
