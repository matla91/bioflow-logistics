from datetime import datetime

from baselhack.interfaces import Action
from baselhack.simulator.river import barge_factor
from baselhack.storage import snapshot_sha256


def decide(scenario, timeline, risk):
    thresholds = scenario["thresholds"]
    at = scenario["start_at"]
    metrics = risk["per_action"]
    suspended = barge_factor(scenario, datetime.fromisoformat(at)) is None
    quarantine = (
        timeline["budget_used"] > 1
        or risk["p_excursion"] >= thresholds["p_excursion_quarantine"]
    )
    rejection = {}
    candidates = []
    baseline = metrics["RUN_AS_PLANNED"]
    for action in Action:
        m = metrics[str(action)]
        reason = None
        if action == Action.QUARANTINE and not quarantine:
            reason = "No measured or predicted excursion budget exceedance above the configured threshold"
        elif not m["eligible"]:
            reason = m["reason"]
        elif action == Action.RUN_AS_PLANNED and (
            suspended
            or baseline["p_miss_slot"] > thresholds["p_miss_slot_low"]
            or timeline["budget_used"] >= thresholds["budget_warning_fraction"]
        ):
            reason = "Baseline does not meet the configured low-delay and excursion-margin criteria"
        elif (
            action == Action.EXPEDITE
            and baseline["p_miss_slot"] <= thresholds["p_miss_slot_low"]
        ):
            reason = "Baseline arrival risk is already low"
        elif (
            action == Action.EXPEDITE
            and m["exp_delay_min"] >= baseline["exp_delay_min"]
        ):
            reason = "No faster same-route variant improves expected delay"
        elif (
            action == Action.BUFFER
            and baseline["p_miss_slot"] <= thresholds["p_miss_slot_low"]
            and risk["p_excursion"] < thresholds["p_excursion_quarantine"]
        ):
            reason = "The lot is forecast to arrive in time within the excursion limit"
        elif action == Action.REROUTE and (
            m["p_excursion"] > baseline["p_excursion"]
            or m["p_miss_slot"] > thresholds["p_miss_slot_low"]
        ):
            reason = "Alternative route increases excursion risk or still risks missing the slot"
        if reason:
            rejection[str(action)] = reason
        else:
            candidates.append(action)
    if quarantine:
        recommended = Action.QUARANTINE
    elif candidates:
        # Explicit deterministic secondary order: preserve the challenge action order on equal delay.
        recommended = min(
            candidates,
            key=lambda a: (metrics[str(a)]["exp_delay_min"], list(Action).index(a)),
        )
    else:
        # Fail closed: do not invent a safe recommended action.
        raise ValueError(
            "No eligible action; operator and logistics must reassess the slot"
        )
    source = risk["sources"]["per_action"]
    reasons = [
        {
            "n": 1,
            "text": f"Baseline: {risk['p_miss_slot']:.1%} simulated chance of missing the slot; {risk['p_excursion']:.1%} simulated chance of exceeding excursion budget",
            "source": source,
            "at": at,
        },
        {
            "n": 2,
            "text": f"Projected cumulative simulated excursion budget used: {timeline['budget_used']:.1%}",
            "source": "timeline.json + ASSUMED config/material.yaml",
            "at": timeline["steps"][-1]["t"] if timeline["steps"] else at,
        },
    ]
    if suspended:
        measured = [
            p
            for p in scenario["rhine"]["kaub_cm"]
            if datetime.fromisoformat(p["t"]) <= datetime.fromisoformat(at)
        ]
        if measured:
            point = max(measured, key=lambda p: datetime.fromisoformat(p["t"]))
            reasons.append(
                {
                    "n": len(reasons) + 1,
                    "text": f"Kaub gauge {point['v']} cm; route suspended under ASSUMED navigation bands",
                    "source": scenario["sources"]["kaub_cm"],
                    "at": point["t"],
                }
            )
    if scenario["verification"]:
        reasons.append(
            {
                "n": len(reasons) + 1,
                "text": "Verification pending: " + "; ".join(scenario["verification"]),
                "source": "data/cache verification metadata",
                "at": at,
            }
        )
    if scenario.get("simulated_kaub_cm") is not None:
        reasons.append(
            {
                "n": len(reasons) + 1,
                "text": f"River sensitivity override: {scenario['simulated_kaub_cm']} cm, simulated",
                "source": scenario["sources"]["simulated_kaub_cm"],
                "at": at,
            }
        )
    rejected = []
    for action in Action:
        if action == recommended:
            continue
        m = metrics[str(action)]
        reason = (
            "Quarantine has priority when the excursion limit is exceeded"
            if quarantine
            else rejection.get(
                str(action),
                f"Higher or tied expected simulated batch delay ({m['exp_delay_min']:.1f} min)",
            )
        )
        rejected.append(
            {"action": str(action), "reason": reason, "source": source, "at": at}
        )
    approver = (
        "QA"
        if recommended == Action.QUARANTINE
        else "logistics"
        if recommended in (Action.EXPEDITE, Action.REROUTE)
        else "operator"
    )
    headline = {
        Action.RUN_AS_PLANNED: "Material forecast to meet the slot within the configured budget",
        Action.BUFFER: "Use cold-store safety stock for this batch",
        Action.EXPEDITE: "Ask logistics for a faster slot on the same route",
        Action.REROUTE: "Ask logistics to reroute and resequence the reactor",
        Action.QUARANTINE: "Do not charge this lot; request QA quarantine review",
    }[recommended]
    result = {
        "decision_id": "D-"
        + snapshot_sha256({"scenario": scenario, "timeline": timeline, "risk": risk})[
            :16
        ],
        "scenario_id": scenario["scenario_id"],
        "lot": scenario["site"]["lot"],
        "slot": f"{scenario['slot']['reactor']} {scenario['slot']['charge_at']}",
        "recommended": str(recommended),
        "headline": headline,
        "rejected": rejected,
        "reasons": reasons,
        "would_change_if": [
            "Cold-store stock changes",
            "Measured river level changes",
            "Handover exposure or reactor readiness changes",
            "For afternoon heat exposure: unload before 10:00 Basel local time",
        ],
        "requires_approval_by": approver,
        "explanation": "pending",
        "sources": {
            "recommendation": "rules/engine.py; ASSUMED thresholds; Monte Carlo probabilities",
            "approval": "human authorization required; browser roles are demo labels, not authentication",
        },
    }
    return result
