"""Batch quantities and stored shipment evidence; no provider or fixture lookups."""

from datetime import datetime, timedelta

import numpy as np

from baselhack.batch_readiness import production_readiness
from baselhack.batch_temperature import product_temperature
from baselhack.data_engine.database import digest, utc
from baselhack.interfaces import (
    BatchRecommendation,
    IncomingShipmentResult,
    ProvenanceSummary,
    ShipmentState,
    StoredBatchAssessment,
)
from baselhack.logistics import evaluate
from baselhack.simulation.delay import delay_penalties, journey_durations

MODEL_VERSION = "batch-stored-evidence-v1"
DEFAULT_PROFILE_ID = "batch-default-v1"


def _incoming(shipment, plan, dependency, snapshot, profile, observations, sufficient):
    values = dict(
        shipment_id=shipment.id,
        planned_quantity_kg=plan.quantity_kg,
        dependency_quantity_kg=dependency,
        planned_arrival_at=shipment.planned_arrival_at,
        actual_arrival_at=shipment.actual_arrival_at,
        scheduled_after_charge=shipment.planned_arrival_at
        > snapshot.batch.planned_charge_at,
        status="UNAVAILABLE",
        on_time_arrival_probability=None,
        eta_p50=None,
        eta_p90=None,
        cold_chain_exposure_proxy_risk=None,
        logistics=None,
    )
    if snapshot.reference_at > snapshot.as_of:
        return IncomingShipmentResult(
            **values,
            reason="Operational snapshot postdates cutoff; schedule and QA knowledge were not captured then.",
        )
    if shipment.actual_arrival_at is not None:
        return IncomingShipmentResult(
            **{
                **values,
                "status": "ARRIVED",
                "on_time_arrival_probability": float(
                    shipment.actual_arrival_at <= snapshot.batch.planned_charge_at
                ),
                "eta_p50": shipment.actual_arrival_at,
                "eta_p90": shipment.actual_arrival_at,
                "reason": "Arrival is recorded by cutoff; exact timing is observed, not a model prediction. QA release remains separate.",
            }
        )
    reason = _unavailable_reason(shipment, snapshot, profile, observations)
    if reason:
        return IncomingShipmentResult(**values, reason=reason)
    assert shipment.actual_departure_at is not None and observations is not None
    duration = (
        shipment.planned_arrival_at - shipment.planned_departure_at
    ).total_seconds() / 60
    elapsed = (snapshot.as_of - shipment.actual_departure_at).total_seconds() / 60
    remaining = duration - elapsed
    if remaining <= 0:
        return IncomingShipmentResult(
            **values,
            reason="Planned journey duration elapsed without recorded arrival; remaining duration is unknown. No delay label or invented remaining time is used.",
        )
    state = ShipmentState(
        shipment_id=shipment.id,
        as_of=snapshot.as_of,
        deadline_at=snapshot.batch.planned_charge_at,
        route_mode=shipment.route_mode,
        planned_remaining_min=remaining,
        handling_min=profile.handling_min,
        protection_remaining_min=profile.protection_remaining_min,
        stock_available=int(sufficient),
        stock_required=1,
        expedite_available=profile.expedite_available,
        reroute_available=profile.reroute_available,
    )
    try:
        detailed = evaluate(observations, state, profile.logistics, profile.station_ids)
    except ValueError as error:
        # Missing/stale external signals are evidence gaps, not a fallback forecast.
        if "Weather" not in str(error):
            raise
        return IncomingShipmentResult(**values, reason=str(error))
    traffic, river, weather, _ = delay_penalties(
        state, detailed.features, profile.logistics
    )
    durations = journey_durations(state, profile.logistics, traffic, river, weather)[
        "BASELINE"
    ]
    baseline = next(a for a in detailed.actions if a.action == "BUFFER")
    return IncomingShipmentResult(
        **{
            **values,
            "status": "MODELED",
            "on_time_arrival_probability": baseline.on_time_arrival_probability,
            "eta_p50": snapshot.as_of
            + timedelta(minutes=float(np.quantile(durations, 0.5))),
            "eta_p90": snapshot.as_of
            + timedelta(minutes=float(np.quantile(durations, 0.9))),
            "cold_chain_exposure_proxy_risk": detailed.cold_chain_exposure_proxy_risk,
            "logistics": detailed,
            "reason": "Paired Monte Carlo uses stored external evidence and planned duration minus elapsed time since actual departure. Timing is conditional on assumptions, not QA release.",
        }
    )


def _unavailable_reason(shipment, snapshot, profile, observations):
    if snapshot.reference_at > snapshot.as_of:
        return "Operational snapshot postdates cutoff; schedule knowledge was not captured then."
    if shipment.origin != profile.origin or shipment.destination != profile.destination:
        return "Stored route is outside the configured model corridor."
    if shipment.actual_departure_at is None:
        return "No actual departure at cutoff; this in-transit model does not simulate future departure waits. Planned milestones remain visible."
    if snapshot.batch.planned_charge_at < snapshot.as_of:
        return "Charge deadline precedes cutoff; forward action simulation cannot recover historical readiness."
    if observations is None:
        return "No stored external observations applicable at cutoff/knowledge time."
    return None


def _recommendation(readiness, incoming, temperature):
    qa_review = any(
        t.status != "OBSERVED_WITHIN_BUDGET"
        or not t.complete_journey
        or t.last_product_outside_range
        for t in temperature
    )
    dependencies = [item for item in incoming if item.dependency_quantity_kg > 0]
    action, alternatives = None, []
    reason = "No supported aggregate action comparison is available; review quantities, incoming timing and QA evidence."
    sufficient = readiness.reservation_shortfall_kg == 0
    if sufficient:
        action = "BUFFER"
        reason = "Released reserved stock covers the recorded batch demand by charge time; incoming timing and product evidence remain separate."
    if (
        len(incoming) == 1
        and incoming[0].logistics is not None
        and readiness.uncovered_quantity_kg == 0
    ):
        model = incoming[0].logistics
        action, alternatives = model.recommendation.action, model.actions
        reason = (
            model.recommendation.reason
            + " Production timing is conditional on material quantity and subsequent human QA release; it is not a production authorization."
        )
    elif dependencies and not sufficient:
        reason = (
            "Released reservations leave a quantity shortfall; incoming plans are prospective and require arrival plus human QA release. "
            + reason
        )
    if qa_review:
        reason += " Human QA review is required; no automatic quarantine or release is inferred."
    return BatchRecommendation(
        action=action,
        reason=reason,
        requires_approval_by="operator" if action == "BUFFER" else "logistics",
        qa_review_required=bool(qa_review),
        alternatives=alternatives,
    )


def analyze_batch(
    database,
    dataset_id,
    batch_id,
    as_of,
    profile_id=DEFAULT_PROFILE_ID,
    known_at=None,
    model_version=MODEL_VERSION,
):
    """Assess SQLite-only batch inputs and append immutable, idempotent evidence."""
    as_of = datetime.fromisoformat(utc(as_of))
    if known_at is not None:
        known_at = datetime.fromisoformat(utc(known_at))
    snapshot = database.batch_snapshot(dataset_id, batch_id, as_of)
    if known_at is not None and known_at < snapshot.reference_at:
        raise ValueError(
            "Operational snapshot postdates known_at; historical operational knowledge is unavailable"
        )
    profile = database.batch_profile(profile_id)
    try:
        observations = database.observations(as_of, known_at)
    except ValueError as error:
        if "No stored observations" not in str(error):
            raise
        observations = None
    readiness, dependencies = production_readiness(snapshot)
    plans = {p.shipment_id: p for p in snapshot.supply_plans}
    incoming = [
        _incoming(
            s,
            plans[s.id],
            dependencies[s.id],
            snapshot,
            profile,
            observations,
            readiness.reservation_shortfall_kg == 0,
        )
        for s in snapshot.shipments
    ]
    temperature = [
        product_temperature(s, snapshot.material, profile.max_reading_gap_min)
        for s in snapshot.shipments
    ]
    limitations = [
        "Operations and product readings are synthetic demo evidence; material limits are demonstration assumptions, not pharmaceutical release policy.",
        "QA and reservation state exists only at the operational snapshot reference time. Earlier historical states and the actual production decision at a past charge time cannot be reconstructed.",
        "Released reservations are credited only when available by both cutoff and charge time. Unreserved stock and competing reservations are not automatically allocated.",
        "Incoming dependency is prospective quantity coverage; arrivals and acceptable sampled temperatures do not imply QA release or production authorization.",
        "Default observation selection uses latest stored revisions at the measurement cutoff, not knowledge available then. An explicit known_at filters stored retrieval history; operational capture history is unavailable.",
        "Forward timing applies only to departed shipments in the configured corridor while planned remaining duration is positive; departure waits and overdue journeys require further evidence.",
        "Timing/ambient Monte Carlo uses uncalibrated persisted assumptions. Protection autonomy is configured, not inferred from temperature samples; measured product exposure stays separate.",
        "Action production-continuity probabilities are conditional timing events for one shipment, not batch QA/readiness probabilities. Multiple dependent shipments have no aggregate recommendation.",
        "Seven existing domain/licence verification gates remain open.",
    ]
    if snapshot.as_of > snapshot.reference_at:
        limitations.append(
            "Operational QA/reservation snapshot predates cutoff; no subsequent mutation history is available."
        )
    for item in incoming:
        if item.logistics is not None:
            limitations.extend(item.logistics.limitations)
    inputs = {
        "operations": snapshot.model_dump(mode="json"),
        "observations": observations.model_dump(mode="json") if observations else None,
        "profile": profile.model_dump(mode="json"),
        "known_at": utc(known_at) if known_at else None,
        "model_version": model_version,
    }
    body = dict(
        dataset_id=dataset_id,
        batch_id=batch_id,
        shipment_ids=[s.id for s in snapshot.shipments],
        as_of=as_of,
        known_at=known_at,
        input_sha256=digest(inputs),
        model_version=model_version,
        production_readiness=readiness,
        incoming_shipments=incoming,
        product_temperature=temperature,
        recommendation=_recommendation(readiness, incoming, temperature),
        provenance=[
            ProvenanceSummary(
                kind="SIMULATED",
                observed_at=snapshot.reference_at,
                detail="Persisted operational snapshot and shipment product readings; no generator labels used.",
            ),
            ProvenanceSummary(
                kind="REAL",
                source_indices=list(range(len(observations.sources))),
                detail="Stored external observations and retrieval metadata; no analysis-worker provider fetch.",
            )
            if observations
            else ProvenanceSummary(
                kind="MODEL",
                detail="External observation evidence unavailable; no replacement data fabricated.",
            ),
            ProvenanceSummary(
                kind="ASSUMED",
                detail=f"Immutable persisted configuration {profile.profile_id}; uncalibrated coefficients and sparse product-temperature interpolation.",
            ),
        ],
        real_data_sources=observations.sources if observations else [],
        assumptions=profile,
        limitations=list(dict.fromkeys(limitations)),
    )
    provisional = StoredBatchAssessment(assessment_id="0" * 64, **body)
    identity = provisional.model_dump(mode="json", exclude={"assessment_id"})
    record = provisional.model_copy(update={"assessment_id": digest(identity)})
    database.store_batch_assessment(record, {"inputs": inputs})
    return record
