"""Snapshot logistics risk under explicitly simulated shipment assumptions."""

import numpy as np

from baselhack.interfaces import (
    LogisticsActionResult,
    LogisticsAssumptions,
    LogisticsFeatures,
    LogisticsResult,
    ObservationSource,
    RiskDriver,
    ShipmentState,
)
from baselhack.output.frontend import provenance_summary

from .delay import delay_penalties, journey_durations
from .navigation import assess_navigation
from .recommendation import recommend, with_counterfactual_changes
from .shipment import validate_snapshot
from .thermal import ambient_distance_c, exposure_proxy

MODEL = (
    "Explainable paired normal Monte Carlo with ambient degree-minute exposure proxy v2"
)


def simulate(
    shipment: ShipmentState,
    features: LogisticsFeatures,
    assumptions: LogisticsAssumptions,
    sources: list[ObservationSource],
) -> LogisticsResult:
    """Compare explicit timing and ambient proxy dimensions using seeded draws."""
    if not sources:
        raise ValueError(
            "At least one real observation source is required for provenance"
        )
    warnings = validate_snapshot(shipment, features, assumptions)
    actions, lateness, proxies, drivers, navigation = _evaluate(
        shipment, features, assumptions
    )
    recommendation_features = features.model_copy(
        update={"warnings": warnings + navigation.warnings}
    )
    recommendation = recommend(actions, recommendation_features, assumptions, sources)
    recommendation = with_counterfactual_changes(
        recommendation,
        _counterfactual_changes(
            shipment, recommendation_features, assumptions, sources
        ),
    )
    return LogisticsResult(
        shipment_id=shipment.shipment_id,
        as_of=shipment.as_of,
        predicted_delay_min=float(np.mean(lateness["BASELINE"])),
        delay_risk=float(
            np.mean(lateness["BASELINE"] > assumptions.delay_threshold_min)
        ),
        cold_chain_exposure_proxy_risk=float(
            np.mean(proxies["BASELINE"] > assumptions.exposure_budget_degree_min)
        ),
        action_success_probabilities={
            item.action: item.success_probability for item in actions
        },
        actions=actions,
        recommendation=recommendation,
        navigation=navigation,
        data_provenance=provenance_summary(
            features, shipment, assumptions, sources, navigation
        ),
        main_risk_drivers=drivers + _shipment_drivers(shipment, features, assumptions),
        features=recommendation_features,
        simulated_shipment=shipment,
        assumptions=assumptions,
        real_data_sources=sources,
        limitations=_limitations(warnings + navigation.warnings),
        model=MODEL,
    )


def _evaluate(shipment, features, assumptions):
    """Run paired scenarios without recursion or recommendation side effects."""
    navigation, _ = assess_navigation(shipment, features, assumptions)
    traffic, river, weather, drivers = delay_penalties(shipment, features, assumptions)
    durations = journey_durations(shipment, assumptions, traffic, river, weather)
    time_to_deadline = (shipment.deadline_at - shipment.as_of).total_seconds() / 60
    # validate_snapshot rejects missing weather before any thermal calculation.
    assert features.weather is not None
    proxies = {
        action: exposure_proxy(elapsed, shipment, features.weather, assumptions)
        for action, elapsed in durations.items()
    }
    lateness = {
        action: np.maximum(elapsed - time_to_deadline, 0.0)
        for action, elapsed in durations.items()
    }
    stock_sufficient = shipment.stock_available >= shipment.stock_required
    route_available = shipment.route_mode != "river" or navigation.normal_route_eligible
    actions = [
        _action_result(
            action,
            lateness[action],
            proxies[action],
            stock_sufficient,
            assumptions,
            (
                shipment.reroute_available
                if action == "REROUTE"
                else route_available
                and (action != "EXPEDITE" or shipment.expedite_available)
            ),
        )
        for action in ("BUFFER", "EXPEDITE", "REROUTE")
    ]
    return actions, lateness, proxies, drivers, navigation


def _action_result(
    action, lateness, proxy, stock_sufficient, assumptions, route_available
):
    exposure_risk = float(np.mean(proxy > assumptions.exposure_budget_degree_min))
    on_time = float(np.mean(lateness == 0)) if route_available else 0.0
    arrival_delay = float(np.mean(lateness))
    if action == "BUFFER":
        return LogisticsActionResult(
            action=action,
            eligible=stock_sufficient,
            success_probability=float(stock_sufficient),
            production_continuity_probability=1.0 if stock_sufficient else on_time,
            on_time_arrival_probability=on_time,
            predicted_delay_min=0.0 if stock_sufficient else arrival_delay,
            predicted_arrival_delay_min=arrival_delay,
            delay_risk=0.0
            if stock_sufficient
            else float(np.mean(lateness > assumptions.delay_threshold_min)),
            cold_chain_exposure_proxy_risk=exposure_risk,
            assessment=(
                "Factory continuity is covered by simulated stock; incoming shipment timing and exposure remain separate."
                if stock_sufficient
                else "BUFFER is ineligible; production continuity falls back to incoming shipment arrival."
            ),
            reason=(
                "ASSUMED sufficient stock covers the factory deadline; incoming shipment exposure is unchanged."
                if stock_sufficient
                else "ASSUMED stock is insufficient; BUFFER cannot cover the factory deadline. Incoming shipment delay and exposure are unchanged."
            ),
        )
    joint_success = (lateness <= assumptions.delay_threshold_min) & (
        proxy <= assumptions.exposure_budget_degree_min
    )
    return LogisticsActionResult(
        action=action,
        eligible=route_available,
        success_probability=float(np.mean(joint_success)) if route_available else 0.0,
        production_continuity_probability=on_time,
        on_time_arrival_probability=on_time,
        predicted_delay_min=arrival_delay,
        predicted_arrival_delay_min=arrival_delay,
        delay_risk=float(np.mean(lateness > assumptions.delay_threshold_min)),
        cold_chain_exposure_proxy_risk=exposure_risk,
        assessment=(
            "Incoming shipment arrival determines production continuity; exposure remains an ambient proxy."
            if route_available
            else "The transport intervention is unavailable in the scenario; factory timing cannot be restored by this action."
        ),
        reason=(
            (
                "ASSUMED transport and handling speed factors reduce all corresponding journey minutes."
                if route_available
                else "EXPEDITE is unavailable under the simulated availability or official route status; delay and ambient proxy calculations describe a hypothetical finite scenario."
            )
            if action == "EXPEDITE"
            else (
                "ASSUMED alternative road transport retains reduced traffic and full weather additions, omits river additions, and adds transfer handling."
                if route_available
                else "REROUTE is unavailable under the simulated availability input; delay and ambient proxy calculations describe the hypothetical alternative."
            )
        ),
    )


def _counterfactual_changes(shipment, features, assumptions, sources):
    """Rerun bounded single-input changes with the same seed; never infer thresholds."""
    cases = [("stock_available", 0, "units", "shipment")]
    cases.extend(
        (
            "planned_remaining_min",
            shipment.planned_remaining_min * factor,
            "min",
            "shipment",
        )
        for factor in assumptions.recommendation_policy.sensitivity_factors
    )
    cases.extend(
        (
            "protection_remaining_min",
            shipment.protection_remaining_min * factor,
            "min",
            "shipment",
        )
        for factor in (0.5, 2.0)
    )
    cases.append(("expedite_transport_factor", 1.0, "factor", "assumptions"))
    changes = []
    for field, value, unit, owner in cases:
        original = shipment if owner == "shipment" else assumptions
        previous = getattr(original, field)
        if previous == value:
            continue
        changed = original.model_copy(update={field: value})
        candidate_shipment = changed if owner == "shipment" else shipment
        candidate_assumptions = changed if owner == "assumptions" else assumptions
        actions, _, _, _, navigation = _evaluate(
            candidate_shipment, features, candidate_assumptions
        )
        recommendation_features = features.model_copy(
            update={"warnings": features.warnings + navigation.warnings}
        )
        candidate = recommend(
            actions, recommendation_features, candidate_assumptions, sources
        )
        evidence = "SIMULATED" if owner == "shipment" else "ASSUMED"
        changes.append(
            (
                f"{evidence} {field} changed from {previous:g} to {value:g} {unit}",
                candidate,
            )
        )
    return changes


def _shipment_drivers(shipment, features, assumptions):
    weather = features.weather
    assert weather is not None
    distance = ambient_distance_c(
        weather.air_temperature_c, assumptions.ambient_reference_band_c
    )
    values = [
        (
            "Snapshot ambient temperature",
            weather.air_temperature_c,
            "°C",
            "observed",
            f"Ambient is {distance:g}°C outside ASSUMED reference band {assumptions.ambient_reference_band_c}. "
            "Snapshot ambient is ASSUMED constant over the entire future unprotected interval; actual product temperature is not inferred.",
        ),
        (
            "Planned remaining transport",
            shipment.planned_remaining_min,
            "min",
            "assumed",
            "SIMULATED remaining transport excludes handling; normal variation is added using ASSUMED transport_sd_min and transport duration is floored at zero.",
        ),
        (
            "Remaining handling",
            shipment.handling_min,
            "min",
            "assumed",
            "SIMULATED handling is separately varied using ASSUMED handling_sd_min and added to whole-journey time.",
        ),
        (
            "Time until factory deadline",
            (shipment.deadline_at - shipment.as_of).total_seconds() / 60,
            "min",
            "assumed",
            "SIMULATED schedule window; lateness is total remaining journey time beyond this window, floored at zero.",
        ),
        (
            "Remaining packaging protection",
            shipment.protection_remaining_min,
            "min",
            "assumed",
            "SIMULATED whole-journey packaging autonomy; ambient exposure proxy accrues only after this duration expires.",
        ),
        (
            "Prior ambient exposure proxy",
            shipment.prior_exposure_degree_min,
            "°C·min",
            "assumed",
            "SIMULATED prior degree-minutes added to each action's future exposure proxy; not measured product exposure.",
        ),
    ]
    return [
        RiskDriver(
            name=name,
            value=value,
            unit=unit,
            estimated_delay_contribution_min=0,
            explanation=explanation,
            evidence_kind=kind,
        )
        for name, value, unit, kind, explanation in values
    ]


def _limitations(warnings):
    return [
        "All shipment, factory stock, protection, coefficients and thresholds are SIMULATED or ASSUMED; none are external provider facts or validated QA limits.",
        "Monte Carlo probabilities are scenario frequencies under uncalibrated assumptions, not calibrated forecasts or validated operational success rates.",
        "The cold-chain exposure measure is an ambient degree-minute proxy; ambient observations alone do not establish actual product-temperature excursions.",
        "Ambient weather observations alone do not establish actual product-temperature excursion, pharmaceutical quality, or QA release status.",
        "ASSUMED snapshot ambient remains constant over the whole future unprotected journey; this conservative persistence scenario is not a weather forecast and can miss future worsening.",
        "ASSUMED packaging autonomy expires as one whole-journey clock; refrigeration failures, packaging performance and product thermal response are not modelled.",
        "Independent normal transport and handling draws, with durations floored at zero, are paired across actions; they do not model extremes, station causality or operational feasibility.",
        "Without a valid official status/forecast adapter, Rhine navigation state and delay use an ASSUMED fallback. Falling level/discharge describe one hydrological state; the largest component is used without summing them. No official threshold values are inferred.",
        "Deprecated success_probability is stock sufficiency for BUFFER; for EXPEDITE/REROUTE it is the joint frequency of lateness <= delay_threshold_min and ambient proxy <= exposure_budget_degree_min. It does not drive recommendations.",
        "Comparable production continuity and on-time arrival use the exact simulated deadline, independently of delay_threshold_min and the ambient proxy budget.",
        *warnings,
    ]
