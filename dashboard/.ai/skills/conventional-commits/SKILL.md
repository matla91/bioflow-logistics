---
name: conventional-commits
description: Use this skill whenever writing a git commit message in this project, or when reviewing / amending an existing commit message. Triggers for /commit, "commit this", "write a commit message", or any request that results in a new commit. Ensures messages follow the Conventional Commits specification used by the project.
---

# Conventional Commits

All commits follow the [Conventional Commits](https://www.conventionalcommits.org/) specification.

## Format

```
<type>(<optional scope>): <description>

[optional body]

[optional footer(s)]
```

## Types

- `feat:` — a new feature
- `fix:` — a bug fix
- `ui:` — visual/presentation changes that don't add a feature (layout, spacing, widths, sectioning, copy tweaks)
- `ux:` — interaction or flow improvements (form behaviour, navigation, validation messages, helper text)
- `docs:` — documentation only
- `style:` — formatting, whitespace (no code change)
- `refactor:` — code change that neither fixes a bug nor adds a feature
- `perf:` — performance improvement
- `test:` — adding or correcting tests
- `build:` — build system or dependency changes
- `ci:` — CI configuration
- `chore:` — maintenance tasks that don't fit elsewhere
- `revert:` — reverting a previous commit

## Rules

- Description is imperative, present tense: "add login", not "added login" or "adds login".
- No capitalization of the first letter of the description.
- No period at the end of the description.
- Scope is optional and describes the affected area: `feat(auth):`, `fix(billing):`.
- Breaking changes: append `!` after type/scope (`feat(api)!: remove v1 endpoints`) or add a `BREAKING CHANGE:` footer.
- Keep commits short and clean — no body unless genuinely necessary.
- Never add AI agent co-authorship footers (no `Co-Authored-By:` lines).

## Examples

```
feat(billing): add stripe webhook handler
fix(auth): prevent session fixation on login
ui(organizations): wrap form fields in a details section
ux(organizations): add helper text for the slug field
refactor: extract user creation into Action
chore: bump dependencies
```
