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

from .delay import delay_penalties, journey_durations
from .shipment import validate_snapshot
from .thermal import ambient_distance_c, exposure_proxy

MODEL = (
    "Explainable paired normal Monte Carlo with ambient degree-minute exposure proxy v1"
)


def simulate(
    shipment: ShipmentState,
    features: LogisticsFeatures,
    assumptions: LogisticsAssumptions,
    sources: list[ObservationSource],
) -> LogisticsResult:
    """Compare factory delay and incoming-lot ambient exposure using seeded draws."""
    if not sources:
        raise ValueError(
            "At least one real observation source is required for provenance"
        )
    warnings = validate_snapshot(shipment, features, assumptions)
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
    actions = [
        _action_result(
            action, lateness[action], proxies[action], stock_sufficient, assumptions
        )
        for action in ("BUFFER", "EXPEDITE", "REROUTE")
    ]
    return LogisticsResult(
        shipment_id=shipment.shipment_id,
        as_of=shipment.as_of,
        predicted_delay_min=float(np.mean(lateness["BASELINE"])),
        delay_risk=float(
            np.mean(lateness["BASELINE"] > assumptions.delay_threshold_min)
        ),
        thermal_exposure_risk=float(
            np.mean(proxies["BASELINE"] > assumptions.exposure_budget_degree_min)
        ),
        action_success_probabilities={
            item.action: item.success_probability for item in actions
        },
        actions=actions,
        main_risk_drivers=drivers + _shipment_drivers(shipment, features, assumptions),
        features=features,
        simulated_shipment=shipment,
        assumptions=assumptions,
        real_data_sources=sources,
        limitations=_limitations(warnings),
        model=MODEL,
    )


def _action_result(action, lateness, proxy, stock_sufficient, assumptions):
    exposure_risk = float(np.mean(proxy > assumptions.exposure_budget_degree_min))
    if action == "BUFFER":
        return LogisticsActionResult(
            action=action,
            eligible=stock_sufficient,
            success_probability=float(stock_sufficient),
            predicted_delay_min=0.0 if stock_sufficient else float(np.mean(lateness)),
            delay_risk=0.0
            if stock_sufficient
            else float(np.mean(lateness > assumptions.delay_threshold_min)),
            shipment_thermal_exposure_risk=exposure_risk,
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
        eligible=True,
        success_probability=float(np.mean(joint_success)),
        predicted_delay_min=float(np.mean(lateness)),
        delay_risk=float(np.mean(lateness > assumptions.delay_threshold_min)),
        shipment_thermal_exposure_risk=exposure_risk,
        reason=(
            "ASSUMED transport and handling speed factors reduce all corresponding journey minutes."
            if action == "EXPEDITE"
            else "ASSUMED alternative road transport retains reduced traffic and full weather additions, omits river additions, and adds transfer handling."
        ),
    )


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
        "The thermal measure is an ambient degree-minute proxy; ambient observations alone do not establish actual product-temperature excursions, product safety or quality release.",
        "ASSUMED snapshot ambient remains constant over the whole future unprotected journey; this conservative persistence scenario is not a weather forecast and can miss future worsening.",
        "ASSUMED packaging autonomy expires as one whole-journey clock; refrigeration failures, packaging performance and product thermal response are not modelled.",
        "Independent normal transport and handling draws, with durations floored at zero, are paired across actions; they do not model extremes, station causality or operational feasibility.",
        "Observed Rhine falling trends add only assumed river-route delay; absolute levels do not determine navigation restrictions in this model.",
        "BUFFER success describes assumed factory continuity from sufficient stock and leaves the incoming shipment exposure risk unchanged.",
        *warnings,
    ]
