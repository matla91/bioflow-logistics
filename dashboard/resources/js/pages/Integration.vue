<script setup lang="ts">
import { Head, Link, usePage } from '@inertiajs/vue3';
import { computed, ref } from 'vue';
import IntegrationDecisionPanel from '@/components/console/IntegrationDecisionPanel.vue';
import { decisionForAssessment } from '@/lib/integration-decisions';
import {
    formatBaselTime,
    formatBaselTimeShort,
    formatMinutes,
    formatProbability,
} from '@/lib/batch-display';
import {
    humanizeAlternativeReason,
    humanizeCounterfactual,
    humanizeRecommendationReason,
    recommendationSummary,
    scenarioStatus,
    selectedActionResult,
} from '@/lib/logistics-display';
import type {
    OperationalDataset,
    StoredLogisticsAssessment,
} from '@/types/integration';
import type {
    IntegrationActionRoles,
    IntegrationDecisions,
    IntegrationDemoShipments,
} from '@/types/integration-decisions';

const props = defineProps<{
    assessments: StoredLogisticsAssessment[];
    operations: OperationalDataset[];
    decisions: IntegrationDecisions;
    actionRoles: IntegrationActionRoles;
    demoShipments: IntegrationDemoShipments;
    unavailable: boolean;
}>();

const page = usePage();

defineOptions({
    layout: {
        breadcrumbs: [{ title: 'Logistics scenarios', href: '/integration' }],
    },
});

const scenarioOrder: StoredLogisticsAssessment['scenario'][] = [
    'normal',
    'disruption',
    'severe',
];
const scenarioRecords = computed(() =>
    scenarioOrder.flatMap((scenario) =>
        props.assessments.filter((record) => record.scenario === scenario),
    ),
);
const selectedAssessmentId = ref<string | null>(null);
const assessment = computed(
    () =>
        props.assessments.find(
            (record) => record.assessment_id === selectedAssessmentId.value,
        ) ??
        props.assessments.find((record) => record.scenario === 'normal') ??
        props.assessments[0] ??
        null,
);
const logistics = computed(() => assessment.value?.result ?? null);
const selectedAction = computed(() =>
    logistics.value ? selectedActionResult(logistics.value) : null,
);
const activeScenario = computed(() =>
    scenarioStatus(assessment.value?.scenario ?? ''),
);
const summary = computed(() =>
    logistics.value ? recommendationSummary(logistics.value) : '',
);
const warnings = computed(() => [
    ...(logistics.value?.external_state.warnings ?? []),
    ...(logistics.value?.external_state.navigation.warnings ?? []),
]);
const provenanceRows = computed(() =>
    Object.entries(logistics.value?.data_provenance ?? {}).map(
        ([key, evidence]) => ({ key, ...evidence }),
    ),
);
const whyNotRows = computed(() =>
    Object.entries(logistics.value?.recommendation.why_not ?? {}).map(
        ([action, explanation]) => ({ action, explanation }),
    ),
);
const operationalKpis = computed(() => [
    {
        label: 'Production continuity',
        value: selectedAction.value
            ? formatProbability(
                  selectedAction.value.production_continuity_probability,
              )
            : 'Unavailable',
        detail: 'Factory deadline met',
    },
    {
        label: 'On-time arrival',
        value: selectedAction.value
            ? formatProbability(
                  selectedAction.value.on_time_arrival_probability,
              )
            : 'Unavailable',
        detail: 'Incoming shipment deadline met',
    },
    {
        label: 'Expected incoming delay',
        value: selectedAction.value
            ? formatMinutes(selectedAction.value.predicted_arrival_delay_min)
            : 'Unavailable',
        detail: 'Mean over simulated journeys',
    },
]);
const formatNumber = (value: number | null | undefined, digits = 1) =>
    value == null || !Number.isFinite(value)
        ? '—'
        : value.toFixed(digits).replace(/\.0$/, '');
const signalCards = computed(() => {
    if (!logistics.value) return [];
    const { external_state: state, data_provenance: provenance } =
        logistics.value;
    const traffic = state.traffic[0];
    return [
        {
            label: 'Basel traffic',
            kind: provenance.traffic_current?.kind,
            value: traffic
                ? `${traffic.observed_count} vehicles`
                : 'Unavailable',
            detail: traffic
                ? `Station ${traffic.station_id} · z-score ${formatNumber(traffic.z_score, 2)} · ${provenance.traffic_anomaly?.kind ?? 'Unlinked evidence'}`
                : 'No usable current observation',
            note: traffic
                ? `${traffic.baseline_sample_count} baseline samples · ${traffic.status.replaceAll('_', ' ')}`
                : '',
        },
        {
            label: 'Rhine',
            kind: provenance.rhine_current?.kind,
            value: state.rhine
                ? `${formatNumber(state.rhine.discharge_m3_s)} m³/s`
                : 'Unavailable',
            detail: state.rhine
                ? `Level ${formatNumber(state.rhine.level_masl, 3)} m ASL`
                : 'No usable current observation',
            note: state.rhine
                ? `Level trend ${formatNumber(state.rhine.level_trend_cm_per_hour, 2)} cm/h · ${provenance.rhine_trends?.kind ?? 'Unlinked evidence'}`
                : '',
        },
        {
            label: 'Weather',
            kind: provenance.weather_current?.kind,
            value: state.weather
                ? `${formatNumber(state.weather.air_temperature_c)} °C`
                : 'Unavailable',
            detail: state.weather
                ? `Rain ${formatNumber(state.weather.precipitation_mm)} mm · wind ${formatNumber(state.weather.wind_speed_m_s)} m/s`
                : 'No usable current observation',
            note: state.weather
                ? `Temperature trend ${formatNumber(state.weather.temperature_trend_c_per_hour, 2)} °C/h · ${provenance.weather_trend?.kind ?? 'Unlinked evidence'}`
                : '',
        },
        {
            label: 'Navigation state',
            kind: state.navigation.kind,
            value: state.navigation.state,
            detail: `+${formatMinutes(state.navigation.delay_penalty_min)} delay · ${state.navigation.delay_kind}`,
            note: state.navigation.normal_route_eligible
                ? 'Normal route eligible'
                : 'Normal route unavailable',
        },
    ];
});
</script>

<template>
    <Head title="Logistics scenarios" />
    <div class="logistics-dashboard">
        <header class="logistics-header">
            <div>
                <p class="logistics-eyebrow">SMARTFLOW · RHINE TO REACTOR</p>
                <h1>Logistics scenarios</h1>
                <p class="logistics-subtitle">
                    Compare operational actions under changing Rhine-region
                    conditions
                </p>
            </div>
            <nav aria-label="Assessment mode" class="logistics-mode">
                <Link href="/integration" aria-current="page"
                    >Logistics scenarios</Link
                >
                <Link href="/integration/batches">Batch assessment</Link>
            </nav>
        </header>
        <p class="logistics-pipeline">
            Observed Basel signals → Monte Carlo simulation → deterministic
            decision policy → operator recommendation
        </p>

        <p
            v-if="(unavailable || !assessment) && page.props.errors.decision"
            role="alert"
            class="text-sm text-destructive"
        >
            {{ page.props.errors.decision }}
        </p>

        <section v-if="unavailable" class="logistics-empty" role="status">
            <h2>Stored analysis unavailable</h2>
            <p>The analysis service could not be reached. Try again shortly.</p>
            <Link href="/integration">Retry</Link>
        </section>
        <section v-else-if="!assessment" class="logistics-empty" role="status">
            <h2>No stored logistics assessments yet</h2>
            <p>Try again after the assessment worker has run.</p>
        </section>

        <template v-else-if="logistics">
            <nav aria-label="Logistics scenario" class="logistics-selector">
                <span class="logistics-muted">Stored scenario</span>
                <button
                    v-for="record in scenarioRecords"
                    :key="record.assessment_id"
                    type="button"
                    :aria-pressed="
                        assessment.assessment_id === record.assessment_id
                    "
                    @click="selectedAssessmentId = record.assessment_id"
                >
                    {{ scenarioStatus(record.scenario).label }}
                </button>
                <span
                    class="logistics-snapshot"
                    :title="formatBaselTime(logistics.as_of)"
                >
                    {{ formatBaselTimeShort(logistics.as_of) }} · Basel
                </span>
            </nav>

            <section
                aria-label="Recommended action outcomes"
                class="logistics-outcomes"
            >
                <article
                    class="logistics-recommendation"
                    :data-action="logistics.recommendation.action"
                    aria-live="polite"
                    aria-atomic="true"
                >
                    <div class="logistics-card-heading">
                        <h2>Recommended action</h2>
                        <span
                            class="logistics-scenario-state"
                            :data-tone="activeScenario.tone"
                        >
                            {{ activeScenario.label }}
                        </span>
                    </div>
                    <strong class="logistics-action">{{
                        logistics.recommendation.action ?? 'Reassess'
                    }}</strong>
                    <p class="logistics-summary">{{ summary }}</p>
                    <IntegrationDecisionPanel
                        :key="assessment.assessment_id"
                        :assessment="assessment"
                        :decision="decisionForAssessment(assessment, decisions)"
                        :action-roles="actionRoles"
                        :demo-shipments="demoShipments"
                    />
                </article>
                <article
                    v-for="kpi in operationalKpis"
                    :key="kpi.label"
                    class="logistics-kpi"
                >
                    <h2>{{ kpi.label }}</h2>
                    <strong>{{ kpi.value }}</strong>
                    <p>{{ kpi.detail }}</p>
                    <span class="logistics-kind" data-kind="MODEL">MODEL</span>
                </article>
            </section>

            <section aria-label="Basel signals" class="logistics-signals">
                <article
                    v-for="signal in signalCards"
                    :key="signal.label"
                    class="logistics-card"
                >
                    <div class="logistics-card-heading">
                        <h2>{{ signal.label }}</h2>
                        <b
                            v-if="signal.kind"
                            class="logistics-kind"
                            :data-kind="signal.kind"
                            >{{ signal.kind }}</b
                        >
                        <span v-else class="logistics-muted"
                            >Unlinked evidence</span
                        >
                    </div>
                    <strong class="logistics-signal-value">{{
                        signal.value
                    }}</strong>
                    <p class="logistics-muted">{{ signal.detail }}</p>
                    <p v-if="signal.note" class="logistics-signal-note">
                        {{ signal.note }}
                    </p>
                </article>
            </section>

            <section
                class="logistics-comparison"
                aria-label="Compare operational actions"
            >
                <div class="logistics-card-heading">
                    <h2>Compare operational actions</h2>
                    <span class="logistics-muted"
                        >Monte Carlo frequencies · under scenario
                        assumptions</span
                    >
                </div>
                <div class="logistics-action-grid">
                    <article
                        v-for="option in logistics.actions"
                        :key="option.action"
                        class="logistics-card"
                        :data-recommended="
                            option.action === logistics.recommendation.action
                        "
                        :data-eligible="option.eligible"
                    >
                        <div class="logistics-card-heading">
                            <h3>{{ option.action }}</h3>
                            <span class="logistics-action-badge">
                                {{
                                    option.action ===
                                    logistics.recommendation.action
                                        ? 'RECOMMENDED'
                                        : option.eligible
                                          ? 'ELIGIBLE'
                                          : 'INELIGIBLE'
                                }}
                            </span>
                        </div>
                        <dl class="logistics-metrics">
                            <div>
                                <dt>Production continuity</dt>
                                <dd>
                                    {{
                                        formatProbability(
                                            option.production_continuity_probability,
                                        )
                                    }}
                                </dd>
                            </div>
                            <div>
                                <dt>On-time arrival</dt>
                                <dd>
                                    {{
                                        formatProbability(
                                            option.on_time_arrival_probability,
                                        )
                                    }}
                                </dd>
                            </div>
                            <div>
                                <dt>Ambient exposure proxy</dt>
                                <dd>
                                    {{
                                        formatProbability(
                                            option.cold_chain_exposure_proxy_risk,
                                        )
                                    }}
                                </dd>
                            </div>
                            <div>
                                <dt>Expected incoming delay</dt>
                                <dd>
                                    {{
                                        formatMinutes(
                                            option.predicted_arrival_delay_min,
                                        )
                                    }}
                                </dd>
                            </div>
                            <div>
                                <dt>Expected factory delay</dt>
                                <dd>
                                    {{
                                        formatMinutes(
                                            option.predicted_delay_min,
                                        )
                                    }}
                                </dd>
                            </div>
                        </dl>
                        <p class="logistics-card-note">
                            {{ option.assessment }}
                        </p>
                    </article>
                </div>
                <p class="logistics-card-note">
                    Ambient exposure is a proxy. It does not establish
                    product-temperature excursion, pharmaceutical quality or QA
                    release status.
                </p>
            </section>

            <details class="logistics-audit">
                <summary>Why this recommendation &amp; alternatives</summary>
                <div class="logistics-audit-content">
                    <section>
                        <h2>Why this recommendation</h2>
                        <p>
                            {{
                                humanizeRecommendationReason(
                                    logistics.recommendation.reason,
                                )
                            }}
                        </p>
                        <p class="logistics-card-note">
                            Evidence confidence:
                            {{ logistics.recommendation.confidence }} ·
                            category, not a probability.
                        </p>
                        <h3>Why not the alternatives?</h3>
                        <ul>
                            <li v-for="row in whyNotRows" :key="row.action">
                                <b>{{ row.action }}</b
                                >:
                                {{ humanizeAlternativeReason(row.explanation) }}
                            </li>
                        </ul>
                        <p v-if="!whyNotRows.length">
                            No alternative reasons supplied.
                        </p>
                    </section>
                    <section>
                        <h2>Would change if</h2>
                        <p class="logistics-card-note">
                            Tested scenario changes; examples, not universal
                            thresholds.
                        </p>
                        <ul>
                            <li
                                v-for="condition in logistics.recommendation
                                    .would_change_if"
                                :key="condition"
                            >
                                {{ humanizeCounterfactual(condition) }}
                            </li>
                        </ul>
                        <p
                            v-if="
                                !logistics.recommendation.would_change_if.length
                            "
                        >
                            No evaluated change altered the recommendation.
                        </p>
                    </section>
                </div>
            </details>

            <details class="logistics-audit">
                <summary>
                    Evidence, provenance &amp; model limits ({{
                        provenanceRows.length
                    }}
                    evidence entries)
                </summary>
                <div class="logistics-audit-content">
                    <section>
                        <h2>Stored assessment identity</h2>
                        <dl class="logistics-metrics logistics-identifiers">
                            <div>
                                <dt>Assessment ID</dt>
                                <dd>{{ assessment.assessment_id }}</dd>
                            </div>
                            <div>
                                <dt>Shipment ID</dt>
                                <dd>{{ logistics.shipment_id }}</dd>
                            </div>
                            <div>
                                <dt>As of</dt>
                                <dd>{{ formatBaselTime(logistics.as_of) }}</dd>
                            </div>
                            <div>
                                <dt>Input digest</dt>
                                <dd>{{ assessment.input_sha256 }}</dd>
                            </div>
                            <div>
                                <dt>Model version</dt>
                                <dd>{{ assessment.model_version }}</dd>
                            </div>
                        </dl>
                    </section>
                    <section>
                        <h2>Warnings</h2>
                        <ul>
                            <li
                                v-for="(warning, index) in warnings"
                                :key="index"
                            >
                                {{ warning }}
                            </li>
                        </ul>
                        <p v-if="!warnings.length">No warnings supplied.</p>
                        <h3>Navigation evidence</h3>
                        <p>{{ logistics.external_state.navigation.reason }}</p>
                        <p class="logistics-card-note">
                            {{
                                logistics.external_state.navigation.provider ??
                                'No provider supplied'
                            }}
                            · observed
                            {{
                                formatBaselTime(
                                    logistics.external_state.navigation
                                        .observed_at ?? null,
                                )
                            }}. Reported delay:
                            {{
                                formatMinutes(
                                    logistics.external_state.navigation
                                        .reported_delay_min ?? null,
                                )
                            }}.
                        </p>
                    </section>
                    <section v-for="row in provenanceRows" :key="row.key">
                        <h2>
                            {{ row.key.replaceAll('_', ' ') }}
                            <b class="logistics-kind" :data-kind="row.kind">{{
                                row.kind
                            }}</b>
                        </h2>
                        <p>{{ row.detail }}</p>
                        <p v-if="row.provider" class="logistics-card-note">
                            {{ row.provider }}
                        </p>
                        <p v-if="row.observed_at" class="logistics-card-note">
                            Observed {{ formatBaselTime(row.observed_at) }}
                        </p>
                        <p
                            v-if="row.source_indices?.length"
                            class="logistics-card-note"
                        >
                            Source indices: {{ row.source_indices.join(', ') }}
                        </p>
                    </section>
                    <section>
                        <h2>Model limitations</h2>
                        <ul>
                            <li
                                v-for="limit in logistics.limitations"
                                :key="limit"
                            >
                                {{ limit }}
                            </li>
                        </ul>
                    </section>
                </div>
            </details>

            <details class="logistics-audit">
                <summary>
                    Decision policy &amp; original model explanations
                </summary>
                <div class="logistics-audit-content">
                    <section>
                        <h2>Deterministic policy</h2>
                        <p>{{ logistics.recommendation.policy_detail }}</p>
                        <h3>Original recommendation reason</h3>
                        <p>{{ logistics.recommendation.reason }}</p>
                        <ul>
                            <li v-for="row in whyNotRows" :key="row.action">
                                <b>{{ row.action }}</b
                                >: {{ row.explanation }}
                            </li>
                            <li
                                v-for="condition in logistics.recommendation
                                    .would_change_if"
                                :key="condition"
                            >
                                {{ condition }}
                            </li>
                        </ul>
                    </section>
                    <section>
                        <h2>
                            Baseline incoming shipment · before intervention
                        </h2>
                        <dl class="logistics-metrics">
                            <div>
                                <dt>Mean delay</dt>
                                <dd>
                                    {{
                                        formatMinutes(
                                            logistics.operational_impact
                                                .predicted_delay_min,
                                        )
                                    }}
                                </dd>
                            </div>
                            <div>
                                <dt>Delay frequency</dt>
                                <dd>
                                    {{
                                        formatProbability(
                                            logistics.operational_impact
                                                .delay_risk,
                                        )
                                    }}
                                </dd>
                            </div>
                            <div>
                                <dt>Ambient exposure proxy</dt>
                                <dd>
                                    {{
                                        formatProbability(
                                            logistics.operational_impact
                                                .cold_chain_exposure_proxy_risk,
                                        )
                                    }}
                                </dd>
                            </div>
                        </dl>
                        <h3>Simulated shipment inputs</h3>
                        <dl class="logistics-metrics">
                            <div>
                                <dt>Shipment deadline</dt>
                                <dd>
                                    {{
                                        formatBaselTime(
                                            logistics.simulated_shipment
                                                .deadline_at,
                                        )
                                    }}
                                </dd>
                            </div>
                            <div>
                                <dt>Route mode</dt>
                                <dd>
                                    {{
                                        logistics.simulated_shipment.route_mode
                                    }}
                                </dd>
                            </div>
                            <div>
                                <dt>Planned remaining journey</dt>
                                <dd>
                                    {{
                                        formatMinutes(
                                            logistics.simulated_shipment
                                                .planned_remaining_min,
                                        )
                                    }}
                                </dd>
                            </div>
                            <div>
                                <dt>Handling</dt>
                                <dd>
                                    {{
                                        formatMinutes(
                                            logistics.simulated_shipment
                                                .handling_min,
                                        )
                                    }}
                                </dd>
                            </div>
                            <div>
                                <dt>Packaging protection remaining</dt>
                                <dd>
                                    {{
                                        formatMinutes(
                                            logistics.simulated_shipment
                                                .protection_remaining_min,
                                        )
                                    }}
                                </dd>
                            </div>
                            <div>
                                <dt>Factory stock available</dt>
                                <dd>
                                    {{
                                        logistics.simulated_shipment
                                            .stock_available
                                    }}
                                </dd>
                            </div>
                        </dl>
                    </section>
                    <section
                        v-for="option in logistics.actions"
                        :key="option.action"
                    >
                        <h2>{{ option.action }} · original assessment</h2>
                        <p>{{ option.assessment }}</p>
                        <p>{{ option.reason }}</p>
                    </section>
                </div>
            </details>
            <details v-if="operations.length" class="logistics-audit">
                <summary>Separate simulated operations</summary>
                <div class="logistics-audit-content">
                    <section
                        v-for="dataset in operations"
                        :key="dataset.dataset_id"
                    >
                        <h2>
                            {{ dataset.dataset_id }}
                            <b class="logistics-kind" data-kind="SIMULATED"
                                >SIMULATED</b
                            >
                        </h2>
                        <p>
                            {{ dataset.batches.length }} batches ·
                            {{ dataset.shipments.length }} shipments ·
                            {{ dataset.inventory.length }} inventory lots.
                        </p>
                        <p class="logistics-card-note">
                            Reference time:
                            {{ formatBaselTime(dataset.reference_at) }}. These
                            records are separate from the scenario assessments
                            above.
                        </p>
                    </section>
                </div>
            </details>
        </template>
    </div>
</template>

<style scoped>
/* Keep the existing dark assessment cards and restrained navigation hierarchy. */
.logistics-dashboard {
    display: flex;
    flex: 1;
    min-width: 0;
    flex-direction: column;
    gap: 12px;
    padding: 16px 22px;
    background: var(--assessment-bg);
    color: var(--assessment-text);
    font-size: 14px;
}
.logistics-header,
.logistics-selector,
.logistics-mode,
.logistics-card-heading {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 10px;
}
.logistics-header,
.logistics-card-heading {
    justify-content: space-between;
}
.logistics-eyebrow {
    color: var(--assessment-accent);
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.12em;
}
h1 {
    margin-top: 3px;
    font-size: 27px;
    font-weight: 700;
    letter-spacing: -0.03em;
}
.logistics-subtitle,
.logistics-pipeline,
.logistics-muted,
.logistics-snapshot,
.logistics-signal-note {
    color: var(--assessment-muted);
    font-size: 12px;
}
.logistics-subtitle {
    margin-top: 4px;
    font-size: 13px;
}
.logistics-pipeline {
    font-size: 13px;
    line-height: 1.5;
}
.logistics-mode {
    gap: 3px;
    padding: 4px;
    border: 1px solid var(--assessment-border);
    border-radius: 9px;
    font-size: 13px;
}
.logistics-mode a,
.logistics-selector button {
    padding: 7px 12px;
    border-radius: 6px;
    color: var(--assessment-muted);
}
.logistics-selector button {
    border: 1px solid var(--assessment-border);
    font-weight: 600;
    cursor: pointer;
}
.logistics-mode [aria-current],
.logistics-selector [aria-pressed='true'] {
    background: var(--assessment-selected);
    color: var(--assessment-selected-text);
    box-shadow: inset 0 0 0 1px var(--assessment-accent);
}
a:hover,
button:hover {
    color: var(--assessment-selected-text);
}
a:focus-visible,
button:focus-visible,
summary:focus-visible {
    outline: 2px solid var(--assessment-focus);
    outline-offset: 4px;
}
.logistics-snapshot {
    margin-left: auto;
}
.logistics-outcomes {
    display: grid;
    grid-template-columns: minmax(0, 2.4fr) repeat(3, minmax(0, 1fr));
    gap: 12px;
}
.logistics-recommendation,
.logistics-card,
.logistics-kpi {
    min-width: 0;
    padding: 14px;
    border: 1px solid var(--assessment-border);
    border-radius: 11px;
    background: var(--assessment-surface);
}
.logistics-recommendation {
    border: 1px solid var(--assessment-accent);
    border-left-width: 4px;
    background: var(--assessment-raised);
}
.logistics-recommendation[data-action='BUFFER'] {
    border-left-color: var(--assessment-positive);
}
.logistics-recommendation[data-action='EXPEDITE'] {
    border-left-color: var(--assessment-warning);
}
.logistics-card-heading h2,
.logistics-kpi h2 {
    font-size: 13px;
    font-weight: 650;
}
.logistics-scenario-state {
    font-size: 11px;
    color: var(--assessment-muted);
}
.logistics-scenario-state[data-tone='warning'] {
    color: var(--assessment-warning);
}
.logistics-scenario-state[data-tone='alert'] {
    color: var(--assessment-alert);
}
.logistics-action {
    display: block;
    margin-top: 7px;
    font-size: 43px;
    font-weight: 700;
    letter-spacing: -0.035em;
    line-height: 1.1;
}
.logistics-summary {
    margin-top: 8px;
    line-height: 1.5;
}
.logistics-kpi {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 9px;
}
.logistics-kpi strong {
    font-size: 31px;
    line-height: 1.1;
    font-weight: 700;
    letter-spacing: -0.035em;
    font-variant-numeric: tabular-nums;
    overflow-wrap: anywhere;
}
.logistics-kpi p {
    font-size: 12px;
    color: var(--assessment-muted);
}
.logistics-kpi .logistics-kind {
    margin-top: auto;
}
.logistics-signals {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 12px;
}
.logistics-signal-value {
    display: block;
    margin: 9px 0 5px;
    font-size: 22px;
    font-weight: 700;
    line-height: 1.2;
    font-variant-numeric: tabular-nums;
}
.logistics-signal-note {
    margin-top: 4px;
    font-size: 11px;
}
.logistics-kind {
    display: inline-block;
    padding: 2px 5px;
    border: 1px solid var(--assessment-border);
    border-radius: 3px;
    font-size: 10px;
    font-weight: 650;
    letter-spacing: 0.04em;
    color: var(--assessment-accent);
}
.logistics-kind[data-kind='REAL'] {
    color: var(--assessment-positive);
}
.logistics-kind[data-kind='SIMULATED'] {
    color: var(--assessment-violet);
}
.logistics-kind[data-kind='ASSUMED'] {
    color: var(--assessment-warning);
}
.logistics-comparison {
    padding: 14px;
    border: 1px solid var(--assessment-border);
    border-radius: 11px;
    background: var(--assessment-surface);
}
.logistics-comparison > .logistics-card-heading h2 {
    font-size: 17px;
}
.logistics-action-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 12px;
    margin-top: 12px;
}
.logistics-action-grid [data-recommended='true'] {
    background: var(--assessment-raised);
    border-color: var(--assessment-accent);
}
.logistics-action-grid [data-eligible='false'] {
    border-style: dashed;
}
.logistics-action-grid h3 {
    font-size: 20px;
    font-weight: 700;
}
.logistics-action-badge {
    font-size: 10px;
    font-weight: 700;
    color: var(--assessment-muted);
}
[data-recommended='true'] .logistics-action-badge {
    color: var(--assessment-accent);
}
.logistics-metrics {
    display: flex;
    flex-direction: column;
    gap: 7px;
    margin-top: 11px;
}
.logistics-metrics > div {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 10px;
}
dt {
    font-size: 12px;
    color: var(--assessment-muted);
}
dd {
    font-size: 13px;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
    text-align: right;
}
.logistics-card-note {
    margin-top: 10px;
    color: var(--assessment-muted);
    font-size: 12px;
    line-height: 1.5;
}
.logistics-audit {
    border: 1px solid var(--assessment-border);
    border-radius: 8px;
    color: var(--assessment-muted);
}
.logistics-audit > summary {
    padding: 11px 15px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
}
.logistics-audit-content {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 22px;
    padding: 8px 16px 20px;
    font-size: 13px;
}
.logistics-audit h2,
.logistics-audit h3 {
    color: var(--assessment-text);
    font-weight: 650;
    margin-bottom: 8px;
}
.logistics-audit h3 {
    margin-top: 16px;
}
.logistics-audit p,
.logistics-audit li,
.logistics-identifiers dd {
    overflow-wrap: anywhere;
    line-height: 1.6;
}
.logistics-identifiers dd {
    max-width: 70%;
}
.logistics-audit ul {
    list-style: disc;
    padding-left: 17px;
    margin-top: 10px;
}
.logistics-audit li + li {
    margin-top: 7px;
}
.logistics-empty {
    padding: 28px;
    border: 1px solid var(--assessment-border);
    border-radius: 11px;
    background: var(--assessment-surface);
}
.logistics-empty h2 {
    font-size: 20px;
    font-weight: 700;
}
.logistics-empty p,
.logistics-empty a {
    margin-top: 10px;
    display: block;
}
@media (max-width: 1100px) {
    .logistics-outcomes {
        grid-template-columns: repeat(3, minmax(0, 1fr));
    }
    .logistics-recommendation {
        grid-column: 1 / -1;
    }
    .logistics-signals {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }
}
@media (max-width: 700px) {
    .logistics-dashboard {
        padding: 14px;
    }
    .logistics-outcomes,
    .logistics-signals,
    .logistics-action-grid,
    .logistics-audit-content {
        grid-template-columns: minmax(0, 1fr);
    }
    .logistics-snapshot {
        margin-left: 0;
        width: 100%;
    }
}
</style>
