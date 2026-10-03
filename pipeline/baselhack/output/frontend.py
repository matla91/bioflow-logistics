"""Compact presentation contract and concise evidence labels for logistics.

Source indices refer to the full ``real_data_sources`` list in the detailed
result. This module labels evidence; it neither predicts nor selects an action.
"""

import json
from pathlib import Path

from baselhack.interfaces import (
    ExternalState,
    FrontendAction,
    LogisticsAssumptions,
    LogisticsFeatures,
    LogisticsFrontendResult,
    LogisticsResult,
    NavigationAssessment,
    ObservationSource,
    OperationalImpact,
    ProvenanceSummary,
    ShipmentState,
)


def _source_indices(sources: list[ObservationSource], signal: str) -> list[int]:
    """Match the integrated datasets instead of treating any metadata as evidence."""
    if signal in {"rhine", "traffic"}:
        dataset = {"rhine": "100089", "traffic": "100006"}[signal]
        return [
            index for index, source in enumerate(sources) if source.dataset == dataset
        ]
    return [
        index
        for index, source in enumerate(sources)
        if "meteoswiss" in source.provider.casefold()
        and "bas" in source.dataset.casefold()
    ]


def _observed_summary(sources, indices, observed_at, detail):
    providers = list(dict.fromkeys(sources[index].provider for index in indices))
    return ProvenanceSummary(
        kind="REAL",
        provider="; ".join(providers),
        observed_at=observed_at,
        source_indices=indices,
        detail=detail,
    )


def _fresh(observed_at, as_of, max_age_min):
    return 0 <= (as_of - observed_at).total_seconds() / 60 <= max_age_min


def provenance_summary(
    features: LogisticsFeatures,
    shipment: ShipmentState,
    assumptions: LogisticsAssumptions,
    sources: list[ObservationSource],
    navigation: NavigationAssessment,
) -> dict[str, ProvenanceSummary]:
    """Summarize evidence without calling an unavailable observation REAL.

    REAL requires both a current feature and matching declared source metadata.
    Statistical transformations are MODEL; a navigation fallback is ASSUMED.
    Merely integrating hydrological observations never creates an official
    navigation forecast. Current labels also check freshness for direct callers
    that supply features without using the normal feature builder.
    """
    rhine_sources = _source_indices(sources, "rhine")
    traffic_sources = _source_indices(sources, "traffic")
    weather_sources = _source_indices(sources, "weather")
    provenance = {
        "shipment_state": ProvenanceSummary(
            kind="SIMULATED",
            observed_at=shipment.as_of,
            detail="Shipment schedule, factory stock, route availability and packaging protection are scenario inputs.",
        ),
        "model_coefficients": ProvenanceSummary(
            kind="ASSUMED",
            detail="Delay coefficients, variability and the ambient exposure proxy budget are uncalibrated assumptions.",
        ),
        "delay_simulation": ProvenanceSummary(
            kind="MODEL",
            detail=(
                f"Seeded Monte Carlo scenario frequencies ({assumptions.n_runs} runs; "
                f"seed {assumptions.seed}), conditional on simulated state and assumed coefficients."
            ),
        ),
    }
    rhine = features.rhine
    if (
        rhine is not None
        and rhine_sources
        and _fresh(rhine.observed_at, shipment.as_of, assumptions.max_rhine_age_min)
        and (rhine.level_masl is not None or rhine.discharge_m3_s is not None)
    ):
        provenance["rhine_current"] = _observed_summary(
            sources,
            rhine_sources,
            features.rhine.observed_at,
            "Latest usable Basel Rhine level/discharge observation; no navigation forecast implied.",
        )
    current_traffic = [
        feature
        for feature in features.traffic
        if _fresh(feature.interval_end, shipment.as_of, assumptions.max_traffic_age_min)
    ]
    if current_traffic and traffic_sources:
        provenance["traffic_current"] = _observed_summary(
            sources,
            traffic_sources,
            max(feature.interval_end for feature in current_traffic),
            "Latest usable complete hourly station counts; individual timestamps remain in external_state.",
        )
    if (
        features.weather is not None
        and weather_sources
        and _fresh(
            features.weather.observed_at,
            shipment.as_of,
            assumptions.max_weather_age_min,
        )
    ):
        provenance["weather_current"] = _observed_summary(
            sources,
            weather_sources,
            features.weather.observed_at,
            "MeteoSwiss Basel/Binningen ambient observations; no product temperature is measured.",
        )
    if any(feature.z_score is not None for feature in features.traffic):
        provenance["traffic_anomaly"] = ProvenanceSummary(
            kind="MODEL",
            source_indices=traffic_sources,
            detail="Historical statistical anomaly detection using station, weekday and local-hour sample history; current observation availability is labelled separately.",
        )
    if rhine is not None and (
        rhine.level_trend_cm_per_hour is not None
        or rhine.discharge_trend_m3_s_per_hour is not None
    ):
        provenance["rhine_trends"] = ProvenanceSummary(
            kind="MODEL",
            source_indices=rhine_sources,
            detail="Bounded linear slopes of preceding observation sample history; no validated navigation relationship.",
        )
    if (
        features.weather is not None
        and features.weather.temperature_trend_c_per_hour is not None
    ):
        provenance["weather_trend"] = ProvenanceSummary(
            kind="MODEL",
            source_indices=weather_sources,
            detail="Bounded linear ambient-temperature slope from preceding sample history; no future weather forecast implied.",
        )
    provenance["rhine_navigation"] = ProvenanceSummary(
        kind=navigation.kind,
        provider=navigation.provider,
        observed_at=navigation.observed_at,
        detail=navigation.reason,
    )
    provenance["rhine_navigation_delay"] = ProvenanceSummary(
        kind=navigation.delay_kind,
        provider=navigation.provider
        if navigation.delay_kind in {"REAL", "OFFICIAL_FORECAST"}
        else None,
        observed_at=navigation.observed_at
        if navigation.delay_kind in {"REAL", "OFFICIAL_FORECAST"}
        else None,
        detail=(
            f"Navigation mean-minute addition ({navigation.delay_penalty_min:g} min) "
            "has its own provenance; an official state alone does not supply a validated delay relationship."
        ),
    )
    return provenance


def to_frontend(result: LogisticsResult) -> LogisticsFrontendResult:
    """Validate a detailed result and select the canonical frontend fields."""
    validated = LogisticsResult.model_validate(result.model_dump(mode="python"))
    return LogisticsFrontendResult(
        as_of=validated.as_of,
        shipment_id=validated.shipment_id,
        external_state=ExternalState(
            rhine=validated.features.rhine,
            traffic=validated.features.traffic,
            weather=validated.features.weather,
            navigation=validated.navigation,
            warnings=validated.features.warnings,
        ),
        simulated_shipment=validated.simulated_shipment,
        operational_impact=OperationalImpact(
            predicted_delay_min=validated.predicted_delay_min,
            delay_risk=validated.delay_risk,
            cold_chain_exposure_proxy_risk=validated.cold_chain_exposure_proxy_risk,
        ),
        actions=[
            FrontendAction(
                action=action.action,
                eligible=action.eligible,
                production_continuity_probability=action.production_continuity_probability,
                on_time_arrival_probability=action.on_time_arrival_probability,
                cold_chain_exposure_proxy_risk=action.cold_chain_exposure_proxy_risk,
                predicted_delay_min=action.predicted_delay_min,
                predicted_arrival_delay_min=action.predicted_arrival_delay_min,
                assessment=action.assessment,
                reason=action.reason,
            )
            for action in validated.actions
        ],
        recommendation=validated.recommendation,
        data_provenance=validated.data_provenance,
        limitations=[
            limitation
            for limitation in validated.limitations
            if not limitation.startswith("Deprecated success_probability")
        ],
    )


def dumps_frontend(result: LogisticsResult) -> str:
    """Serialize a compact payload with valid JSON numbers and fixed formatting."""
    return (
        json.dumps(
            to_frontend(result).model_dump(mode="json"),
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    )


def write_frontend(result: LogisticsResult, path: str | Path) -> Path:
    """Write the presentation artifact; full evidence stays in detailed output."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(dumps_frontend(result), encoding="utf-8")
    return target
