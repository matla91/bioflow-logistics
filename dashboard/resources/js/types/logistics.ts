export type EvidenceKind =
    | 'REAL'
    | 'OFFICIAL_FORECAST'
    | 'MODEL'
    | 'SIMULATED'
    | 'ASSUMED';

export type LogisticsAction = 'BUFFER' | 'EXPEDITE' | 'REROUTE';

export type TrafficFeature = {
    station_id: string;
    interval_end: string;
    observed_count: number;
    baseline_mean: number | null;
    baseline_sd: number | null;
    baseline_sample_count: number;
    z_score: number | null;
    status: 'ok' | 'missing_baseline' | 'zero_variance';
};

export type RhineFeatures = {
    observed_at: string;
    level_masl: number | null;
    discharge_m3_s: number | null;
    level_trend_cm_per_hour: number | null;
    discharge_trend_m3_s_per_hour: number | null;
    sample_count: number;
};

export type WeatherFeatures = {
    observed_at: string;
    air_temperature_c: number;
    precipitation_mm: number | null;
    wind_speed_m_s: number | null;
    relative_humidity_pct: number | null;
    temperature_trend_c_per_hour: number | null;
};

export type NavigationAssessment = {
    state: 'NORMAL' | 'WATCH' | 'RESTRICTED' | 'SEVERE' | 'UNKNOWN';
    kind: EvidenceKind;
    normal_route_eligible: boolean;
    delay_penalty_min: number;
    delay_kind: EvidenceKind;
    reported_delay_min?: number | null;
    provider?: string | null;
    observed_at?: string | null;
    reason: string;
    warnings?: string[];
};

export type ShipmentState = {
    simulated: true;
    shipment_id: string;
    as_of: string;
    deadline_at: string;
    route_mode: 'river' | 'road';
    planned_remaining_min: number;
    handling_min: number;
    protection_remaining_min: number;
    prior_exposure_degree_min?: number;
    stock_available: number;
    stock_required?: number;
    expedite_available?: boolean;
    reroute_available?: boolean;
};

export type OperationalImpact = {
    predicted_delay_min: number;
    delay_risk: number;
    cold_chain_exposure_proxy_risk: number;
};

export type FrontendAction = {
    action: LogisticsAction;
    eligible: boolean;
    production_continuity_probability: number;
    on_time_arrival_probability: number;
    cold_chain_exposure_proxy_risk: number;
    predicted_delay_min: number;
    predicted_arrival_delay_min: number;
    assessment: string;
    reason: string;
};

export type Recommendation = {
    action: LogisticsAction | null;
    confidence: 'HIGH' | 'MEDIUM' | 'LOW';
    reason: string;
    why_not: Partial<Record<LogisticsAction, string>>;
    would_change_if: string[];
    policy_detail: string;
};

export type ProvenanceSummary = {
    kind: EvidenceKind;
    provider?: string | null;
    observed_at?: string | null;
    source_indices?: number[];
    detail: string;
};

export type LogisticsFrontendResult = {
    as_of: string;
    shipment_id: string;
    external_state: {
        rhine: RhineFeatures | null;
        traffic: TrafficFeature[];
        weather: WeatherFeatures | null;
        navigation: NavigationAssessment;
        warnings: string[];
    };
    simulated_shipment: ShipmentState;
    operational_impact: OperationalImpact;
    actions: FrontendAction[];
    recommendation: Recommendation;
    data_provenance: Record<string, ProvenanceSummary>;
    limitations: string[];
};
