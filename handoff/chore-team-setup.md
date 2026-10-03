# Handoff: T1 Current Affairs C4 v1.1 scaffold

Status: in progress · Updated: 2026-10-03 · Branch: chore/team-setup · Last owner: @cfpramod

## Goal

Share the C4 concept and provisional repository scaffolding for Current Affairs to work through together under the kit's hard rules. The user clarified that the intent is team concept-sharing, not presenting an already-completed individual build.

## State

The scaffold is provisional material for team review, not an agreed final implementation. The user approved publishing a clean replacement repository named `current-affairs`, with the project name Current Affairs. Repository-local author and committer identities use @cfpramod's GitHub noreply address. The replacement starts from a fresh commit of the previous scaffold's tracked files; the previous published repository and its history are preserved separately. The initial clean copy passed the staged guard, commit hooks, documentation check and full-history privacy audit. Branding updates are being checked before publication. No PR merge is authorized. Team usernames are pending.

## Done

- Preserved the original kit, repository and remote; configured active executable privacy hooks.
- Applied v1.1: snapshots instead of ignored out, Pydantic models/part contracts in the single interface source, generated JSON Schemas and TypeScript, pixi tasks and lockfile, consolidated kit design/plan/SOURCES homes, tau 360/360, strict UTC-hour weather lookup.
- Cached real May/July ambient and October river/weather evidence with provenance. Historical normal river is separately simulated as authorized. Requested September cache filename retains metadata disclosing actual coverage starts 2 September.
- Implemented seeded journey/thermal/recovery simulation, 2,000 paired runs per action, priority-first rules, template explanation and optional ML extension modules.
- Built four-view React app and local FastAPI snapshot/log server. Precomputed independent ambient warm/cold, dock delay, river sensitivity, readiness drift and stock controls; early heat unload avoids quarantine in this model.
- Logs enforce role labels, reasons and chosen override action; they persist complete immutable evidence under decision SHA-256. Runtime logs/evidence stay ignored. Browser labels are demo roles, not authentication.
- Ran pixi setup and complete data-to-decision chain. Expected actions: normal RUN_AS_PLANNED, afternoon heat QUARANTINE, low river BUFFER. Current baseline simulated excursion probabilities are 0, 0.7735 and 0 respectively; report those as model output, not the brief's reference values or real-world accuracy.
- Validated all baseline/variant artifact contracts and generated-file drift. Implemented test subset: 27 passed. Full suite intentionally has seven verification failures. Frontend build/format, Python lint/format and strict doc check pass.
- Content privacy audit of the scaffold passes. A clean replacement history avoids the historical identity finding from the separate old repository; no merge is authorized.
- Obsolete v1 draft files remain only in ignored data/raw/v1-draft. The official pixi executable is project-local in ignored .pixi/bin.
- Expanded README.md with the implemented components, repository map, run commands, extension skeletons and honest validation status. Corrected the claim that the uncommitted demo artifacts were already committed.
- Set repository-local Git email to the verified GitHub noreply identity; left global settings unchanged. At the user's subsequent direction, left published history and stash untouched.
- Reframed README.md around the shared concept deck and team contributions. Existing runnable code, screens and outputs are provisional placeholders, with scope, stack, assumptions and assignments open for team review. Read the deck at the link in the team chat. Do not continue building additional features without a team-selected task.

- Preserved the user-edited README and updated project-facing branding to Current Affairs. Verified 27 implementation tests, Python lint/format, frontend format/build and documentation checks before the v1 branch push.

## Next

Review the shared concept with the team before developing more features. Existing implementation work is scaffolding to inspect and reshape, not a finished team product.

1. Obtain teammates' GitHub usernames and agreed areas/task assignments. Update TEAM.md and plan owners. Repository-local noreply identity is already set.
2. Use https://github.com/cfpramod/current-affairs for new collaboration. Keep the previous repository separate; do not bring its old commits into the clean replacement. The old repository still contains historical personal metadata.
3. Domain/data owners resolve config/verification.yaml: navigation bands, Basel high-water stop, traffic station mapping, optional river history, organiser MIT confirmation, supplemental OpenStreetMap geometry conditions, and September-start evidence if citing that date.
4. Confirm team review policy and demo owner. The current one-reviewer rule is a proposal.
5. Review the v1 setup PR before merging. The new commit uses noreply identity and staged/push hooks remain active. The deliberate verification failures must be disclosed; do not merge with unresolved required checks.

## Commands

Use pixi, or the local executable .pixi/bin/pixi if pixi is absent from PATH. Pixi installs its locked environment locally. Run setup, test, contracts, variants, all, or demo with SCENE=s1_normal_2026-05-10. The behavior-only test command is pixi run test -- -m 'not verification'; it does not certify outstanding domain gates. Demo serving makes no external requests after setup/build; controls select independently precomputed snapshots rather than combining arbitrary values.

## Files

- README.md: actual quick start and task commands.
- docs/design.md: concept, simulator, UI and contract links.
- docs/plan.md: tasks, ML priorities, scenes, story and team checkpoints.
- docs/SOURCES.md: source evidence, provider licences and caveats.
- docs/DECISION_RULES.md: action rules and approval roles.
- pipeline/baselhack/interfaces.py: single contract source.
- pixi.toml and pixi.lock: tasks and resolved environment.
- config and scenarios: all ASSUMED model/scene values.
- snapshots: baseline and bounded offline variant evidence.
- TEAM.md: GitHub usernames, work boundaries and agreements.

## Decisions / limitations

The explicit v1.1 brief supersedes v1.0; kit hard rules prevail. Optional ML priorities 2–4 remain extension skeletons and do not claim trained-model performance or gauge consistency without evidence. There is no production authentication or real QA release workflow. Verification failures are deliberate per the brief and must not be hidden. The clean replacement history passes the local privacy audit; the seven domain/data gates remain unresolved, so this is not a green release or demo tag.

## Resume prompt

> Continue T1 Current Affairs C4 v1.1 on chore/team-setup. Read this handoff, TEAM.md and docs/plan.md. Accept teammate usernames/assignments and review the provisional v1 scaffold together. Use the clean current-affairs repository; the repository-local noreply identity is configured. Do not import the old repository history. Preserve kit hard rules and never merge without approval for that PR.
