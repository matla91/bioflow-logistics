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
