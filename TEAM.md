# Smartflow

Challenge 4: From a Rhine Signal to Action: Manufacturing in the BioValley.
Repository: https://github.com/cfpramod/current-affairs

## People and ownership

| GitHub username | Agreed work | Files or areas |
| --- | --- | --- |
| @cfpramod | T1 repository scaffold | Shared foundation and collaboration docs |

Teammate usernames, task assignments and demo owner await the team's handoff. No personal names, contact details or profile levels belong here.

| Work package | File boundaries |
| --- | --- |
| UX | web theme/design assets and four-view design; coordinate app edits with full stack |
| Full stack | web application wiring, local API/logging, explanation integration |
| Data | loaders, scenario builder, simulator, rules, cache and snapshots |
| ML | ml modules and risk generation |
| Domain/process | config values, scenario parameters, decision rules and demo story in plan |

## Working agreements

- One shared repo; separate clone/worktree and task branch for each concurrent task.
- Branches describe work, such as feat/t4-offline-controls. Never commit directly to main.
- Before editing shared files, agree one owner; schema/type outputs are generated from the interface source.
- Run relevant tests and privacy hooks before committing/pushing. Never bypass hooks, force-push or rebase shared branches.
- Every change reaches main through a PR. The assistant merges only with an explicit yes for that PR.
- Proposed review policy, pending team agreement: one teammate reviews each PR.
- Sync when the team chooses: ready, next, blocked. Demo owner remains unassigned; time keeper is optional.

## One home per fact

| Information | Home |
| --- | --- |
| People, work areas and agreements | This file |
| Concept, model, UI and contract links | docs/design.md |
| Tasks, dependencies, ML priorities, scenes and checkpoints | docs/plan.md |
| Action rule table | docs/DECISION_RULES.md |
| Sources, caveats and licences | docs/SOURCES.md |
| Append-only team decisions | docs/decisions.md |
| Task state and resume prompt | handoff/ |
| Models and part contracts | pipeline/baselhack/interfaces.py |

Profiles and credentials stay local. Each teammate runs participant setup in their own chat. Follow TEAMWORK.md for the collaboration walkthrough and HACKAMRHEIN.md for setup.
