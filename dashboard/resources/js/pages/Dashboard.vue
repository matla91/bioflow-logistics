<script setup lang="ts">
import { Head, Link } from '@inertiajs/vue3';
import { computed } from 'vue';
import type {
    EvidenceKind,
    FrontendAction,
    LogisticsAction,
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

const scenarios: { key: ScenarioKey; label: string; expected: string }[] = [
    { key: 'normal', label: 'Normal', expected: 'BUFFER' },
    { key: 'disruption', label: 'Disruption', expected: 'EXPEDITE' },
    { key: 'severe', label: 'Severe', expected: 'REROUTE' },
];

const actionLabels: Record<LogisticsAction, string> = {
    BUFFER: 'Buffer',
    EXPEDITE: 'Expedite',
    REROUTE: 'Reroute',
};

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

const selectedAction = computed<FrontendAction | null>(() => {
    const action = props.logistics.recommendation.action;

    return (
        props.logistics.actions.find((candidate) => candidate.action === action) ??
        null
    );
});

const traffic = computed(() => props.logistics.external_state.traffic[0] ?? null);

const warnings = computed(() => [
    ...props.logistics.external_state.warnings,
    ...(props.logistics.external_state.navigation.warnings ?? []),
]);

const provenanceRows = computed(() =>
    Object.entries(props.logistics.data_provenance).map(([key, value]) => ({
        key,
        ...value,
    })),
);

const whyNotRows = computed(() =>
    Object.entries(props.logistics.recommendation.why_not).map(
        ([action, explanation]) => ({
            action: action as LogisticsAction,
            explanation: explanation ?? '',
        }),
    ),
);

const formatPercent = (value: number) => `${(value * 100).toFixed(1)}%`;
const formatMinutes = (value: number) =>
    value < 0.05 ? '<0.1 min' : `${value.toFixed(1)} min`;
const formatNumber = (value: number | null, digits = 1) =>
    value === null ? '—' : value.toFixed(digits);
</script>

<template>
    <div class="mx-auto flex w-full max-w-7xl flex-1 flex-col gap-6 p-4 md:p-6">
        <Head title="BioFlow decision dashboard" />

        <header class="flex flex-wrap items-start justify-between gap-4">
            <div>
                <div
                    class="text-xs font-semibold tracking-[0.18em] text-sky-700 uppercase dark:text-sky-400"
                >
                    BioFlow · Rhine to reactor
                </div>
                <h1 class="mt-1 text-3xl font-bold tracking-tight">
                    Manufacturing decision dashboard
                </h1>
                <p class="mt-1 max-w-3xl text-sm text-muted-foreground">
                    Real Basel signals feed a Monte Carlo logistics model and a
                    deterministic decision policy. The dashboard displays the
                    model output; it does not recompute the recommendation.
                </p>
            </div>

            <div class="flex flex-col items-end gap-2 text-xs">
                <span
                    class="rounded border-2 border-dashed border-violet-500/70 px-2.5 py-1 font-semibold text-violet-700 dark:text-violet-300"
                >
                    SIMULATED SHIPMENT
                </span>
                <span class="text-muted-foreground">
                    {{ logistics.shipment_id }} · as of
                    {{ new Date(logistics.as_of).toLocaleString() }}
                </span>
            </div>
        </header>

        <nav class="flex flex-wrap gap-2">
            <Link
                v-for="item in scenarios"
                :key="item.key"
                :href="`/dashboard?scenario=${item.key}`"
                class="rounded-lg border px-4 py-2 text-sm font-medium transition-colors hover:bg-accent"
                :class="
                    scenario === item.key
                        ? 'border-sky-600 bg-sky-50 text-sky-800 dark:bg-sky-950/40 dark:text-sky-300'
                        : 'bg-card'
                "
            >
                {{ item.label }}
                <span class="ml-1 text-xs text-muted-foreground">
                    → {{ item.expected }}
                </span>
            </Link>
        </nav>

        <section
            v-if="warnings.length > 0"
            class="rounded-xl border border-amber-500/50 bg-amber-50 p-4 text-sm dark:bg-amber-950/20"
        >
            <div class="font-semibold text-amber-800 dark:text-amber-300">
                Evidence warnings
            </div>
            <ul class="mt-1 list-disc pl-5 text-amber-900/80 dark:text-amber-200/80">
                <li v-for="warning in warnings" :key="warning">
                    {{ warning }}
                </li>
            </ul>
        </section>

        <section class="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <div class="rounded-xl border-2 border-sky-600/60 bg-card p-4">
                <div class="text-xs font-semibold text-sky-700 uppercase dark:text-sky-400">
                    Recommended action
                </div>
                <div class="mt-1 text-3xl font-bold tracking-tight">
                    {{
                        logistics.recommendation.action
                            ? actionLabels[logistics.recommendation.action]
                            : 'Reassess'
                    }}
                </div>
            </div>

            <div class="rounded-xl border bg-card p-4">
                <div class="text-sm text-muted-foreground">
                    Evidence quality
                </div>
                <div class="mt-1 text-3xl font-bold">
                    {{ logistics.recommendation.confidence }}
                </div>
                <div class="mt-1 text-xs text-muted-foreground">
                    Categorical evidence quality, not a probability.
                </div>
            </div>

            <div class="rounded-xl border bg-card p-4">
                <div class="text-sm text-muted-foreground">
                    Baseline mean lateness
                </div>
                <div class="mt-1 text-3xl font-bold tabular-nums">
                    {{
                        formatMinutes(
                            logistics.operational_impact.predicted_delay_min,
                        )
                    }}
                </div>
            </div>

            <div class="rounded-xl border bg-card p-4">
                <div class="text-sm text-muted-foreground">
                    Baseline delay frequency
                </div>
                <div class="mt-1 text-3xl font-bold tabular-nums">
                    {{ formatPercent(logistics.operational_impact.delay_risk) }}
                </div>
                <div class="mt-1 text-xs text-muted-foreground">
                    Monte Carlo scenario frequency under assumptions.
                </div>
            </div>
        </section>

        <section class="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <article class="rounded-xl border bg-card p-4">
                <div class="flex items-center justify-between gap-2">
                    <h2 class="font-semibold">Basel traffic</h2>
                    <span
                        class="rounded px-1.5 py-0.5 text-xs font-semibold"
                        :class="evidenceStyles[logistics.data_provenance.traffic_current?.kind ?? 'REAL']"
                    >
                        {{ logistics.data_provenance.traffic_current?.kind ?? 'REAL' }}
                    </span>
                </div>
                <template v-if="traffic">
                    <div class="mt-3 text-2xl font-bold tabular-nums">
                        {{ traffic.observed_count.toFixed(0) }}
                    </div>
                    <div class="text-sm text-muted-foreground">
                        vehicles · station {{ traffic.station_id }}
                    </div>
                    <div class="mt-2 text-sm">
                        z-score
                        <b>{{ formatNumber(traffic.z_score, 2) }}</b>
                        · baseline n={{ traffic.baseline_sample_count }}
                    </div>
                </template>
                <p v-else class="mt-3 text-sm text-muted-foreground">
                    No current traffic observation.
                </p>
            </article>

            <article class="rounded-xl border bg-card p-4">
                <div class="flex items-center justify-between gap-2">
                    <h2 class="font-semibold">Rhine</h2>
                    <span
                        class="rounded px-1.5 py-0.5 text-xs font-semibold"
                        :class="evidenceStyles[logistics.data_provenance.rhine_current?.kind ?? 'REAL']"
                    >
                        {{ logistics.data_provenance.rhine_current?.kind ?? 'REAL' }}
                    </span>
                </div>
                <template v-if="logistics.external_state.rhine">
                    <div class="mt-3 text-2xl font-bold tabular-nums">
                        {{
                            formatNumber(
                                logistics.external_state.rhine.discharge_m3_s,
                                1,
                            )
                        }}
                        <span class="text-sm font-normal">m³/s</span>
                    </div>
                    <div class="text-sm text-muted-foreground">
                        level
                        {{
                            formatNumber(
                                logistics.external_state.rhine.level_masl,
                                3,
                            )
                        }}
                        masl
                    </div>
                    <div class="mt-2 text-sm">
                        level trend
                        <b>
                            {{
                                formatNumber(
                                    logistics.external_state.rhine
                                        .level_trend_cm_per_hour,
                                    2,
                                )
                            }}
                            cm/h
                        </b>
                    </div>
                </template>
                <p v-else class="mt-3 text-sm text-muted-foreground">
                    No current Rhine observation.
                </p>
            </article>

            <article class="rounded-xl border bg-card p-4">
                <div class="flex items-center justify-between gap-2">
                    <h2 class="font-semibold">Weather</h2>
                    <span
                        class="rounded px-1.5 py-0.5 text-xs font-semibold"
                        :class="evidenceStyles[logistics.data_provenance.weather_current?.kind ?? 'REAL']"
                    >
                        {{ logistics.data_provenance.weather_current?.kind ?? 'REAL' }}
                    </span>
                </div>
                <template v-if="logistics.external_state.weather">
                    <div class="mt-3 text-2xl font-bold tabular-nums">
                        {{ logistics.external_state.weather.air_temperature_c.toFixed(1) }}
                        <span class="text-sm font-normal">°C</span>
                    </div>
                    <div class="text-sm text-muted-foreground">
                        rain
                        {{
                            formatNumber(
                                logistics.external_state.weather.precipitation_mm,
                                1,
                            )
                        }}
                        mm · wind
                        {{
                            formatNumber(
                                logistics.external_state.weather.wind_speed_m_s,
                                1,
                            )
                        }}
                        m/s
                    </div>
                    <div class="mt-2 text-sm">
                        temperature trend
                        <b>
                            {{
                                formatNumber(
                                    logistics.external_state.weather
                                        .temperature_trend_c_per_hour,
                                    2,
                                )
                            }}
                            °C/h
                        </b>
                    </div>
                </template>
                <p v-else class="mt-3 text-sm text-muted-foreground">
                    No current weather observation.
                </p>
            </article>

            <article class="rounded-xl border bg-card p-4">
                <div class="flex items-center justify-between gap-2">
                    <h2 class="font-semibold">Navigation</h2>
                    <span
                        class="rounded px-1.5 py-0.5 text-xs font-semibold"
                        :class="evidenceStyles[logistics.external_state.navigation.kind]"
                    >
                        {{ logistics.external_state.navigation.kind }}
                    </span>
                </div>
                <div class="mt-3 text-2xl font-bold">
                    {{ logistics.external_state.navigation.state }}
                </div>
                <div class="text-sm text-muted-foreground">
                    {{
                        formatMinutes(
                            logistics.external_state.navigation.delay_penalty_min,
                        )
                    }}
                    modeled delay addition
                </div>
                <p class="mt-2 text-xs text-muted-foreground">
                    {{ logistics.external_state.navigation.reason }}
                </p>
            </article>
        </section>

        <section
            class="flex flex-col gap-4 rounded-xl border-2 border-sky-600/60 bg-card p-5"
        >
            <div class="flex flex-wrap items-end justify-between gap-3">
                <div>
                    <div
                        class="text-xs font-semibold tracking-wide text-sky-700 uppercase dark:text-sky-400"
                    >
                        Decision policy output
                    </div>
                    <h2 class="mt-1 text-2xl font-bold">
                        Compare operational actions
                    </h2>
                </div>
                <div class="text-right text-xs text-muted-foreground">
                    Frequencies come from the seeded simulation.<br />
                    Evidence quality is reported separately.
                </div>
            </div>

            <div class="grid gap-3 lg:grid-cols-3">
                <article
                    v-for="option in logistics.actions"
                    :key="option.action"
                    class="flex flex-col gap-3 rounded-xl border-2 p-4"
                    :class="
                        option.action === logistics.recommendation.action
                            ? 'border-sky-600 bg-sky-50 dark:bg-sky-950/30'
                            : option.eligible
                              ? 'border-border'
                              : 'border-dashed opacity-70'
                    "
                >
                    <div class="flex items-start justify-between gap-2">
                        <div>
                            <div
                                v-if="option.action === logistics.recommendation.action"
                                class="text-xs font-semibold text-sky-700 uppercase dark:text-sky-400"
                            >
                                Recommended
                            </div>
                            <h3 class="text-xl font-bold">
                                {{ actionLabels[option.action] }}
                            </h3>
                        </div>
                        <span
                            class="rounded px-2 py-1 text-xs font-semibold"
                            :class="
                                option.eligible
                                    ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300'
                                    : 'bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300'
                            "
                        >
                            {{ option.eligible ? 'ELIGIBLE' : 'INELIGIBLE' }}
                        </span>
                    </div>

                    <dl class="grid grid-cols-2 gap-x-3 gap-y-2 text-sm">
                        <dt class="text-muted-foreground">
                            Production continuity
                        </dt>
                        <dd class="text-right font-semibold tabular-nums">
                            {{
                                formatPercent(
                                    option.production_continuity_probability,
                                )
                            }}
                        </dd>

                        <dt class="text-muted-foreground">On-time arrival</dt>
                        <dd class="text-right font-semibold tabular-nums">
                            {{ formatPercent(option.on_time_arrival_probability) }}
                        </dd>

                        <dt class="text-muted-foreground">
                            Exposure proxy risk
                        </dt>
                        <dd class="text-right font-semibold tabular-nums">
                            {{
                                formatPercent(
                                    option.cold_chain_exposure_proxy_risk,
                                )
                            }}
                        </dd>

                        <dt class="text-muted-foreground">
                            Incoming mean lateness
                        </dt>
                        <dd class="text-right font-semibold tabular-nums">
                            {{
                                formatMinutes(
                                    option.predicted_arrival_delay_min,
                                )
                            }}
                        </dd>
                    </dl>

                    <p class="mt-auto text-xs leading-relaxed text-muted-foreground">
                        {{ option.assessment }}
                    </p>
                </article>
            </div>
        </section>

        <section class="grid gap-6 rounded-xl border bg-card p-5 lg:grid-cols-2">
            <div>
                <div
                    class="text-xs font-semibold tracking-wide text-sky-700 uppercase dark:text-sky-400"
                >
                    Why this recommendation
                </div>
                <h2 class="mt-1 text-xl font-bold">
                    {{
                        logistics.recommendation.action
                            ? actionLabels[logistics.recommendation.action]
                            : 'Reassessment required'
                    }}
                </h2>
                <p class="mt-2 text-sm leading-relaxed">
                    {{ logistics.recommendation.reason }}
                </p>

                <div v-if="selectedAction" class="mt-4 grid grid-cols-2 gap-3">
                    <div class="rounded-lg bg-muted/50 p-3">
                        <div class="text-xs text-muted-foreground">
                            Production continuity
                        </div>
                        <div class="text-xl font-bold tabular-nums">
                            {{
                                formatPercent(
                                    selectedAction.production_continuity_probability,
                                )
                            }}
                        </div>
                    </div>
                    <div class="rounded-lg bg-muted/50 p-3">
                        <div class="text-xs text-muted-foreground">
                            Incoming on time
                        </div>
                        <div class="text-xl font-bold tabular-nums">
                            {{
                                formatPercent(
                                    selectedAction.on_time_arrival_probability,
                                )
                            }}
                        </div>
                    </div>
                </div>

                <div class="mt-5">
                    <h3 class="text-sm font-semibold">Why not the alternatives?</h3>
                    <ul class="mt-2 flex flex-col gap-2">
                        <li
                            v-for="row in whyNotRows"
                            :key="row.action"
                            class="rounded-lg border p-3 text-sm"
                        >
                            <b>{{ actionLabels[row.action] }}</b>
                            <p class="mt-1 text-muted-foreground">
                                {{ row.explanation }}
                            </p>
                        </li>
                    </ul>
                </div>
            </div>

            <div class="flex flex-col gap-5">
                <div>
                    <h3 class="text-sm font-semibold">Would change if</h3>
                    <ul
                        class="mt-2 list-disc space-y-2 pl-5 text-sm text-muted-foreground"
                    >
                        <li
                            v-for="condition in logistics.recommendation
                                .would_change_if"
                            :key="condition"
                        >
                            {{ condition }}
                        </li>
                    </ul>
                </div>

                <div class="rounded-lg border border-amber-500/40 p-4">
                    <div class="text-sm font-semibold">
                        Cold-chain interpretation guardrail
                    </div>
                    <p class="mt-1 text-sm text-muted-foreground">
                        The displayed cold-chain metric is an ambient exposure
                        proxy. Ambient weather alone does not establish an actual
                        product-temperature excursion, pharmaceutical quality, or
                        QA release status.
                    </p>
                </div>

                <details>
                    <summary class="cursor-pointer text-sm font-semibold">
                        Decision policy
                    </summary>
                    <p class="mt-2 text-xs leading-relaxed text-muted-foreground">
                        {{ logistics.recommendation.policy_detail }}
                    </p>
                </details>
            </div>
        </section>

        <section class="rounded-xl border bg-card p-5">
            <div>
                <h2 class="text-lg font-semibold">Evidence provenance</h2>
                <p class="mt-1 text-sm text-muted-foreground">
                    Observed, modeled, simulated and assumed inputs are kept
                    distinct.
                </p>
            </div>

            <div class="mt-4 grid gap-3 lg:grid-cols-2">
                <article
                    v-for="row in provenanceRows"
                    :key="row.key"
                    class="rounded-lg border p-3"
                >
                    <div class="flex items-start justify-between gap-3">
                        <div class="font-mono text-xs">
                            {{ row.key }}
                        </div>
                        <span
                            class="rounded px-1.5 py-0.5 text-xs font-semibold"
                            :class="evidenceStyles[row.kind]"
                        >
                            {{ row.kind }}
                        </span>
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
                </article>
            </div>
        </section>

        <details class="rounded-xl border bg-card p-5">
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

        <footer class="pb-4 text-xs text-muted-foreground">
            Dashboard UI adapted from the team console. Decision values are read
            directly from the logistics frontend JSON contract.
        </footer>
    </div>
</template>
