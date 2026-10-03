<script setup lang="ts">
import { Head, Link } from '@inertiajs/vue3';
import { computed } from 'vue';
import {
    actionLabel,
    assessmentSummary,
    batchLabel,
    formatBaselTime,
    formatBaselTimeShort,
    formatKg,
    formatMinutes,
    formatProbability,
    incomingStatusLabel,
    productionStatusLabel,
    qaReleaseLabel,
    shipmentLabel,
    temperaturePresentation,
} from '@/lib/batch-display';
import type { StoredBatchAssessment } from '@/types/integration';

const props = defineProps<{
    assessment: StoredBatchAssessment | null;
    batches: { id: string; label: string }[];
    selectedBatchId: string | null;
    unavailable: boolean;
    missing: boolean;
}>();

defineOptions({
    layout: {
        breadcrumbs: [
            { title: 'Batch assessment', href: '/integration/batches' },
        ],
    },
});

const summary = computed(() =>
    props.assessment ? assessmentSummary(props.assessment) : null,
);
const readiness = computed(() => props.assessment?.production_readiness);
const temperatures = computed(() =>
    (props.assessment?.product_temperature ?? []).map((evidence) => ({
        evidence,
        display: temperaturePresentation(
            evidence,
            props.assessment?.recommendation.qa_review_required,
        ),
    })),
);
const approvalRoles = {
    operator: 'Operator',
    logistics: 'Logistics',
    QA: 'QA',
};
</script>

<template>
    <Head title="Batch assessment" />
    <div class="batch-dashboard">
        <header class="batch-header">
            <div>
                <p class="batch-eyebrow">SMARTFLOW · RHINE TO REACTOR</p>
                <h1>Batch assessment</h1>
                <p class="batch-subtitle">
                    Stored operational evidence for a manufacturing batch
                </p>
            </div>
            <nav aria-label="Assessment mode" class="batch-mode">
                <Link href="/integration">Logistics scenarios</Link>
                <Link href="/integration/batches" aria-current="page">
                    Batch assessment
                </Link>
            </nav>
        </header>

        <nav aria-label="Batch selector" class="batch-selector">
            <span class="batch-muted">Stored batch</span>
            <Link
                v-for="batch in batches"
                :key="batch.id"
                :href="`/integration/batches?batch_id=${encodeURIComponent(batch.id)}`"
                :aria-current="
                    selectedBatchId === batch.id ? 'page' : undefined
                "
                preserve-scroll
            >
                {{ batch.label }}
            </Link>
            <span class="batch-selector-note"
                >Stored evidence · cutoff shown below</span
            >
        </nav>

        <section v-if="unavailable" class="batch-empty" role="status">
            <h2>Stored assessment unavailable</h2>
            <p>The analysis service could not be reached. Try again shortly.</p>
            <Link href="/integration/batches">Retry</Link>
        </section>
        <section v-else-if="!assessment" class="batch-empty" role="status">
            <h2>
                {{
                    missing
                        ? 'No stored assessment for this batch'
                        : 'No stored batch assessments yet'
                }}
            </h2>
            <p>
                Select an available batch or try again after the assessment
                worker has run.
            </p>
        </section>

        <template v-else-if="summary && readiness">
            <section
                aria-label="Operator assessment summary"
                class="batch-summary"
                :data-tone="summary.tone"
            >
                <div class="batch-summary-main">
                    <p class="batch-eyebrow">
                        {{ batchLabel(assessment.batch_id) }}
                    </p>
                    <h2>{{ summary.headline }}</h2>
                    <p class="batch-summary-detail">{{ summary.detail }}</p>
                    <p v-if="summary.limitation" class="batch-summary-limit">
                        {{ summary.limitation }}
                    </p>
                </div>
                <dl class="batch-summary-facts">
                    <div>
                        <dt>
                            {{
                                summary.retrospective
                                    ? 'Stored recommendation'
                                    : 'Recommended action'
                            }}
                        </dt>
                        <dd>
                            {{ actionLabel(assessment.recommendation.action) }}
                        </dd>
                    </div>
                    <div>
                        <dt>Human review</dt>
                        <dd>
                            {{
                                approvalRoles[
                                    assessment.recommendation
                                        .requires_approval_by
                                ]
                            }}
                            {{
                                assessment.recommendation.action
                                    ? 'approval required'
                                    : 'review required'
                            }}
                            <span
                                v-if="
                                    assessment.recommendation.qa_review_required
                                "
                            >
                                · QA review required</span
                            >
                        </dd>
                    </div>
                    <div>
                        <dt>Assessment cutoff</dt>
                        <dd>
                            <time
                                :datetime="assessment.as_of"
                                :title="formatBaselTime(assessment.as_of)"
                                >{{
                                    formatBaselTimeShort(assessment.as_of)
                                }}</time
                            >
                        </dd>
                    </div>
                    <div>
                        <dt>Planned charge</dt>
                        <dd>
                            <time
                                :datetime="readiness.planned_charge_at"
                                :title="
                                    formatBaselTime(readiness.planned_charge_at)
                                "
                                >{{
                                    formatBaselTimeShort(
                                        readiness.planned_charge_at,
                                    )
                                }}</time
                            >
                        </dd>
                    </div>
                </dl>
            </section>

            <div class="batch-evidence-grid">
                <section
                    class="batch-card"
                    aria-labelledby="production-heading"
                >
                    <div class="batch-card-heading">
                        <span class="batch-card-number">01</span>
                        <h2 id="production-heading">Production readiness</h2>
                    </div>
                    <p
                        class="batch-status"
                        :data-tone="
                            readiness.reservation_shortfall_kg > 0
                                ? 'warning'
                                : 'neutral'
                        "
                    >
                        {{ productionStatusLabel(readiness.status) }}
                    </p>
                    <div class="batch-primary-metric">
                        <strong>{{
                            formatKg(readiness.released_reserved_quantity_kg)
                        }}</strong>
                        <span
                            >released reserved ·
                            {{ formatKg(readiness.required_quantity_kg) }}
                            required</span
                        >
                    </div>
                    <dl class="batch-metrics">
                        <div
                            :class="{
                                'batch-shortage':
                                    readiness.reservation_shortfall_kg > 0,
                            }"
                        >
                            <dt>Reservation shortfall</dt>
                            <dd>
                                {{
                                    formatKg(readiness.reservation_shortfall_kg)
                                }}
                            </dd>
                        </div>
                        <div>
                            <dt>Incoming dependency</dt>
                            <dd>
                                {{ formatKg(readiness.incoming_dependency_kg) }}
                            </dd>
                        </div>
                        <div
                            :class="{
                                'batch-shortage':
                                    readiness.uncovered_quantity_kg > 0,
                            }"
                        >
                            <dt>Uncovered quantity</dt>
                            <dd>
                                {{ formatKg(readiness.uncovered_quantity_kg) }}
                            </dd>
                        </div>
                    </dl>
                    <p class="batch-card-note">
                        {{
                            summary.retrospective
                                ? 'Snapshot coverage does not prove historical QA or reservation state at charge time.'
                                : 'Incoming plans still require arrival and human QA release; they are not released stock.'
                        }}
                    </p>
                </section>

                <section class="batch-card" aria-labelledby="incoming-heading">
                    <div class="batch-card-heading">
                        <span class="batch-card-number">02</span>
                        <h2 id="incoming-heading">Incoming shipment</h2>
                    </div>
                    <p
                        v-if="assessment.incoming_shipments.length === 0"
                        class="batch-card-note"
                    >
                        No incoming shipment evidence supplied.
                    </p>
                    <article
                        v-for="shipment in assessment.incoming_shipments"
                        :key="shipment.shipment_id"
                        class="batch-shipment"
                    >
                        <div class="batch-status-row">
                            <span
                                class="batch-status"
                                :data-tone="
                                    shipment.status === 'UNAVAILABLE'
                                        ? 'warning'
                                        : 'neutral'
                                "
                            >
                                {{ incomingStatusLabel(shipment.status) }}
                            </span>
                            <span class="batch-muted">{{
                                shipmentLabel(shipment.shipment_id)
                            }}</span>
                        </div>
                        <dl class="batch-metrics">
                            <div>
                                <dt>Planned quantity</dt>
                                <dd>
                                    {{ formatKg(shipment.planned_quantity_kg) }}
                                </dd>
                            </div>
                            <div>
                                <dt>Batch dependency</dt>
                                <dd>
                                    {{
                                        formatKg(
                                            shipment.dependency_quantity_kg,
                                        )
                                    }}
                                </dd>
                            </div>
                            <div>
                                <dt>Planned arrival</dt>
                                <dd>
                                    {{
                                        formatBaselTimeShort(
                                            shipment.planned_arrival_at,
                                        )
                                    }}
                                </dd>
                            </div>
                            <div>
                                <dt>Actual arrival</dt>
                                <dd>
                                    {{
                                        formatBaselTimeShort(
                                            shipment.actual_arrival_at,
                                        )
                                    }}
                                </dd>
                            </div>
                        </dl>
                        <p
                            class="batch-arrival-flag"
                            :data-tone="
                                shipment.scheduled_after_charge
                                    ? 'warning'
                                    : 'neutral'
                            "
                        >
                            {{
                                shipment.scheduled_after_charge
                                    ? 'Scheduled after charge'
                                    : 'Not scheduled after charge'
                            }}
                        </p>
                        <details
                            v-if="
                                shipment.on_time_arrival_probability !== null ||
                                shipment.eta_p50 !== null ||
                                shipment.eta_p90 !== null ||
                                shipment.cold_chain_exposure_proxy_risk !== null
                            "
                            class="batch-inline-audit batch-model-metrics"
                            :open="shipment.status === 'MODELED'"
                        >
                            <summary>
                                {{
                                    shipment.status === 'ARRIVED'
                                        ? 'Recorded arrival metrics'
                                        : 'Modeled timing & ambient proxy'
                                }}
                            </summary>
                            <dl class="batch-metrics">
                                <div
                                    v-if="
                                        shipment.on_time_arrival_probability !==
                                        null
                                    "
                                >
                                    <dt>
                                        {{
                                            shipment.status === 'ARRIVED'
                                                ? 'Recorded on-time arrival'
                                                : 'On-time arrival probability'
                                        }}
                                    </dt>
                                    <dd>
                                        {{
                                            formatProbability(
                                                shipment.on_time_arrival_probability,
                                            )
                                        }}
                                    </dd>
                                </div>
                                <div v-if="shipment.eta_p50 !== null">
                                    <dt>
                                        {{
                                            shipment.status === 'ARRIVED'
                                                ? 'Observed arrival (p50)'
                                                : 'ETA p50'
                                        }}
                                    </dt>
                                    <dd>
                                        {{
                                            formatBaselTimeShort(
                                                shipment.eta_p50,
                                            )
                                        }}
                                    </dd>
                                </div>
                                <div v-if="shipment.eta_p90 !== null">
                                    <dt>
                                        {{
                                            shipment.status === 'ARRIVED'
                                                ? 'Observed arrival (p90)'
                                                : 'ETA p90'
                                        }}
                                    </dt>
                                    <dd>
                                        {{
                                            formatBaselTimeShort(
                                                shipment.eta_p90,
                                            )
                                        }}
                                    </dd>
                                </div>
                                <div
                                    v-if="
                                        shipment.cold_chain_exposure_proxy_risk !==
                                        null
                                    "
                                >
                                    <dt>Ambient exposure proxy</dt>
                                    <dd>
                                        {{
                                            formatProbability(
                                                shipment.cold_chain_exposure_proxy_risk,
                                            )
                                        }}
                                    </dd>
                                </div>
                            </dl>
                        </details>
                        <p
                            v-if="shipment.status === 'UNAVAILABLE'"
                            class="batch-unavailable"
                        >
                            Timing / ambient model unavailable
                        </p>
                        <details
                            class="batch-inline-audit"
                            :open="shipment.status === 'UNAVAILABLE'"
                        >
                            <summary>
                                {{
                                    shipment.status === 'UNAVAILABLE'
                                        ? 'Why unavailable'
                                        : 'Shipment evidence'
                                }}
                            </summary>
                            <p>{{ shipment.reason }}</p>
                        </details>
                    </article>
                </section>

                <section
                    class="batch-card"
                    aria-labelledby="temperature-heading"
                >
                    <div class="batch-card-heading">
                        <span class="batch-card-number">03</span>
                        <h2 id="temperature-heading">
                            Product temperature / QA
                        </h2>
                    </div>
                    <p
                        v-if="temperatures.length === 0"
                        class="batch-status"
                        data-tone="warning"
                    >
                        Product-temperature evidence unavailable
                    </p>
                    <article
                        v-for="{ evidence, display } in temperatures"
                        :key="evidence.shipment_id"
                        class="batch-temperature"
                    >
                        <p class="batch-status" :data-tone="display.tone">
                            {{ display.statusLabel }}
                        </p>
                        <div
                            class="batch-primary-metric"
                            :data-tone="display.tone"
                        >
                            <strong>{{ display.excursionLabel }}</strong>
                            <span>{{ display.budgetLabel }}</span>
                        </div>
                        <div class="batch-status-row">
                            <span
                                class="batch-journey"
                                :data-tone="
                                    evidence.complete_journey
                                        ? 'neutral'
                                        : 'warning'
                                "
                                >{{ display.journeyLabel }}</span
                            >
                            <span class="batch-muted"
                                >{{ evidence.reading_count }} readings</span
                            >
                        </div>
                        <dl class="batch-metrics">
                            <div
                                :class="{
                                    'batch-shortage':
                                        evidence.last_product_outside_range ===
                                        true,
                                }"
                            >
                                <dt>Last product temperature</dt>
                                <dd>
                                    {{ display.lastReadingLabel }}
                                </dd>
                            </div>
                        </dl>
                        <p v-if="display.limitation" class="batch-card-note">
                            {{ display.limitation }}
                        </p>
                    </article>
                    <p class="batch-qa-state">
                        {{
                            assessment.recommendation.qa_review_required
                                ? 'Human QA review required'
                                : 'QA release requires a separate human decision'
                        }}
                        <span>{{
                            qaReleaseLabel(
                                assessment.recommendation.qa_release_authorized,
                            )
                        }}</span>
                    </p>
                </section>
            </div>

            <div
                class="batch-provenance-strip"
                aria-label="Evidence provenance"
            >
                <span
                    ><b class="batch-kind" data-kind="SIMULATED">SIMULATED</b>
                    ERP / product samples</span
                >
                <span
                    v-if="assessment.provenance.some((p) => p.kind === 'REAL')"
                    ><b class="batch-kind" data-kind="REAL">REAL</b> External
                    observations</span
                >
                <span
                    ><b class="batch-kind" data-kind="MODEL">MODEL</b>
                    Assessment outputs</span
                >
                <span
                    ><b class="batch-kind" data-kind="ASSUMED">ASSUMED</b> Demo
                    limits / interpolation</span
                >
            </div>

            <details class="batch-audit">
                <summary>Assessment evidence &amp; audit details</summary>
                <div class="batch-audit-content">
                    <section>
                        <h2>Stored recommendation &amp; identity</h2>
                        <p>{{ assessment.recommendation.reason }}</p>
                        <dl class="batch-metrics batch-identifiers">
                            <div>
                                <dt>Batch ID</dt>
                                <dd>{{ assessment.batch_id }}</dd>
                            </div>
                            <div>
                                <dt>Assessment ID</dt>
                                <dd>{{ assessment.assessment_id }}</dd>
                            </div>
                            <div>
                                <dt>Input digest</dt>
                                <dd>{{ assessment.input_sha256 }}</dd>
                            </div>
                            <div>
                                <dt>Model version</dt>
                                <dd>{{ assessment.model_version }}</dd>
                            </div>
                            <div>
                                <dt>Knowledge cutoff</dt>
                                <dd>
                                    {{ formatBaselTime(assessment.known_at) }}
                                </dd>
                            </div>
                        </dl>
                    </section>
                    <section
                        v-for="{ evidence } in temperatures"
                        :key="evidence.shipment_id"
                    >
                        <h2>
                            {{ shipmentLabel(evidence.shipment_id) }} · sample
                            coverage
                        </h2>
                        <dl class="batch-metrics">
                            <div>
                                <dt>First sample</dt>
                                <dd>
                                    {{
                                        formatBaselTime(
                                            evidence.first_reading_at,
                                        )
                                    }}
                                </dd>
                            </div>
                            <div>
                                <dt>Last sample</dt>
                                <dd>
                                    {{
                                        formatBaselTime(
                                            evidence.last_reading_at,
                                        )
                                    }}
                                </dd>
                            </div>
                            <div>
                                <dt>Observed product excursion duration</dt>
                                <dd>
                                    {{
                                        formatMinutes(
                                            evidence.observed_excursion_min,
                                        )
                                    }}
                                </dd>
                            </div>
                            <div>
                                <dt>Unobserved bounded intervals</dt>
                                <dd>
                                    {{
                                        formatMinutes(
                                            evidence.unobserved_interval_min,
                                        )
                                    }}
                                </dd>
                            </div>
                            <div>
                                <dt>Source-reported cumulative excursion</dt>
                                <dd>
                                    {{
                                        formatMinutes(
                                            evidence.reported_excursion_min,
                                        )
                                    }}
                                </dd>
                            </div>
                        </dl>
                        <p class="batch-card-note">
                            Observed excursion covers time outside the material
                            range in usable sampled intervals. Bounded gaps
                            exclude unknown future journey time. Sample-window
                            timestamps do not establish continuous observation.
                        </p>
                        <ul>
                            <li
                                v-for="limit in evidence.limitations"
                                :key="limit"
                            >
                                {{ limit }}
                            </li>
                        </ul>
                    </section>
                    <section>
                        <h2>Stock evidence</h2>
                        <p
                            v-for="lot in readiness.stock_evidence"
                            :key="lot.inventory_lot_id"
                        >
                            {{ lot.inventory_lot_id }} · {{ lot.qa_status }} ·
                            {{ formatKg(lot.eligible_reserved_quantity_kg) }}
                            credited. {{ lot.reason }}
                        </p>
                    </section>
                    <section>
                        <h2>Provenance &amp; sources</h2>
                        <p
                            v-for="(item, index) in assessment.provenance"
                            :key="index"
                        >
                            <b class="batch-kind" :data-kind="item.kind">{{
                                item.kind
                            }}</b>
                            {{ item.detail }}
                        </p>
                        <p
                            v-for="source in assessment.real_data_sources"
                            :key="`${source.provider}-${source.dataset}`"
                        >
                            <a
                                :href="source.url"
                                target="_blank"
                                rel="noopener noreferrer"
                                >{{ source.provider }} · {{ source.dataset }}</a
                            >
                            · retrieved
                            {{ formatBaselTime(source.retrieved_at) }} ·
                            {{ source.licence }}
                        </p>
                    </section>
                    <section>
                        <h2>Assessment limitations</h2>
                        <ul>
                            <li
                                v-for="limit in assessment.limitations"
                                :key="limit"
                            >
                                {{ limit }}
                            </li>
                        </ul>
                    </section>
                </div>
            </details>
        </template>
    </div>
</template>

<style scoped>
/* Selectively reuse the reference dashboard's hierarchy, cards and restrained badges. */
.batch-dashboard {
    --batch-muted: var(--assessment-muted);
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
.batch-header,
.batch-status-row,
.batch-selector,
.batch-mode {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
}
.batch-header {
    justify-content: space-between;
}
.batch-eyebrow {
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
.batch-subtitle {
    color: var(--batch-muted);
    font-size: 14px;
    margin-top: 3px;
}
.batch-temperature .batch-shortage {
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
}
.batch-temperature .batch-shortage dd {
    text-align: left;
}
.batch-mode {
    gap: 3px;
    padding: 4px;
    border: 1px solid var(--assessment-border);
    border-radius: 9px;
    font-size: 13px;
}
.batch-mode a,
.batch-selector a {
    padding: 7px 12px;
    border-radius: 6px;
    color: #c6d2e2;
}
.batch-mode [aria-current],
.batch-selector [aria-current] {
    background: var(--assessment-selected);
    color: var(--assessment-selected-text);
    box-shadow: inset 0 0 0 1px #5baddb;
}
a:hover {
    color: #e7f7ff;
}
a:focus-visible,
summary:focus-visible {
    outline: 2px solid var(--assessment-focus);
    outline-offset: 4px;
}
.batch-selector a {
    border: 1px solid #344258;
    font-weight: 600;
}
.batch-selector-note {
    margin-left: auto;
    color: var(--batch-muted);
    font-size: 12px;
}
.batch-muted {
    color: var(--batch-muted);
    font-size: 12px;
}
.batch-summary {
    display: grid;
    grid-template-columns: 1.3fr 1fr;
    gap: 20px;
    padding: 14px 18px;
    border: 1px solid #476684;
    border-left: 4px solid #75c7f8;
    border-radius: 11px;
    background: var(--assessment-raised);
}
.batch-summary[data-tone='warning'] {
    border-left-color: var(--assessment-warning);
}
.batch-summary[data-tone='alert'] {
    border-left-color: var(--assessment-alert);
    background: var(--assessment-alert-bg);
}
.batch-summary h2 {
    font-size: 25px;
    font-weight: 700;
    line-height: 1.2;
    margin-top: 4px;
    letter-spacing: -0.025em;
}
.batch-summary-detail {
    margin-top: 7px;
    font-size: 14px;
}
.batch-summary-limit {
    color: #e7cfab;
    font-size: 12px;
    margin-top: 7px;
    line-height: 1.5;
}
.batch-summary-facts {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px 15px;
    align-content: center;
}
dt {
    color: var(--batch-muted);
    font-size: 12px;
}
.batch-summary-facts dd {
    font-size: 13px;
    font-weight: 600;
    margin-top: 3px;
}
.batch-evidence-grid {
    display: grid;
    grid-template-columns: 0.95fr 1.1fr 1.05fr;
    gap: 12px;
    align-items: stretch;
}
.batch-card {
    min-width: 0;
    padding: 14px;
    border: 1px solid var(--assessment-border);
    border-radius: 11px;
    background: #141f30;
}
.batch-card-heading {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 10px;
}
.batch-card-heading h2 {
    font-size: 14px;
    font-weight: 650;
}
.batch-card-number {
    color: #8fb4d9;
    font-size: 11px;
    font-weight: 700;
}
.batch-status {
    color: #c8d6e7;
    font-size: 13px;
    font-weight: 650;
}
[data-tone='warning'] {
    color: #ffd18b;
}
[data-tone='alert'] {
    color: #ffadb3;
}
.batch-primary-metric {
    margin: 12px 0;
    display: flex;
    flex-direction: column;
    gap: 4px;
}
.batch-primary-metric strong {
    font-size: 29px;
    line-height: 1.1;
    letter-spacing: -0.035em;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
}
.batch-primary-metric span {
    font-size: 12px;
    color: var(--batch-muted);
}
.batch-metrics {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-top: 10px;
}
.batch-metrics > div {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 10px;
}
.batch-metrics dd {
    text-align: right;
    font-size: 13px;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
}
.batch-shortage {
    color: #ffb67a;
    background: #a4511626;
    padding: 7px 8px;
    border-radius: 5px;
}
.batch-shortage dt {
    color: #f4c6a6;
}
.batch-card-note {
    color: var(--batch-muted);
    font-size: 12px;
    line-height: 1.5;
    margin-top: 12px;
}
.batch-arrival-flag {
    font-size: 12px;
    font-weight: 600;
    margin-top: 10px;
}
.batch-model-metrics {
    padding-top: 9px;
    border-top: 1px solid #344258;
}
.batch-unavailable {
    margin-top: 11px;
    color: #ffd18b;
    font-size: 12px;
    font-weight: 600;
}
.batch-inline-audit {
    font-size: 12px;
    color: var(--batch-muted);
    margin-top: 6px;
}
summary {
    cursor: pointer;
}
.batch-inline-audit p {
    line-height: 1.5;
    margin-top: 5px;
}
.batch-journey {
    font-size: 12px;
    font-weight: 650;
}
.batch-qa-state {
    margin-top: 11px;
    padding-top: 9px;
    border-top: 1px solid #344258;
    color: #ffd18b;
    font-size: 13px;
    font-weight: 650;
}
.batch-qa-state span {
    display: block;
    margin-top: 4px;
    color: #d4deed;
    font-size: 12px;
    font-weight: 500;
}
.batch-provenance-strip {
    display: flex;
    flex-wrap: wrap;
    gap: 7px 16px;
    color: var(--batch-muted);
    font-size: 11px;
}
.batch-kind {
    display: inline-block;
    margin-right: 4px;
    border-radius: 3px;
    padding: 2px 5px;
    color: #abd5ff;
    background: #1b3c5a;
    font-size: 10px;
    letter-spacing: 0.04em;
}
.batch-kind[data-kind='SIMULATED'] {
    color: #debbff;
    background: #3c2d58;
}
.batch-kind[data-kind='REAL'] {
    color: #9bdfc6;
    background: #173e37;
}
.batch-kind[data-kind='ASSUMED'] {
    color: #f4d69d;
    background: #463b27;
}
.batch-audit {
    border: 1px solid #344258;
    border-radius: 8px;
    color: var(--batch-muted);
}
.batch-audit > summary {
    padding: 11px 15px;
    font-size: 13px;
    font-weight: 600;
}
.batch-audit-content {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 22px;
    padding: 8px 16px 20px;
    font-size: 13px;
}
.batch-audit h2 {
    color: #e5edf8;
    font-weight: 650;
    margin-bottom: 8px;
}
.batch-audit p,
.batch-audit li {
    overflow-wrap: anywhere;
    line-height: 1.6;
    margin-top: 5px;
}
.batch-audit ul {
    list-style: disc;
    padding-left: 17px;
}
.batch-identifiers > div {
    display: block;
}
.batch-identifiers dd {
    text-align: left;
    overflow-wrap: anywhere;
    font-size: 12px;
}
.batch-empty {
    padding: 25px;
    border: 1px solid #42566f;
    border-radius: 10px;
}
.batch-empty h2 {
    font-size: 22px;
    font-weight: 650;
}
.batch-empty p {
    margin: 10px 0;
    color: var(--batch-muted);
}
.batch-empty a {
    color: var(--assessment-accent);
    text-decoration: underline;
}
.batch-shipment + .batch-shipment,
.batch-temperature + .batch-temperature {
    border-top: 1px solid #344258;
    margin-top: 16px;
    padding-top: 12px;
}
@media (max-width: 1100px) {
    .batch-dashboard {
        padding: 16px;
    }
    .batch-evidence-grid {
        grid-template-columns: 1fr;
    }
    .batch-summary {
        grid-template-columns: 1fr;
    }
    .batch-audit-content {
        grid-template-columns: 1fr;
    }
}
@media (max-width: 600px) {
    .batch-summary-facts {
        grid-template-columns: 1fr;
    }
    .batch-selector-note {
        display: none;
    }
    .batch-mode {
        font-size: 12px;
    }
}
</style>
