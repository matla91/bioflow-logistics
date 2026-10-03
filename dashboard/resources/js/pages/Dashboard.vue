<script setup lang="ts">
import { Head, Link } from '@inertiajs/vue3';
import { computed } from 'vue';
import {
    formatMinutes,
    formatPercent,
    humanizeAlternativeReason,
    humanizeCounterfactual,
    humanizeRecommendationReason,
    recommendationSummary,
} from '@/lib/logistics-display';
import type {
    EvidenceKind,
    FrontendAction,
    LogisticsFrontendResult,
} from '@/types/logistics';

type ScenarioKey = 'normal' | 'disruption' | 'severe';

const props = defineProps<{
    scenario: ScenarioKey;
    logistics: LogisticsFrontendResult;
}>();

defineOptions({
    layout: {
        breadcrumbs: [{ title: 'Decision dashboard', href: '/dashboard' }],
    },
});

const scenarios: { key: ScenarioKey; label: string }[] = [
    { key: 'normal', label: 'Normal' },
    { key: 'disruption', label: 'Disruption' },
    { key: 'severe', label: 'Severe' },
];

const evidenceStyles: Record<EvidenceKind, string> = {
    REAL: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300',
    OFFICIAL_FORECAST:
        'bg-cyan-100 text-cyan-800 dark:bg-cyan-950 dark:text-cyan-300',
    MODEL: 'bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300',
    SIMULATED:
        'bg-violet-100 text-violet-800 dark:bg-violet-950 dark:text-violet-300',
    ASSUMED:
        'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300',
};

const selectedAction = computed<FrontendAction | null>(
    () =>
        props.logistics.actions.find(
            (candidate) =>
                candidate.action === props.logistics.recommendation.action,
        ) ?? null,
);

const summary = computed(() => recommendationSummary(props.logistics));
const traffic = computed(
    () => props.logistics.external_state.traffic[0] ?? null,
);
const navigation = computed(() => props.logistics.external_state.navigation);
const warnings = computed(() => [
    ...props.logistics.external_state.warnings,
    ...(navigation.value.warnings ?? []),
]);
const provenanceRows = computed(() =>
    Object.entries(props.logistics.data_provenance).map(([key, value]) => ({
        key,
        ...value,
    })),
);
const whyNotRows = computed(() =>
    Object.entries(props.logistics.recommendation.why_not).map(
        ([action, explanation]) => ({ action, explanation: explanation ?? '' }),
    ),
);
const operationalKpis = computed(() => [
    {
        label: 'Production continuity',
        value: selectedAction.value
            ? formatPercent(
                  selectedAction.value.production_continuity_probability,
              )
            : '—',
        detail: 'Factory deadline met',
    },
    {
        label: 'On-time arrival',
        value: selectedAction.value
            ? formatPercent(selectedAction.value.on_time_arrival_probability)
            : '—',
        detail: 'Incoming shipment deadline met',
    },
    {
        label: 'Expected incoming delay',
        value: selectedAction.value
            ? formatMinutes(selectedAction.value.predicted_arrival_delay_min)
            : '—',
        detail: 'Mean over simulated journeys',
    },
]);
const snapshotAt = computed(() =>
    new Intl.DateTimeFormat('en-GB', {
        dateStyle: 'medium',
        timeStyle: 'short',
        timeZone: 'Europe/Zurich',
    }).format(new Date(props.logistics.as_of)),
);
const formatNumber = (value: number | null, digits = 1) =>
    value === null ? '—' : value.toFixed(digits);
</script>

<template>
    <div class="mx-auto flex w-full max-w-7xl flex-1 flex-col gap-4 p-4 md:p-6">
        <Head title="BioFlow decision dashboard" />

        <header class="flex flex-wrap items-start justify-between gap-3">
            <div>
                <div
                    class="text-xs font-semibold tracking-[0.18em] text-sky-700 uppercase dark:text-sky-400"
                >
                    BioFlow · Rhine to reactor
                </div>
                <h1 class="mt-1 text-3xl font-bold tracking-tight">
                    Manufacturing decision dashboard
                </h1>
                <p class="mt-1 text-sm text-muted-foreground">
                    Observed Basel signals → simulated outcomes → compared
                    actions → explained recommendation
                </p>
            </div>
            <div class="flex flex-col gap-1 text-xs sm:items-end">
                <span
                    class="rounded border border-dashed border-violet-500/70 px-2 py-1 font-semibold text-violet-700 dark:text-violet-300"
                >
                    SIMULATED SHIPMENT
                </span>
                <span class="text-muted-foreground">{{
                    logistics.shipment_id
                }}</span>
                <span class="text-muted-foreground"
                    >As of {{ snapshotAt }} Basel</span
                >
            </div>
        </header>

        <nav
            aria-label="Logistics scenario"
            class="flex flex-wrap items-center gap-2"
        >
            <span class="mr-1 text-xs font-semibold text-muted-foreground"
                >Scenario</span
            >
            <Link
                v-for="item in scenarios"
                :key="item.key"
                :href="`/dashboard?scenario=${item.key}`"
                :aria-current="scenario === item.key ? 'page' : undefined"
                class="rounded-lg border px-4 py-1.5 text-sm font-medium transition-colors hover:bg-accent"
                :class="
                    scenario === item.key
                        ? 'border-sky-600 bg-sky-50 text-sky-800 dark:bg-sky-950/40 dark:text-sky-300'
                        : 'bg-card'
                "
            >
                {{ item.label }}
            </Link>
        </nav>

        <section
            v-if="warnings.length > 0"
            role="status"
            class="rounded-xl border border-amber-500/50 bg-amber-50 p-3 text-sm dark:bg-amber-950/20"
        >
            <h2 class="font-semibold text-amber-800 dark:text-amber-300">
                Evidence warnings
            </h2>
            <ul
                class="mt-1 list-disc pl-5 text-amber-900/80 dark:text-amber-200/80"
            >
                <li v-for="warning in warnings" :key="warning">
                    {{ warning }}
                </li>
            </ul>
        </section>

        <section
            aria-label="Recommended action outcomes"
            class="grid gap-3 sm:grid-cols-2 lg:grid-cols-5"
        >
            <div
                class="rounded-xl border-2 border-sky-600/60 bg-sky-50/40 p-4 sm:col-span-2 dark:bg-sky-950/20"
            >
                <div class="flex flex-wrap items-center justify-between gap-2">
                    <h2
                        class="text-xs font-semibold text-sky-700 uppercase dark:text-sky-400"
                    >
                        Recommended action
                    </h2>
                    <span
                        class="rounded border bg-card px-2 py-0.5 text-xs text-muted-foreground"
                    >
                        Evidence {{ logistics.recommendation.confidence }}
                    </span>
                </div>
                <div class="mt-1 text-4xl font-bold tracking-tight">
                    {{ logistics.recommendation.action ?? 'Reassess' }}
                </div>
                <p class="mt-2 text-sm leading-relaxed">{{ summary }}</p>
                <p class="mt-2 text-xs text-muted-foreground">
                    Evidence quality is categorical, not a probability.
                </p>
            </div>
            <div
                v-for="kpi in operationalKpis"
                :key="kpi.label"
                class="flex flex-col rounded-xl border bg-card p-4"
            >
                <h2 class="text-sm font-medium text-muted-foreground">
                    {{ kpi.label }}
                </h2>
                <div
                    class="mt-2 text-3xl font-bold tracking-tight tabular-nums"
                >
                    {{ kpi.value }}
                </div>
                <p class="mt-2 text-xs text-muted-foreground">
                    {{ kpi.detail }}
                </p>
                <span
                    class="mt-auto pt-3 text-xs font-semibold text-blue-700 dark:text-blue-300"
                    >MODEL · selected action</span
                >
            </div>
        </section>

        <section
            aria-label="Basel signals"
            class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4"
        >
            <article class="rounded-xl border bg-card p-3">
                <div class="flex items-center justify-between gap-2">
                    <h2 class="text-sm font-semibold">Basel traffic</h2>
                    <span
                        v-if="logistics.data_provenance.traffic_current"
                        class="rounded px-1.5 py-0.5 text-xs font-semibold"
                        :class="
                            evidenceStyles[
                                logistics.data_provenance.traffic_current.kind
                            ]
                        "
                    >
                        {{ logistics.data_provenance.traffic_current.kind }}
                    </span>
                    <span v-else class="text-xs text-muted-foreground"
                        >Unlinked evidence</span
                    >
                </div>
                <template v-if="traffic">
                    <div class="mt-2 text-2xl font-bold tabular-nums">
                        {{ traffic.observed_count.toFixed(0) }}
                        <span class="text-sm font-normal text-muted-foreground"
                            >vehicles</span
                        >
                    </div>
                    <p class="mt-1 text-xs text-muted-foreground">
                        Station {{ traffic.station_id }} ·
                        {{ traffic.status.replaceAll('_', ' ') }}
                    </p>
                    <p class="mt-1 text-xs text-muted-foreground">
                        z-score
                        <b class="font-medium text-foreground">{{
                            formatNumber(traffic.z_score, 2)
                        }}</b>
                        · {{ traffic.baseline_sample_count }} baseline samples
                        <span
                            v-if="logistics.data_provenance.traffic_anomaly"
                            class="ml-1 font-semibold"
                            :class="
                                evidenceStyles[
                                    logistics.data_provenance.traffic_anomaly
                                        .kind
                                ]
                            "
                            >{{
                                logistics.data_provenance.traffic_anomaly.kind
                            }}</span
                        >
                    </p>
                </template>
                <p v-else class="mt-2 text-sm text-muted-foreground">
                    No current traffic observation.
                </p>
            </article>
            <article class="rounded-xl border bg-card p-3">
                <div class="flex items-center justify-between gap-2">
                    <h2 class="text-sm font-semibold">Rhine</h2>
                    <span
                        v-if="logistics.data_provenance.rhine_current"
                        class="rounded px-1.5 py-0.5 text-xs font-semibold"
                        :class="
                            evidenceStyles[
                                logistics.data_provenance.rhine_current.kind
                            ]
                        "
                    >
                        {{ logistics.data_provenance.rhine_current.kind }}
                    </span>
                    <span v-else class="text-xs text-muted-foreground"
                        >Unlinked evidence</span
                    >
                </div>
                <template v-if="logistics.external_state.rhine">
                    <div class="mt-2 text-2xl font-bold tabular-nums">
                        {{
                            formatNumber(
                                logistics.external_state.rhine.discharge_m3_s,
                            )
                        }}
                        <span class="text-sm font-normal text-muted-foreground"
                            >m³/s</span
                        >
                    </div>
                    <p class="mt-1 text-xs text-muted-foreground">
                        Level
                        {{
                            formatNumber(
                                logistics.external_state.rhine.level_masl,
                                3,
                            )
                        }}
                        m ASL
                    </p>
                    <p class="mt-1 text-xs text-muted-foreground">
                        Trend
                        <b class="font-medium text-foreground"
                            >{{
                                formatNumber(
                                    logistics.external_state.rhine
                                        .level_trend_cm_per_hour,
                                    2,
                                )
                            }}
                            cm/h</b
                        >
                        <span
                            v-if="logistics.data_provenance.rhine_trends"
                            class="ml-1 font-semibold"
                            :class="
                                evidenceStyles[
                                    logistics.data_provenance.rhine_trends.kind
                                ]
                            "
                            >{{
                                logistics.data_provenance.rhine_trends.kind
                            }}</span
                        >
                    </p>
                </template>
                <p v-else class="mt-2 text-sm text-muted-foreground">
                    No current Rhine observation.
                </p>
            </article>
            <article class="rounded-xl border bg-card p-3">
                <div class="flex items-center justify-between gap-2">
                    <h2 class="text-sm font-semibold">Weather</h2>
                    <span
                        v-if="logistics.data_provenance.weather_current"
                        class="rounded px-1.5 py-0.5 text-xs font-semibold"
                        :class="
                            evidenceStyles[
                                logistics.data_provenance.weather_current.kind
                            ]
                        "
                    >
                        {{ logistics.data_provenance.weather_current.kind }}
                    </span>
                    <span v-else class="text-xs text-muted-foreground"
                        >Unlinked evidence</span
                    >
                </div>
                <template v-if="logistics.external_state.weather">
                    <div class="mt-2 text-2xl font-bold tabular-nums">
                        {{
                            formatNumber(
                                logistics.external_state.weather
                                    .air_temperature_c,
                            )
                        }}
                        <span class="text-sm font-normal text-muted-foreground"
                            >°C</span
                        >
                    </div>
                    <p class="mt-1 text-xs text-muted-foreground">
                        Rain
                        {{
                            formatNumber(
                                logistics.external_state.weather
                                    .precipitation_mm,
                            )
                        }}
                        mm · wind
                        {{
                            formatNumber(
                                logistics.external_state.weather.wind_speed_m_s,
                            )
                        }}
                        m/s
                    </p>
                    <p class="mt-1 text-xs text-muted-foreground">
                        Trend
                        {{
                            formatNumber(
                                logistics.external_state.weather
                                    .temperature_trend_c_per_hour,
                                2,
                            )
                        }}
                        °C/h
                        <span
                            v-if="logistics.data_provenance.weather_trend"
                            class="ml-1 font-semibold"
                            :class="
                                evidenceStyles[
                                    logistics.data_provenance.weather_trend.kind
                                ]
                            "
                            >{{
                                logistics.data_provenance.weather_trend.kind
                            }}</span
                        >
                    </p>
                </template>
                <p v-else class="mt-2 text-sm text-muted-foreground">
                    No current weather observation.
                </p>
            </article>
            <article class="rounded-xl border bg-card p-3">
                <div class="flex items-center justify-between gap-2">
                    <h2 class="text-sm font-semibold">Navigation</h2>
                    <span
                        class="rounded px-1.5 py-0.5 text-xs font-semibold"
                        :class="evidenceStyles[navigation.kind]"
                        >{{ navigation.kind }}</span
                    >
                </div>
                <div class="mt-2 flex flex-wrap items-baseline gap-2">
                    <strong class="text-2xl tracking-tight">{{
                        navigation.state
                    }}</strong>
                    <span class="text-lg font-semibold tabular-nums"
                        >+{{
                            formatMinutes(navigation.delay_penalty_min)
                        }}</span
                    >
                </div>
                <p class="mt-1 text-xs text-muted-foreground">
                    Delay contribution
                    <span
                        class="font-semibold"
                        :class="evidenceStyles[navigation.delay_kind]"
                        >{{ navigation.delay_kind }}</span
                    >
                </p>
                <details class="mt-1 text-xs text-muted-foreground">
                    <summary class="cursor-pointer">
                        {{
                            navigation.normal_route_eligible
                                ? 'Normal route eligible'
                                : 'Normal route unavailable'
                        }}
                        · details
                    </summary>
                    <p class="mt-2 leading-relaxed">{{ navigation.reason }}</p>
                </details>
            </article>
        </section>

        <section class="rounded-xl border-2 border-sky-600/60 bg-card p-4">
            <div
                class="mb-3 flex flex-wrap items-baseline justify-between gap-2"
            >
                <h2 class="text-xl font-bold">Compare operational actions</h2>
                <p class="text-xs text-muted-foreground">
                    MODEL · seeded simulation frequencies under assumptions
                </p>
            </div>
            <div class="grid gap-3 lg:grid-cols-3">
                <article
                    v-for="option in logistics.actions"
                    :key="option.action"
                    class="flex flex-col gap-3 rounded-xl border-2 p-3"
                    :class="
                        option.action === logistics.recommendation.action
                            ? 'border-sky-600 bg-sky-50 dark:bg-sky-950/30'
                            : option.eligible
                              ? 'border-border'
                              : 'border-dashed opacity-70'
                    "
                >
                    <div class="flex items-center justify-between gap-2">
                        <h3 class="text-xl font-bold tracking-tight">
                            {{ option.action }}
                        </h3>
                        <span
                            v-if="
                                option.action ===
                                logistics.recommendation.action
                            "
                            class="rounded bg-sky-100 px-2 py-1 text-xs font-semibold text-sky-800 dark:bg-sky-900 dark:text-sky-200"
                            >RECOMMENDED</span
                        >
                        <span
                            v-else
                            class="rounded px-2 py-1 text-xs font-semibold"
                            :class="
                                option.eligible
                                    ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300'
                                    : 'bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300'
                            "
                            >{{
                                option.eligible ? 'ELIGIBLE' : 'INELIGIBLE'
                            }}</span
                        >
                    </div>
                    <dl
                        class="grid grid-cols-2 items-baseline gap-x-3 gap-y-2 text-sm"
                    >
                        <dt class="text-muted-foreground">
                            Production continuity
                        </dt>
                        <dd
                            class="text-right text-lg font-semibold tabular-nums"
                        >
                            {{
                                formatPercent(
                                    option.production_continuity_probability,
                                )
                            }}
                        </dd>
                        <dt class="text-muted-foreground">On-time arrival</dt>
                        <dd
                            class="text-right text-lg font-semibold tabular-nums"
                        >
                            {{
                                formatPercent(
                                    option.on_time_arrival_probability,
                                )
                            }}
                        </dd>
                        <dt class="text-muted-foreground">
                            Cold-chain exposure proxy
                        </dt>
                        <dd class="text-right font-semibold tabular-nums">
                            {{
                                formatPercent(
                                    option.cold_chain_exposure_proxy_risk,
                                )
                            }}
                        </dd>
                        <dt class="text-muted-foreground">
                            Incoming mean delay
                        </dt>
                        <dd class="text-right font-semibold tabular-nums">
                            {{
                                formatMinutes(
                                    option.predicted_arrival_delay_min,
                                )
                            }}
                        </dd>
                        <dt class="text-muted-foreground">
                            Factory mean delay
                        </dt>
                        <dd class="text-right font-semibold tabular-nums">
                            {{ formatMinutes(option.predicted_delay_min) }}
                        </dd>
                    </dl>
                    <p
                        class="mt-auto text-xs leading-relaxed text-muted-foreground"
                    >
                        {{ option.assessment }}
                    </p>
                </article>
            </div>
            <p class="mt-3 text-xs text-muted-foreground">
                Cold-chain proxy only — ambient conditions do not establish an
                actual product-temperature excursion, pharmaceutical quality or
                QA release status.
            </p>
        </section>

        <section
            class="grid gap-4 rounded-xl border bg-card p-4 lg:grid-cols-2"
        >
            <div>
                <h2 class="text-lg font-semibold">Why this recommendation</h2>
                <p class="mt-2 text-sm leading-relaxed">
                    {{
                        humanizeRecommendationReason(
                            logistics.recommendation.reason,
                        )
                    }}
                </p>
                <h3 class="mt-4 text-sm font-semibold">
                    Why not the alternatives?
                </h3>
                <ul class="mt-2 flex flex-col gap-2">
                    <li
                        v-for="row in whyNotRows"
                        :key="row.action"
                        class="rounded-lg border p-3 text-sm"
                    >
                        <b>{{ row.action }}</b>
                        <p class="mt-1 leading-relaxed text-muted-foreground">
                            {{ humanizeAlternativeReason(row.explanation) }}
                        </p>
                    </li>
                </ul>
                <p
                    v-if="whyNotRows.length === 0"
                    class="mt-2 text-sm text-muted-foreground"
                >
                    No alternative reasons supplied.
                </p>
            </div>
            <div>
                <h2 class="text-lg font-semibold">Would change if</h2>
                <p class="mt-1 text-xs text-muted-foreground">
                    Tested scenario changes; these are examples, not universal
                    thresholds.
                </p>
                <ul
                    v-if="logistics.recommendation.would_change_if.length > 0"
                    class="mt-3 space-y-3 text-sm"
                >
                    <li
                        v-for="condition in logistics.recommendation
                            .would_change_if"
                        :key="condition"
                        class="rounded-lg border p-3"
                    >
                        {{ humanizeCounterfactual(condition) }}
                    </li>
                </ul>
                <p v-else class="mt-3 text-sm text-muted-foreground">
                    No evaluated change altered the recommendation.
                </p>
            </div>
        </section>

        <details class="rounded-xl border bg-card p-4">
            <summary class="cursor-pointer font-semibold">
                Evidence &amp; provenance
                <span class="ml-2 text-xs font-normal text-muted-foreground"
                    >{{ provenanceRows.length }} entries</span
                >
            </summary>
            <p class="mt-2 text-sm text-muted-foreground">
                Observed, modeled, simulated and assumed evidence stays
                distinct.
            </p>
            <div class="mt-3 grid gap-3 lg:grid-cols-2">
                <article
                    v-for="row in provenanceRows"
                    :key="row.key"
                    class="rounded-lg border p-3"
                >
                    <div class="flex items-start justify-between gap-3">
                        <div class="text-sm font-medium">
                            {{ row.key.replaceAll('_', ' ') }}
                        </div>
                        <span
                            class="rounded px-1.5 py-0.5 text-xs font-semibold"
                            :class="evidenceStyles[row.kind]"
                            >{{ row.kind }}</span
                        >
                    </div>
                    <p class="mt-2 text-sm text-muted-foreground">
                        {{ row.detail }}
                    </p>
                    <div
                        v-if="row.provider"
                        class="mt-2 text-xs text-muted-foreground"
                    >
                        {{ row.provider }}
                    </div>
                    <div
                        v-if="row.observed_at"
                        class="mt-1 text-xs text-muted-foreground"
                    >
                        Observed at {{ row.observed_at }}
                    </div>
                </article>
            </div>
        </details>

        <details class="rounded-xl border bg-card p-4">
            <summary class="cursor-pointer font-semibold">
                Model limitations ({{ logistics.limitations.length }})
            </summary>
            <ul
                class="mt-3 list-disc space-y-2 pl-5 text-sm text-muted-foreground"
            >
                <li v-for="item in logistics.limitations" :key="item">
                    {{ item }}
                </li>
            </ul>
        </details>

        <details class="rounded-xl border bg-card p-4">
            <summary class="cursor-pointer font-semibold">
                Decision policy
            </summary>
            <p class="mt-3 text-sm leading-relaxed text-muted-foreground">
                {{ logistics.recommendation.policy_detail }}
            </p>
            <h3 class="mt-4 text-sm font-semibold">
                Baseline incoming shipment · before intervention
            </h3>
            <p class="mt-2 text-sm text-muted-foreground">
                Mean delay
                {{
                    formatMinutes(
                        logistics.operational_impact.predicted_delay_min,
                    )
                }}
                · delay frequency
                {{ formatPercent(logistics.operational_impact.delay_risk) }} ·
                cold-chain exposure proxy
                {{
                    formatPercent(
                        logistics.operational_impact
                            .cold_chain_exposure_proxy_risk,
                    )
                }}
            </p>
            <h3 class="mt-4 text-sm font-semibold">
                Original model explanations
            </h3>
            <p class="mt-2 text-sm leading-relaxed text-muted-foreground">
                {{ logistics.recommendation.reason }}
            </p>
            <ul class="mt-3 space-y-2 text-sm text-muted-foreground">
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
        </details>

        <footer class="pb-2 text-xs text-muted-foreground">
            The logistics JSON supplies the recommendation. A person makes the
            operational decision.
        </footer>
    </div>
</template>
