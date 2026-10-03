"""Use official navigation input when valid, with a labelled assumed fallback."""

from baselhack.interfaces import (
    LogisticsAssumptions,
    LogisticsFeatures,
    NavigationAssessment,
    RiskDriver,
    ShipmentState,
)


def assess_navigation(
    shipment: ShipmentState,
    features: LogisticsFeatures,
    assumptions: LogisticsAssumptions,
) -> tuple[NavigationAssessment, list[RiskDriver]]:
    """Interpret a supplied official signal; this module does not fetch a feed."""
    fallback, drivers = _assumed_navigation(shipment, features, assumptions)
    official = features.official_navigation
    if official is None:
        return fallback, drivers
    valid = (
        official.issued_at <= shipment.as_of
        and official.valid_from <= shipment.as_of <= official.valid_until
    )
    if not valid:
        warnings = fallback.warnings + [
            "Official navigation input is not valid at as_of; ASSUMED fallback is used."
        ]
        return fallback.model_copy(update={"warnings": warnings}), drivers
    delay = official.expected_delay_min
    delay_kind = official.kind if delay is not None else "ASSUMED"
    warnings = []
    if delay is None:
        delay = fallback.delay_penalty_min
        warnings = fallback.warnings + [
            "Valid official navigation input has no delay estimate; delay uses the ASSUMED trend fallback."
        ]
    else:
        drivers = [
            RiskDriver(
                name="Rhine official navigation delay",
                value=delay,
                unit="min",
                estimated_delay_contribution_min=delay,
                explanation=f"{official.kind} delay supplied by {official.provider}; no threshold is inferred from absolute Rhine observations.",
                evidence_kind=(
                    "official_forecast"
                    if official.kind == "OFFICIAL_FORECAST"
                    else "observed"
                ),
            )
        ]
    horizon_addition = 0.0
    if not official.normal_route_eligible:
        horizon_addition = max(assumptions.route_block_delay_min - delay, 0.0)
        if horizon_addition > 0:
            delay = assumptions.route_block_delay_min
            delay_kind = "ASSUMED"
            drivers.append(
                RiskDriver(
                    name="Rhine route blockage modelling horizon",
                    value=assumptions.route_block_delay_min,
                    unit="min",
                    estimated_delay_contribution_min=horizon_addition,
                    explanation="Official route ineligibility uses an ASSUMED finite horizon for scenario delay/proxy calculations; it does not forecast an arrival or closure duration.",
                    evidence_kind="assumed",
                )
            )
            warnings.append(
                f"Official input marks the normal route unavailable. The effective delay addition uses the ASSUMED {delay:g} min finite modelling horizon; it is not an arrival forecast or expected closure duration."
            )
        else:
            warnings.append(
                f"Official input marks the normal route unavailable. The supplied {delay:g} min delay estimate remains the scenario addition; route ineligibility prevents any inferred on-time arrival even if this finite addition fits the deadline."
            )
    return NavigationAssessment(
        state=official.state,
        kind=official.kind,
        normal_route_eligible=official.normal_route_eligible,
        delay_penalty_min=delay,
        delay_kind=delay_kind,
        reported_delay_min=official.expected_delay_min,
        provider=official.provider,
        observed_at=official.issued_at,
        reason=(
            f"Valid {official.kind} navigation state and explicit route eligibility supplied by {official.provider}. "
            + (
                f"The ASSUMED finite blockage horizon ({delay:g} min) overrides the lower supplied/fallback delay; the official state retains its own provenance."
                if horizon_addition > 0
                else (
                    "No official delay estimate was supplied; delay remains an ASSUMED scenario."
                    if official.expected_delay_min is None
                    else "The supplied official delay estimate replaces the assumed trend delay."
                )
            )
        ),
        warnings=warnings,
    ), drivers


def _assumed_navigation(shipment, features, assumptions):
    rhine = features.rhine
    recent = rhine is not None and (
        0
        <= (shipment.as_of - rhine.observed_at).total_seconds() / 60
        <= assumptions.max_rhine_age_min
    )
    if not recent:
        return _unknown_navigation("Missing, stale or future Rhine observation"), []
    assert rhine is not None
    trends = [
        (
            "Rhine level trend",
            rhine.level_trend_cm_per_hour,
            "cm/hour",
            assumptions.falling_level_min_per_cm_hour,
        ),
        (
            "Rhine discharge trend",
            rhine.discharge_trend_m3_s_per_hour,
            "m³/s/hour",
            assumptions.falling_discharge_min_per_m3_s_hour,
        ),
    ]
    available = [item for item in trends if item[1] is not None]
    if not available:
        return _unknown_navigation("Rhine observation has no usable trends"), []
    components = [max(-value, 0.0) * factor for _, value, _, factor in available]
    largest = max(range(len(components)), key=components.__getitem__)
    penalty = min(components[largest], assumptions.river_penalty_cap_min)
    drivers = [
        RiskDriver(
            name=name,
            value=value,
            unit=unit,
            estimated_delay_contribution_min=penalty if index == largest else 0.0,
            explanation=(
                f"Observed falling trend multiplied by ASSUMED {factor:g} min per {unit}. "
                "Level and discharge represent the same hydrological state, so only the largest component contributes, "
                f"capped at ASSUMED {assumptions.river_penalty_cap_min:g} min. "
                "This is an ASSUMED navigation scenario, not a validated navigation relationship or official threshold."
            ),
            evidence_kind="observed",
        )
        for index, (name, value, unit, factor) in enumerate(available)
    ]
    if penalty >= assumptions.navigation_severe_penalty_min:
        state = "SEVERE"
    elif penalty >= assumptions.navigation_restricted_penalty_min:
        state = "RESTRICTED"
    else:
        state = "WATCH" if penalty > 0 else "NORMAL"
    return NavigationAssessment(
        state=state,
        kind="ASSUMED",
        normal_route_eligible=True,
        delay_penalty_min=penalty,
        delay_kind="ASSUMED",
        observed_at=rhine.observed_at,
        reason=(
            "No valid official navigation adapter input is available. State uses ASSUMED delay bands "
            f"of {assumptions.navigation_restricted_penalty_min:g}/{assumptions.navigation_severe_penalty_min:g} min, "
            "with the largest level/discharge trend component; absolute Rhine values imply no official restriction."
        ),
        warnings=[],
    ), drivers


def _unknown_navigation(reason):
    return NavigationAssessment(
        state="UNKNOWN",
        kind="ASSUMED",
        normal_route_eligible=True,
        delay_penalty_min=0,
        delay_kind="ASSUMED",
        reason=f"{reason}; no official navigation state can be established. Zero assumed addition does not establish route feasibility.",
        warnings=[
            f"{reason}; navigation risk is UNKNOWN and delay may be underestimated."
        ],
    )
