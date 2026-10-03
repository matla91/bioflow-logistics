"""Deterministic decisions from comparable modeled action dimensions."""

from collections.abc import Sequence
from datetime import datetime

from baselhack.interfaces import (
    LogisticsActionResult,
    LogisticsAssumptions,
    LogisticsFeatures,
    ObservationSource,
    Recommendation,
    RecommendationPolicy,
)

ACTION_PRIORITY = {"BUFFER": 0, "EXPEDITE": 1, "REROUTE": 2}
MAX_SENSITIVITY_CHANGES = 3  # Keep the frontend explanation concise.


def recommend(
    actions: Sequence[LogisticsActionResult],
    features: LogisticsFeatures,
    assumptions: LogisticsAssumptions,
    sources: Sequence[ObservationSource],
) -> Recommendation:
    """Apply explicit continuity targets, then compare incoming-lot dimensions.

    Deprecated success probabilities never enter the decision. Confidence is an
    evidence-quality category capped at MEDIUM for assumed/simulated inputs.
    """
    policy = assumptions.recommendation_policy
    eligible = [action for action in actions if action.eligible]
    qualified = [action for action in eligible if _qualifies(action, policy)]
    buffer = next((a for a in qualified if a.action == "BUFFER"), None)
    interventions = [a for a in qualified if a.action != "BUFFER"]
    if buffer is not None and _incoming_sufficient(buffer, policy):
        selected, mode = buffer, "sufficient_buffer"
    elif interventions:
        selected, mode = min(interventions, key=_incoming_order), "intervention"
    elif buffer is not None:
        selected, mode = buffer, "continuity_buffer"
    elif eligible:
        selected = min(
            eligible,
            key=lambda a: (
                -a.production_continuity_probability,
                a.cold_chain_exposure_proxy_risk,
                a.predicted_arrival_delay_min,
                ACTION_PRIORITY[a.action],
            ),
        )
        mode = "below_target"
    else:
        selected, mode = None, "unavailable"
    action_map = {item.action: item for item in actions}
    return Recommendation(
        action=selected.action if selected is not None else None,
        confidence=(
            _evidence_quality(features, assumptions, sources)
            if selected is not None
            else "LOW"
        ),
        reason=_selection_reason(selected, mode, policy),
        why_not={
            name: _alternative_reason(action_map.get(name), selected, mode, policy)
            for name in ACTION_PRIORITY
            if selected is None or name != selected.action
        },
        would_change_if=[],
        policy_detail=(
            f"ASSUMED policy: production continuity target {_number(policy.target_production_continuity)}; "
            f"BUFFER incoming on-time target {_number(policy.target_on_time_arrival)} and "
            f"cold-chain exposure proxy cap {_number(policy.max_exposure_proxy_risk)}. "
            "Qualified shipment interventions compare lower exposure proxy, then lower "
            "incoming mean lateness, then higher on-time arrival; remaining ties use "
            "EXPEDITE before REROUTE. These are scenario criteria, not QA release rules."
        ),
    )


def with_counterfactual_changes(
    recommendation: Recommendation,
    changes: Sequence[tuple[str, Recommendation]],
) -> Recommendation:
    """Attach only decision changes demonstrated by actual model reruns.

    The caller supplies the changed-input description and its computed decision.
    This helper does not infer thresholds or extrapolate between tested cases.
    """
    descriptions = list(recommendation.would_change_if)
    for condition, counterfactual in changes:
        if counterfactual.action == recommendation.action:
            continue
        outcome = counterfactual.action or "reassessment (no eligible action)"
        text = f"{condition}: the paired model rerun selects {outcome}."
        if text not in descriptions:
            descriptions.append(text)
    return recommendation.model_copy(
        update={"would_change_if": descriptions[:MAX_SENSITIVITY_CHANGES]}
    )


def _qualifies(action: LogisticsActionResult, policy: RecommendationPolicy) -> bool:
    return (
        action.production_continuity_probability >= policy.target_production_continuity
    )


def _incoming_sufficient(
    action: LogisticsActionResult, policy: RecommendationPolicy
) -> bool:
    return (
        action.on_time_arrival_probability >= policy.target_on_time_arrival
        and action.cold_chain_exposure_proxy_risk <= policy.max_exposure_proxy_risk
    )


def _incoming_order(action: LogisticsActionResult) -> tuple[float, float, float, int]:
    return (
        action.cold_chain_exposure_proxy_risk,
        action.predicted_arrival_delay_min,
        -action.on_time_arrival_probability,
        ACTION_PRIORITY[action.action],
    )


def _metrics(action: LogisticsActionResult) -> str:
    return (
        f"production continuity {_number(action.production_continuity_probability)}, "
        f"incoming on-time arrival {_number(action.on_time_arrival_probability)}, "
        f"cold-chain exposure proxy risk {_number(action.cold_chain_exposure_proxy_risk)}, "
        f"incoming mean lateness {_number(action.predicted_arrival_delay_min, 1)} min"
    )


def _number(value: float, decimal_places: int = 3) -> str:
    """Avoid rounding distinct values to apparently equal comparison numbers."""
    formatted = f"{value:.{decimal_places}f}"
    return formatted if float(formatted) == value else str(value)


def _selection_reason(selected, mode, policy):
    if selected is None:
        return "No evaluated action is eligible; reassess stock availability and route feasibility."
    metrics = f"{selected.action}: {_metrics(selected)}. "
    if mode == "sufficient_buffer":
        return metrics + (
            "BUFFER meets the continuity target and both incoming shipment criteria; "
            "the modeled stock coverage needs no additional shipment intervention."
        )
    if mode == "intervention":
        return metrics + (
            f"It meets the production continuity target {_number(policy.target_production_continuity)}; "
            "eligible shipment interventions meeting that target are compared by "
            "lower exposure proxy, lower incoming lateness, then higher on-time arrival."
        )
    if mode == "continuity_buffer":
        return metrics + (
            f"BUFFER meets the continuity target {_number(policy.target_production_continuity)}; "
            "no eligible shipment intervention meets that target. Incoming shipment "
            "criteria remain unmet despite the factory stock coverage."
        )
    return metrics + (
        f"No eligible action meets the continuity target {_number(policy.target_production_continuity)}. "
        "This action has the highest modeled continuity; ties favor lower exposure "
        "proxy, lower incoming lateness, then deterministic action priority. Reassessment is needed."
    )


def _alternative_reason(alternative, selected, mode, policy):
    if alternative is None:
        return "No evaluated action was supplied."
    if not alternative.eligible:
        return f"Ineligible: {alternative.reason}"
    if selected is None:
        return "No eligible action was selected; reassessment is needed."
    metrics = f"{alternative.action}: {_metrics(alternative)}. "
    if mode == "sufficient_buffer":
        return (
            metrics
            + "BUFFER already meets all policy criteria without an additional intervention."
        )
    if not _qualifies(alternative, policy) and mode != "below_target":
        return metrics + (
            f"Production continuity {_number(alternative.production_continuity_probability)} "
            f"is below the policy target {_number(policy.target_production_continuity)}."
        )
    if alternative.action == "BUFFER" and mode == "intervention":
        failures = []
        if alternative.on_time_arrival_probability < policy.target_on_time_arrival:
            failures.append(
                f"incoming on-time arrival {_number(alternative.on_time_arrival_probability)} "
                f"is below {_number(policy.target_on_time_arrival)}"
            )
        if alternative.cold_chain_exposure_proxy_risk > policy.max_exposure_proxy_risk:
            failures.append(
                f"cold-chain exposure proxy {_number(alternative.cold_chain_exposure_proxy_risk)} "
                f"exceeds {_number(policy.max_exposure_proxy_risk)}"
            )
        return (
            metrics
            + "Factory continuity alone is insufficient: "
            + "; ".join(failures)
            + "."
        )
    if (
        mode == "below_target"
        and alternative.production_continuity_probability
        < selected.production_continuity_probability
    ):
        return metrics + (
            f"Its continuity is lower than {selected.action}'s "
            f"{_number(selected.production_continuity_probability)}; no eligible action meets the target."
        )
    return metrics + _incoming_comparison(
        alternative, selected, include_on_time=mode != "below_target"
    )


def _incoming_comparison(alternative, selected, *, include_on_time=True):
    if (
        alternative.cold_chain_exposure_proxy_risk
        != selected.cold_chain_exposure_proxy_risk
    ):
        return (
            f"Its exposure proxy risk {_number(alternative.cold_chain_exposure_proxy_risk)} "
            f"is higher than {selected.action}'s {_number(selected.cold_chain_exposure_proxy_risk)}."
        )
    if alternative.predicted_arrival_delay_min != selected.predicted_arrival_delay_min:
        return (
            f"Exposure proxies are tied; its incoming mean lateness "
            f"{_number(alternative.predicted_arrival_delay_min, 1)} min is higher than "
            f"{selected.action}'s {_number(selected.predicted_arrival_delay_min, 1)} min."
        )
    if include_on_time and (
        alternative.on_time_arrival_probability != selected.on_time_arrival_probability
    ):
        return (
            "Exposure and incoming lateness are tied; its on-time arrival "
            f"{_number(alternative.on_time_arrival_probability)} is lower than "
            f"{selected.action}'s {_number(selected.on_time_arrival_probability)}."
        )
    return f"Decision dimensions are tied; deterministic action priority chooses {selected.action}."


def _fresh(as_of: datetime, observed_at: datetime, max_age_min: float) -> bool:
    return 0 <= (as_of - observed_at).total_seconds() / 60 <= max_age_min


def _evidence_quality(features, assumptions, sources):
    """Fresh complete modeled signals and source coverage allow MEDIUM only."""
    if features.warnings or not features.traffic:
        return "LOW"
    if any(
        feature.status != "ok"
        or feature.z_score is None
        or feature.baseline_mean is None
        or feature.baseline_sd is None
        or feature.baseline_sample_count < assumptions.baseline_min_samples
        or not _fresh(
            features.as_of, feature.interval_end, assumptions.max_traffic_age_min
        )
        for feature in features.traffic
    ):
        return "LOW"
    rhine, weather = features.rhine, features.weather
    if (
        rhine is None
        or rhine.level_masl is None
        or rhine.discharge_m3_s is None
        or rhine.level_trend_cm_per_hour is None
        or rhine.discharge_trend_m3_s_per_hour is None
        or not _fresh(features.as_of, rhine.observed_at, assumptions.max_rhine_age_min)
        or weather is None
        or weather.precipitation_mm is None
        or weather.wind_speed_m_s is None
        or not _fresh(
            features.as_of, weather.observed_at, assumptions.max_weather_age_min
        )
    ):
        return "LOW"
    datasets = {source.dataset for source in sources if source.real_data}
    weather_source = any(
        source.real_data
        and "meteoswiss" in source.provider.lower()
        and "bas" in source.dataset.lower()
        for source in sources
    )
    return "MEDIUM" if {"100006", "100089"} <= datasets and weather_source else "LOW"
