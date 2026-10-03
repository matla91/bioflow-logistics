"""THE shared contract source: models, action vocabulary and part signatures.

Run pixi run contracts to generate JSON Schemas and TypeScript declarations.
Every artifact preserves real observation provenance and ASSUMED inputs.
"""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, Protocol

from pydantic import (
    AfterValidator,
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    model_validator,
)


def offset_required(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timestamp must have an explicit UTC offset")
    return value


Timestamp = Annotated[datetime, AfterValidator(offset_required)]
Probability = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
Nonnegative = Annotated[float, Field(ge=0, allow_inf_nan=False)]
Positive = Annotated[float, Field(gt=0, allow_inf_nan=False)]
Finite = Annotated[float, Field(allow_inf_nan=False)]
Text = Annotated[str, Field(min_length=1)]
ReasonText = Annotated[str, Field(min_length=1, pattern=r"\S")]
Sources = Annotated[dict[str, Text], Field(min_length=1)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Action(StrEnum):
    RUN_AS_PLANNED = "RUN_AS_PLANNED"
    EXPEDITE = "EXPEDITE"
    BUFFER = "BUFFER"
    REROUTE = "REROUTE"
    QUARANTINE = "QUARANTINE"


Role = Literal["operator", "logistics", "QA"]


class TemperaturePoint(Contract):
    t: Timestamp
    c: Finite


class GaugePoint(Contract):
    t: Timestamp
    v: Finite


class Position(Contract):
    lat: Annotated[float, Field(ge=-90, le=90)]
    lon: Annotated[float, Field(ge=-180, le=180)]


class RouteSegment(Contract):
    id: Text
    kind: Literal["leg", "handover"]
    refrigerated: bool
    planned_min: Positive
    distribution: Literal["normal", "triangular", "fixed"]
    place: Literal["rotterdam", "basel"]
    position: Position
    sd_min: Nonnegative | None = None
    triangular_min: tuple[Positive, Positive, Positive] | None = None


class Slot(Contract):
    reactor: Text
    charge_at: Timestamp


class Ambient(Contract):
    rotterdam: list[TemperaturePoint]
    basel: list[TemperaturePoint]


class Rhine(Contract):
    kaub_cm: list[GaugePoint]
    basel_cm: list[GaugePoint]


class Traffic(Contract):
    factor_by_hour: dict[str, Annotated[float, Field(ge=1)]]


class Site(Contract):
    reactor: Text
    charge_hour: Annotated[int, Field(ge=0, le=23)]
    timezone: Text
    reactor_drift_sd_min: Nonnegative
    stock_batches: Annotated[int, Field(ge=0)]
    batch_stock_required: Annotated[int, Field(ge=1)]
    lot: Text


class Material(Contract):
    range_c: tuple[Finite, Finite]
    budget_min: Positive
    setpoint_c: Finite
    tau_reefer_min: Positive
    tau_exposed_min: Positive
    recovery_horizon_min: Positive


class RiverBand(Contract):
    min_cm: Finite
    factor: Positive


class Thresholds(Contract):
    river_bands: list[RiverBand]
    river_suspension_below_cm: Finite
    basel_high_water_cm: Finite | None
    p_miss_slot_low: Probability
    p_excursion_quarantine: Probability
    budget_warning_fraction: Probability
    monte_carlo_runs: Annotated[int, Field(ge=1)]
    suspension_delay_min: Positive
    expedite_wait_factor: Probability
    expedite_truck_slot_wait_min: Nonnegative
    reroute_truck_min: Positive
    reroute_truck_sd_min: Nonnegative
    reroute_extra_handover_min: Nonnegative
    traffic_default_factor: Annotated[float, Field(ge=1)]
    traffic_capacity_per_hour: Positive
    traffic_sensitivity: Nonnegative
    traffic_max_factor: Annotated[float, Field(ge=1)]
    traffic_station_ids: list[str]
    gauge_max_change_cm_per_hour: Positive
    forecast_days: Annotated[int, Field(ge=1)]


class Scenario(Contract):
    scenario_id: Text
    seed: Annotated[int, Field(ge=0)]
    start_at: Timestamp
    basel_unload_at: Timestamp | None = None
    slot: Slot
    route: list[RouteSegment]
    ambient: Ambient
    rhine: Rhine
    traffic: Traffic
    site: Site
    material: Material
    thresholds: Thresholds
    overrides: dict[str, Finite]
    simulated_kaub_cm: Finite | None
    verification: list[Text]
    sources: Sources


class TimelineStep(Contract):
    t: Timestamp
    segment: Text
    position: Position
    refrigerated: bool
    ambient_c: Finite
    product_c: Finite
    excursion_min: Nonnegative
    budget_used: Nonnegative
    source: Text


class Timeline(Contract):
    scenario_id: Text
    seed: Annotated[int, Field(ge=0)]
    action: Action
    steps: list[TimelineStep]
    eta: Timestamp | None
    readiness_at: Timestamp
    excursion_min: Nonnegative
    budget_used: Nonnegative
    status: Literal["arrived", "suspended"]
    stock_after: Annotated[int, Field(ge=0)]
    batch_delay_min: Nonnegative
    sources: Sources


class ActionRisk(Contract):
    exp_delay_min: Nonnegative
    p_miss_slot: Probability
    p_excursion: Probability
    stock_after: Annotated[int, Field(ge=0)]
    eligible: bool
    reason: Text


class GaugeFlag(Contract):
    station: Text
    t: Timestamp
    flag: Text
    detail: Text


class RiverForecastPoint(Contract):
    t: Timestamp
    kaub_cm_p50: Finite
    kaub_cm_p90: Finite


class Risk(Contract):
    scenario_id: Text
    n_runs: Annotated[int, Field(ge=1)]
    eta_p50: Timestamp | None
    eta_p90: Timestamp | None
    p_miss_slot: Probability
    p_excursion: Probability
    per_action: Annotated[
        dict[Action, ActionRisk], Field(min_length=len(Action), max_length=len(Action))
    ]
    gauge_flags: list[GaugeFlag]
    river_forecast: list[RiverForecastPoint]
    model: Text
    sources: Sources

    @model_validator(mode="after")
    def all_actions(self):
        if set(self.per_action) != set(Action):
            raise ValueError("Risk must report every action exactly once")
        return self


class EvidenceReason(Contract):
    n: Annotated[int, Field(ge=1)]
    text: Text
    source: Text
    at: Timestamp


class Rejection(Contract):
    action: Action
    reason: Text
    source: Text
    at: Timestamp


class Decision(Contract):
    decision_id: Text
    scenario_id: Text
    lot: Text
    slot: Text
    recommended: Action
    headline: Text
    rejected: list[Rejection]
    reasons: list[EvidenceReason]
    would_change_if: list[Text]
    requires_approval_by: Role
    explanation: Text
    sources: Sources


class LogEntry(Contract):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "allOf": [
                {
                    "if": {"properties": {"verdict": {"const": "OVERRIDE"}}},
                    "then": {
                        "required": ["chosen_action"],
                        "properties": {"chosen_action": {"not": {"type": "null"}}},
                    },
                },
                {
                    "if": {
                        "properties": {"chosen_action": {"const": "QUARANTINE"}},
                        "required": ["chosen_action"],
                    },
                    "then": {"properties": {"by": {"const": "QA"}}},
                },
            ]
        },
    )
    decision_id: Text
    by: Role
    verdict: Literal["APPROVE", "OVERRIDE"]
    reason: ReasonText
    at: Timestamp
    decision_snapshot_sha256: Annotated[str, Field(pattern="^[a-f0-9]{64}$")]
    chosen_action: Action | None = None

    @model_validator(mode="after")
    def override_requires_action(self):
        if self.verdict == "OVERRIDE" and self.chosen_action is None:
            raise ValueError("Override requires a chosen action")
        if self.chosen_action == Action.QUARANTINE and self.by != "QA":
            raise ValueError("Only QA may choose quarantine")
        return self


class Log(RootModel[list[LogEntry]]):
    pass


class DemoVariant(Contract):
    id: Text
    label: Text
    value: Finite
    unit: Text
    ready: bool
    recommended: Action | None = None
    error: Text | None = None
    source: Text


class DemoVariants(RootModel[list[DemoVariant]]):
    pass


ARTIFACT_MODELS = {
    "scenario": Scenario,
    "timeline": Timeline,
    "risk": Risk,
    "decision": Decision,
    "log": Log,
    "variants": DemoVariants,
}


class Simulator(Protocol):
    def __call__(
        self,
        scenario: dict,
        seed: int,
        action: Action = Action.RUN_AS_PLANNED,
        record: bool = True,
    ) -> dict: ...


class ScenarioBuilder(Protocol):
    def __call__(self, scene: str, overrides: dict | None = None) -> dict: ...


class DecisionAnalysis(Protocol):
    def __call__(self, scenario: dict, n_runs: int | None = None) -> dict: ...


class RuleEngine(Protocol):
    def __call__(self, scenario: dict, timeline: dict, risk: dict) -> dict: ...


# Additive Basel snapshot contracts. Legacy journey artifacts remain unchanged.
class ObservationSource(Contract):
    """Provenance for observed external data, never shipment/factory assumptions."""

    provider: Text
    dataset: Text
    url: Text
    retrieved_at: Timestamp
    licence: Text
    real_data: Literal[True] = True
    sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")] | None = None


class TrafficObservation(Contract):
    """Sum of distinct approved lanes at one station over one complete UTC hour."""

    station_id: Text
    interval_start: Timestamp
    interval_end: Timestamp
    vehicle_count: Nonnegative

    @model_validator(mode="after")
    def hourly_interval(self):
        if (self.interval_end - self.interval_start).total_seconds() != 3600:
            raise ValueError("Traffic observation must cover exactly one hour")
        return self


class RhineObservation(Contract):
    """Basel 100089: level in metres above sea level, discharge in m³/s."""

    t: Timestamp
    station_id: Text = "2289"
    level_masl: Finite | None = None
    discharge_m3_s: Nonnegative | None = None


class WeatherObservation(Contract):
    """MeteoSwiss BAS hourly observation; t is the UTC interval ending."""

    t: Timestamp
    station_id: Literal["BAS"] = "BAS"
    air_temperature_c: Finite
    precipitation_mm: Nonnegative | None = None
    wind_speed_m_s: Nonnegative | None = None
    relative_humidity_pct: Annotated[float, Field(ge=0, le=100)] | None = None


class RealObservations(Contract):
    traffic: list[TrafficObservation]
    rhine: list[RhineObservation]
    weather: list[WeatherObservation]
    sources: Annotated[list[ObservationSource], Field(min_length=1)]


class TrafficBaseline(Contract):
    station_id: Text
    weekday: Annotated[int, Field(ge=0, le=6)]
    hour: Annotated[int, Field(ge=0, le=23)]
    sample_count: Annotated[int, Field(ge=1)]
    mean_count: Nonnegative
    sd_count: Nonnegative


class TrafficFeature(Contract):
    station_id: Text
    interval_end: Timestamp
    observed_count: Nonnegative
    baseline_mean: Nonnegative | None
    baseline_sd: Nonnegative | None
    baseline_sample_count: Annotated[int, Field(ge=0)]
    z_score: Finite | None
    status: Literal["ok", "missing_baseline", "zero_variance"]


class RhineFeatures(Contract):
    observed_at: Timestamp
    level_masl: Finite | None
    discharge_m3_s: Nonnegative | None
    level_trend_cm_per_hour: Finite | None
    discharge_trend_m3_s_per_hour: Finite | None
    sample_count: Annotated[int, Field(ge=1)]


class WeatherFeatures(Contract):
    observed_at: Timestamp
    air_temperature_c: Finite
    precipitation_mm: Nonnegative | None
    wind_speed_m_s: Nonnegative | None
    relative_humidity_pct: Annotated[float, Field(ge=0, le=100)] | None
    temperature_trend_c_per_hour: Finite | None


ProvenanceKind = Literal["REAL", "OFFICIAL_FORECAST", "MODEL", "SIMULATED", "ASSUMED"]
LogisticsAction = Literal["BUFFER", "EXPEDITE", "REROUTE"]
NavigationState = Literal["NORMAL", "WATCH", "RESTRICTED", "SEVERE", "UNKNOWN"]


class OfficialNavigationSignal(Contract):
    """Future adapter input; no official feed is integrated by the current demo.

    State/route eligibility must come from the identified official source. A
    missing delay estimate remains missing and uses a labelled assumed fallback.
    """

    kind: Literal["REAL", "OFFICIAL_FORECAST"]
    state: Literal["NORMAL", "WATCH", "RESTRICTED", "SEVERE"]
    provider: Text
    source_url: Text
    issued_at: Timestamp
    valid_from: Timestamp
    valid_until: Timestamp
    normal_route_eligible: bool
    expected_delay_min: Nonnegative | None = None

    @model_validator(mode="after")
    def valid_window(self):
        if self.valid_until < self.valid_from or self.issued_at > self.valid_until:
            raise ValueError(
                "Official navigation signal has an invalid validity window"
            )
        return self


class NavigationAssessment(Contract):
    """Official state if supplied and valid; otherwise an ASSUMED trend scenario.

    Delay provenance is independent of status provenance. No state implies an
    official hydrological threshold or navigation restriction without an adapter.
    """

    state: NavigationState
    kind: ProvenanceKind
    normal_route_eligible: bool
    delay_penalty_min: Nonnegative
    delay_kind: ProvenanceKind
    reported_delay_min: Nonnegative | None = None
    provider: Text | None = None
    observed_at: Timestamp | None = None
    reason: Text
    warnings: list[str] = []


class LogisticsFeatures(Contract):
    as_of: Timestamp
    traffic: list[TrafficFeature]
    rhine: RhineFeatures | None
    weather: WeatherFeatures | None
    warnings: list[str]
    official_navigation: OfficialNavigationSignal | None = None


class ShipmentState(Contract):
    """All fields are SIMULATED. Transport minutes exclude handling minutes.

    Protection autonomy is remaining whole-journey time until packaging protection
    is assumed to expire. BUFFER covers the factory deadline from assumed stock.
    """

    simulated: Literal[True] = True
    shipment_id: Text
    as_of: Timestamp
    deadline_at: Timestamp
    route_mode: Literal["river", "road"]
    planned_remaining_min: Positive
    handling_min: Nonnegative
    protection_remaining_min: Nonnegative
    prior_exposure_degree_min: Nonnegative = 0
    stock_available: Annotated[int, Field(ge=0)]
    stock_required: Annotated[int, Field(ge=1)] = 1
    expedite_available: bool = True
    reroute_available: bool = True

    @model_validator(mode="after")
    def future_deadline(self):
        if self.deadline_at < self.as_of:
            raise ValueError("Shipment deadline must be at or after as_of")
        return self


class RecommendationPolicy(Contract):
    """Assumed service targets for deterministic decisions, not calibrated limits."""

    target_production_continuity: Probability = 0.95
    target_on_time_arrival: Probability = 0.90
    max_exposure_proxy_risk: Probability = 0.10
    sensitivity_factors: tuple[Positive, ...] = (0.5, 1.5, 2.0)


class LogisticsAssumptions(Contract):
    """Uncalibrated scenario coefficients, never provider facts or QA limits."""

    assumed: Literal[True] = True
    n_runs: Annotated[int, Field(ge=1, le=1000000)]
    seed: Annotated[int, Field(ge=0)]
    transport_sd_min: Nonnegative
    handling_sd_min: Nonnegative
    traffic_min_per_positive_z: Nonnegative
    traffic_z_cap: Positive
    falling_level_min_per_cm_hour: Nonnegative
    falling_discharge_min_per_m3_s_hour: Nonnegative
    river_penalty_cap_min: Nonnegative
    rain_min_per_mm: Nonnegative
    wind_threshold_m_s: Nonnegative
    wind_min_per_m_s: Nonnegative
    delay_threshold_min: Nonnegative
    ambient_reference_band_c: tuple[Finite, Finite]
    exposure_budget_degree_min: Positive
    expedite_transport_factor: Annotated[float, Field(gt=0, le=1)]
    expedite_handling_factor: Annotated[float, Field(gt=0, le=1)]
    reroute_transport_min: Positive
    reroute_transport_sd_min: Nonnegative
    reroute_extra_handling_min: Nonnegative
    reroute_traffic_factor: Probability
    max_traffic_age_min: Positive
    max_rhine_age_min: Positive
    max_weather_age_min: Positive
    trend_window_min: Positive
    trend_min_span_min: Positive
    baseline_min_samples: Annotated[int, Field(ge=2)]
    navigation_restricted_penalty_min: Positive = 30
    navigation_severe_penalty_min: Positive = 60
    route_block_delay_min: Positive = 1440
    recommendation_policy: RecommendationPolicy = Field(
        default_factory=RecommendationPolicy
    )

    @model_validator(mode="after")
    def ordered_band(self):
        if self.ambient_reference_band_c[0] >= self.ambient_reference_band_c[1]:
            raise ValueError("Ambient reference band must be ordered")
        if self.trend_min_span_min > self.trend_window_min:
            raise ValueError("Minimum trend span must fit inside the trend window")
        if self.navigation_restricted_penalty_min >= self.navigation_severe_penalty_min:
            raise ValueError("Assumed navigation delay bands must be ordered")
        return self


class LogisticsActionResult(Contract):
    """Separate production timing, shipment timing and ambient exposure outcomes.

    Arrival and production continuity use the exact deadline, without the legacy
    delay tolerance. Factory timing is independent of ambient proxy exceedance;
    no pharmaceutical usability or QA release is inferred. BUFFER may cover the
    factory while incoming arrival/exposure remain poor.
    """

    action: LogisticsAction
    eligible: bool
    production_continuity_probability: Probability
    on_time_arrival_probability: Probability
    cold_chain_exposure_proxy_risk: Probability = Field(
        validation_alias=AliasChoices(
            "cold_chain_exposure_proxy_risk", "shipment_thermal_exposure_risk"
        )
    )
    predicted_delay_min: Nonnegative
    predicted_arrival_delay_min: Nonnegative
    delay_risk: Probability
    assessment: Text
    reason: Text
    success_probability: Probability = Field(
        description="DEPRECATED: BUFFER stock coverage, otherwise joint factory lateness <= tolerance and ambient proxy <= budget. Not comparable across actions; never used for recommendations.",
        json_schema_extra={"deprecated": True},
    )

    @property
    def shipment_thermal_exposure_risk(self) -> float:
        """Deprecated read alias. JSON uses cold_chain_exposure_proxy_risk."""
        return self.cold_chain_exposure_proxy_risk


class Recommendation(Contract):
    """Deterministic scenario recommendation; confidence describes evidence quality."""

    action: LogisticsAction | None
    confidence: Literal["HIGH", "MEDIUM", "LOW"]
    reason: Text
    why_not: dict[LogisticsAction, Text]
    would_change_if: list[Text]
    policy_detail: Text


class ProvenanceSummary(Contract):
    """Indices refer to full detailed-output source metadata; no repeated URLs."""

    kind: ProvenanceKind
    provider: Text | None = None
    observed_at: Timestamp | None = None
    source_indices: list[Annotated[int, Field(ge=0)]] = []
    detail: Text


class RiskDriver(Contract):
    name: Text
    value: Finite
    unit: Text
    estimated_delay_contribution_min: Nonnegative
    explanation: Text
    evidence_kind: Literal[
        "observed", "official_forecast", "model", "simulated", "assumed"
    ]


class LogisticsResult(Contract):
    """Probabilities are Monte Carlo frequencies under assumptions, not calibration.

    predicted_delay_min is mean lateness beyond the simulated deadline. delay_risk
    uses delay_threshold_min. Proxy risk is P(ambient degree-minute proxy exceeds
    its assumed budget), with no claim of actual product-temperature excursions.
    Success means factory lateness <= threshold AND exposure proxy <= budget;
    BUFFER instead needs sufficient stock, independent of the incoming lot's proxy.
    """

    shipment_id: Text
    as_of: Timestamp
    predicted_delay_min: Nonnegative
    delay_risk: Probability
    cold_chain_exposure_proxy_risk: Probability = Field(
        validation_alias=AliasChoices(
            "cold_chain_exposure_proxy_risk", "thermal_exposure_risk"
        )
    )
    action_success_probabilities: dict[
        Literal["BUFFER", "EXPEDITE", "REROUTE"], Probability
    ] = Field(
        description="DEPRECATED: action-specific legacy success events; do not compare or use for recommendations.",
        json_schema_extra={"deprecated": True},
    )
    actions: list[LogisticsActionResult]
    navigation: NavigationAssessment
    recommendation: Recommendation
    data_provenance: dict[str, ProvenanceSummary]
    main_risk_drivers: list[RiskDriver]
    features: LogisticsFeatures
    simulated_shipment: ShipmentState
    assumptions: LogisticsAssumptions
    real_data_sources: Annotated[list[ObservationSource], Field(min_length=1)]
    limitations: list[Text]
    model: Text

    @model_validator(mode="after")
    def three_actions(self):
        expected = {"BUFFER", "EXPEDITE", "REROUTE"}
        if set(self.action_success_probabilities) != expected:
            raise ValueError("All three action success probabilities are required")
        if len(self.actions) != 3 or {a.action for a in self.actions} != expected:
            raise ValueError("All three action details are required")
        for action in self.actions:
            if (
                self.action_success_probabilities[action.action]
                != action.success_probability
            ):
                raise ValueError("Action details and success probabilities must agree")
        if self.recommendation.action is not None:
            chosen = next(
                a for a in self.actions if a.action == self.recommendation.action
            )
            if not chosen.eligible:
                raise ValueError("Recommended action must be eligible")
        if set(self.recommendation.why_not) != expected - {self.recommendation.action}:
            raise ValueError("Recommendation must explain all alternatives")
        return self

    @property
    def thermal_exposure_risk(self) -> float:
        """Deprecated read alias. JSON uses cold_chain_exposure_proxy_risk."""
        return self.cold_chain_exposure_proxy_risk


class ExternalState(Contract):
    rhine: RhineFeatures | None
    traffic: list[TrafficFeature]
    weather: WeatherFeatures | None
    navigation: NavigationAssessment
    warnings: list[str]


class OperationalImpact(Contract):
    """Baseline factory lateness and ambient proxy frequencies under assumptions."""

    predicted_delay_min: Nonnegative
    delay_risk: Probability
    cold_chain_exposure_proxy_risk: Probability


class FrontendAction(Contract):
    """Comparable scenario dimensions; deprecated legacy success is excluded."""

    action: LogisticsAction
    eligible: bool
    production_continuity_probability: Probability
    on_time_arrival_probability: Probability
    cold_chain_exposure_proxy_risk: Probability
    predicted_delay_min: Nonnegative
    predicted_arrival_delay_min: Nonnegative
    assessment: Text
    reason: Text


class LogisticsFrontendResult(Contract):
    """Primary frontend contract. Internal Monte Carlo/source details stay separate."""

    as_of: Timestamp
    shipment_id: Text
    external_state: ExternalState
    simulated_shipment: ShipmentState
    operational_impact: OperationalImpact
    actions: list[FrontendAction]
    recommendation: Recommendation
    data_provenance: dict[str, ProvenanceSummary]
    limitations: list[Text]

    @model_validator(mode="after")
    def complete_action_comparison(self):
        expected = {"BUFFER", "EXPEDITE", "REROUTE"}
        if len(self.actions) != 3 or {a.action for a in self.actions} != expected:
            raise ValueError("All three frontend action dimensions are required")
        if (
            self.recommendation.action is not None
            and not next(
                a for a in self.actions if a.action == self.recommendation.action
            ).eligible
        ):
            raise ValueError("Recommended action must be eligible")
        if set(self.recommendation.why_not) != expected - {self.recommendation.action}:
            raise ValueError("Recommendation must explain all alternatives")
        return self


class StoredLogisticsAssessment(Contract):
    """Immutable named-scenario result; not an operational batch/QA assessment."""

    assessment_id: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    input_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    scenario: Literal["normal", "disruption", "severe"]
    model_version: Text
    result: LogisticsFrontendResult


# These have separate cache/output homes; legacy scenes do not require them.
LOGISTICS_MODELS = {
    "stored-logistics-assessment": StoredLogisticsAssessment,
    "logistics": LogisticsResult,
    "logistics-frontend": LogisticsFrontendResult,
    "real-observations": RealObservations,
    "shipment-state": ShipmentState,
    "logistics-assumptions": LogisticsAssumptions,
}


class LogisticsFeatureBuilder(Protocol):
    def __call__(
        self,
        observations: RealObservations,
        as_of: datetime,
        assumptions: LogisticsAssumptions,
        station_ids: list[str],
    ) -> LogisticsFeatures: ...


class LogisticsSimulation(Protocol):
    def __call__(
        self,
        shipment: ShipmentState,
        features: LogisticsFeatures,
        assumptions: LogisticsAssumptions,
        sources: list[ObservationSource],
    ) -> LogisticsResult: ...


class OperationalMaterial(Contract):
    """Synthetic demo material; quantities are consistently expressed in kg."""

    id: Text
    name: Text
    quantity_unit: Literal["kg"] = "kg"
    range_c: tuple[Finite, Finite]
    budget_min: Positive

    @model_validator(mode="after")
    def ordered_range(self):
        if self.range_c[0] >= self.range_c[1]:
            raise ValueError("Material temperature range must be increasing")
        return self


class OperationalShipment(Contract):
    """Planned and observed milestones are separate; no future actuals."""

    id: Text
    material_id: Text
    lot_id: Text
    quantity_kg: Positive
    route_mode: Literal["river", "road"]
    origin: Text
    destination: Text
    planned_departure_at: Timestamp
    planned_arrival_at: Timestamp
    actual_departure_at: Timestamp | None
    actual_arrival_at: Timestamp | None
    status: Literal["planned", "in_transit", "arrived", "suspended"]
    scenario: Literal["normal", "heat", "delay", "planned"]

    @model_validator(mode="after")
    def ordered_milestones(self):
        if self.planned_arrival_at <= self.planned_departure_at:
            raise ValueError("Planned arrival must follow departure")
        if self.actual_arrival_at is not None and (
            self.actual_departure_at is None
            or self.actual_arrival_at < self.actual_departure_at
        ):
            raise ValueError("Actual arrival must follow actual departure")
        if self.status == "planned" and self.actual_departure_at is not None:
            raise ValueError("Planned shipments cannot have actual departure")
        if self.status == "arrived" and self.actual_arrival_at is None:
            raise ValueError("Arrived shipments require actual arrival")
        return self


class ProductionBatch(Contract):
    """Synthetic demand for one material at one reactor charge slot."""

    id: Text
    reactor: Text
    material_id: Text
    required_quantity_kg: Positive
    planned_charge_at: Timestamp
    status: Literal["planned", "waiting_material"]


class BatchSupplyPlan(Contract):
    """Planned incoming supply; this does not reserve released inventory."""

    batch_id: Text
    shipment_id: Text
    quantity_kg: Positive


class InventoryLot(Contract):
    """On-site stock; QA disposition is explicit synthetic fixture state."""

    id: Text
    material_id: Text
    quantity_kg: Nonnegative
    available_at: Timestamp
    qa_status: Literal["released", "pending", "quarantined"]
    shipment_id: Text | None = None


class StockReservation(Contract):
    batch_id: Text
    inventory_lot_id: Text
    quantity_kg: Positive


class ShipmentReading(Contract):
    shipment_id: Text
    at: Timestamp
    product_c: Finite
    ambient_c: Finite
    refrigerated: bool
    excursion_min: Nonnegative


class OperationalDataset(Contract):
    """Reproducible operations fixture, separate from ML training feature CSVs."""

    dataset_id: Text
    simulated: Literal[True] = True
    seed: Annotated[int, Field(ge=0)]
    reference_at: Timestamp
    materials: list[OperationalMaterial]
    shipments: list[OperationalShipment]
    batches: list[ProductionBatch]
    supply_plans: list[BatchSupplyPlan]
    inventory: list[InventoryLot]
    reservations: list[StockReservation]
    readings: list[ShipmentReading]
    assumptions: dict[str, object]


LOGISTICS_MODELS["operational-dataset"] = OperationalDataset
