---
name: actions-dto-architecture
description: Use this skill when writing or reviewing backend PHP code that involves business logic, controllers, models, or data passed between layers. Triggers when creating or modifying controllers, Action classes, form requests, jobs, listeners, console commands, or any code that coordinates domain behavior. Also use when deciding where a piece of logic belongs, when introducing a new data structure passed between layers, or when a controller or model is growing beyond thin delegation / persistence concerns.
---

# Actions + DTOs architecture

## Core rules

- **All business logic lives in Actions.** Never put business logic in controllers or models.
    - Controllers: accept input → build DTO → invoke Action → return response.
    - Models: persistence only (casts, relationships, scopes). No behavior that coordinates multiple models, performs side effects, or encodes domain rules.
- **Data flows through DTOs.** Never pass raw arrays between layers.
    - All DTOs use `spatie/laravel-data`.
    - Controllers convert request input into a DTO before calling an Action.
    - Actions accept DTOs as input and return DTOs (or domain models) as output.
- **Dependency arrow points inward.** Domain code never depends on HTTP.
    - Actions and DTOs must not import `Illuminate\Http\*`, `Request`, `Response`, or controller/route helpers.
    - If an Action needs request data, receive it as a DTO — the controller builds it.
    - Outer layers (HTTP, Console, Jobs) depend on inner layers (Actions, DTOs, Models). Never the reverse.

## Layering

```
HTTP (Controllers, FormRequests)  ──▶  Actions  ──▶  Models / Services
                                      ▲
                                      │
                                     DTOs
```

- Controllers are thin.
- One Action = one business operation, with a single public method `handle`.
- Compose Actions from other Actions when needed.

## What NOT to do

- No service classes that accumulate arbitrary methods — prefer one Action per operation.
- No `Request`, `auth()`, `session()`, or `request()` helpers inside Actions.
- No associative arrays as parameters or return types where a DTO would do.
- No business logic on Eloquent models (`$user->upgradeToPremium()` belongs in an Action).
