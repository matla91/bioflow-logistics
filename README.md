# Current Affairs · from a Rhine signal to a factory-floor decision

Hack am Rhein 2026, Challenge 4: *From a Rhine Signal to Action: Manufacturing in the BioValley*.

> **The operator's question:** "My next batch charges the reactor at 06:00. Will the material be here, and is it still good to use?"

A 2–8 °C intermediate travels from Shanghai by sea, Rhine barge and truck to a site near Basel. We combine **real**
public signals (Rhine levels, air temperature, Basel traffic) with a **simulated** shipment to recommend one action:
run as planned, expedite, use safety stock, reroute, or flag the lot for QA. The recommendation shows its evidence
and the options it rejected, and **a person approves or overrides it**.

**Rules recommend, ML supplies probabilities, an LLM may word the explanation, people decide.**

Concept deck and team working pages: link in the team chat.

---

## Where we are: a starting point, not the solution

This repo is a **walking skeleton**. Every part exists in a simple form and the parts are wired together, so we can
see the whole chain run and then make each part good. Nothing here is final: screens, rules, parameters and the
stack are all open for the team to change.

| Works today (simple version) | Still open (see [docs/plan.md](docs/plan.md)) |
| --- | --- |
| Real-data loaders + cached observations for 3 scenes | Traffic station choice; long Rhine history; licence check |
| Seeded journey + temperature simulator | Validating the assumed limits and durations with the domain |
| Monte Carlo comparison of all five actions (ML priority 1) | Risk model, gauge anomaly check, river forecast (stubs) |
| Rule engine → decision with rejected options and sources | Scene-specific "would change if" lines (currently generic) |
| Starter web app: decision card, approve / override, log | Real UX: operator, scenario controls, QA views |
| Offline demo from `snapshots/` | Demo story, rehearsal, the sources slide |

## Get it running (5 minutes)

Install [pixi](https://pixi.prefix.dev/latest/installation/), then from the repo root:

```sh
pixi run setup
pixi run demo SCENE=s1_normal_2026-05-10     # open the URL it prints
```

The demo runs offline from prepared snapshots. No API key is needed.

| Scene | What happens | Recommendation |
| --- | --- | --- |
| `s1_normal_2026-05-10` | Mild day, normal handovers | Run as planned |
| `s2_heat_2026-07-30` | Unloaded in Basel on a 38 °C afternoon | Quarantine (QA decides); an unload before 10:00 would have been fine |
| `s3_lowriver_2026-10-01` | Kaub gauge at −6 cm, barge suspended | Use safety stock (operator approves) |

Other tasks: `pixi run data` (refresh real data), `sim` / `ml` / `decide SCENE=…` (run one stage), `all`,
`variants` (offline dial variants), `contracts` (regenerate schemas and TS types), `test`.

## Our areas and where to start

| Area | Start in | First things to do |
| --- | --- | --- |
| **UX** | `web/src/App.tsx`, [docs/design.md](docs/design.md) | Redesign the operator screen and decision card so it reads in 10 seconds at 5 a.m.; add the journey timeline and temperature trace |
| **Full stack** | `web/`, `pipeline/baselhack/api.py` | Own the app shell, scenario controls and demo mode; keep it working offline |
| **Data engineering** | `pipeline/baselhack/loaders/`, `pipeline/baselhack/simulator/`, `data/cache/` | Choose the Basel traffic stations; find long Rhine history; confirm data licences (T2) |
| **ML engineering** | `pipeline/baselhack/ml/` | Decision analysis works; build the risk model, then the gauge anomaly check (T5) |
| **Domain & process** | `config/`, `scenarios/`, [docs/DECISION_RULES.md](docs/DECISION_RULES.md) | Check the assumed limits, durations and rules; make "would change if" specific per scene (T3) |

Agree owners in [TEAM.md](TEAM.md) (GitHub usernames only). Tasks, dependencies and "done when" are in
[docs/plan.md](docs/plan.md).

## How the parts connect

`loaders → scenario.json → simulator → timeline.json → ML → risk.json → rules → decision.json → web app → log.json`

All shared data models live in **one file**, [pipeline/baselhack/interfaces.py](pipeline/baselhack/interfaces.py).
`schemas/` and `web/src/interfaces.ts` are generated from it (`pixi run contracts`), so we never edit them by hand.
Changing the interface file needs a line in [docs/decisions.md](docs/decisions.md) in the same commit.

## How we work (the kit does most of this for us)

- A branch per task (`feat/…`, `fix/…`, `data/…`), a pull request to `main`, and a merge only after an explicit yes.
- We commit with our GitHub **noreply** emails. The privacy check blocks anything else. Never `--no-verify`.
- `pixi run test -- -m "not verification"` checks the code. Plain `pixi run test` also runs the **open verification
  items** in [config/verification.yaml](config/verification.yaml), which fail on purpose until someone resolves them
  with evidence.
- Collaboration walkthrough: [TEAMWORK.md](TEAMWORK.md). Kit setup: [HACKAMRHEIN.md](HACKAMRHEIN.md).

## Ground rules for the demo

- **Real stays real, simulated stays labelled.** Never invent a gauge or temperature value. Sources:
  [docs/SOURCES.md](docs/SOURCES.md).
- **Every reason on the card cites a source and a time.**
- **The LLM never decides**, and the demo never depends on the network.
- This is hackathon exploration: outputs are not a pharmaceutical release decision.

**Sunday 4 Oct, FHNW Campus Dreispitz:** doors 13:00, **submission 15:00**, demos from 15:30.

Code: MIT (pending organiser confirmation). Data keeps its providers' terms.
