"""THE shared contract source: models, action vocabulary and part signatures.

Run pixi run contracts to generate JSON Schemas and TypeScript declarations.
Every artifact preserves real observation provenance and ASSUMED inputs.
"""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, Protocol

from pydantic import (
    AfterValidator,
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


class LogisticsFeatures(Contract):
    as_of: Timestamp
    traffic: list[TrafficFeature]
    rhine: RhineFeatures | None
    weather: WeatherFeatures | None
    warnings: list[str]


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

    @model_validator(mode="after")
    def future_deadline(self):
        if self.deadline_at < self.as_of:
            raise ValueError("Shipment deadline must be at or after as_of")
        return self


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

    @model_validator(mode="after")
    def ordered_band(self):
        if self.ambient_reference_band_c[0] >= self.ambient_reference_band_c[1]:
            raise ValueError("Ambient reference band must be ordered")
        if self.trend_min_span_min > self.trend_window_min:
            raise ValueError("Minimum trend span must fit inside the trend window")
        return self


class LogisticsActionResult(Contract):
    action: Literal["BUFFER", "EXPEDITE", "REROUTE"]
    eligible: bool
    success_probability: Probability
    predicted_delay_min: Nonnegative
    delay_risk: Probability
    shipment_thermal_exposure_risk: Probability
    reason: Text


class RiskDriver(Contract):
    name: Text
    value: Finite
    unit: Text
    estimated_delay_contribution_min: Nonnegative
    explanation: Text
    evidence_kind: Literal["observed", "assumed"]


class LogisticsResult(Contract):
    """Probabilities are Monte Carlo frequencies under assumptions, not calibration.

    predicted_delay_min is mean lateness beyond the simulated deadline. delay_risk
    uses delay_threshold_min. Thermal risk is P(ambient degree-minute proxy exceeds
    its assumed budget), with no claim of actual product-temperature excursions.
    Success means factory lateness <= threshold AND exposure proxy <= budget;
    BUFFER instead needs sufficient stock, independent of the incoming lot's proxy.
    """

    shipment_id: Text
    as_of: Timestamp
    predicted_delay_min: Nonnegative
    delay_risk: Probability
    thermal_exposure_risk: Probability
    action_success_probabilities: dict[
        Literal["BUFFER", "EXPEDITE", "REROUTE"], Probability
    ]
    actions: list[LogisticsActionResult]
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
        return self


# These have separate cache/output homes; legacy scenes do not require them.
LOGISTICS_MODELS = {
    "logistics": LogisticsResult,
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
