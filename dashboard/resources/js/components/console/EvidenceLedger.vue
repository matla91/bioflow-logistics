<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import type { ShipmentConsole, EvidenceKind } from '@/types/console';
import { formatDateTime } from './format';
import SignalChart from './SignalChart.vue';
import TemperatureChart from './TemperatureChart.vue';

const props = defineProps<{ shipment: ShipmentConsole }>();

const selected = ref<number>(1);

watch(
    () => props.shipment.id,
    () => {
        selected.value = props.shipment.reasons.find((r) => r.signal)?.n ?? 1;
    },
    { immediate: true },
);

const selectedReason = computed(() =>
    props.shipment.reasons.find((r) => r.n === selected.value),
);

const signal = computed(() => {
    const key = selectedReason.value?.signal;

    return key && key !== 'temperature' ? props.shipment.signals[key] : null;
});

const kindStyles: Record<EvidenceKind, { label: string; badge: string }> = {
    real: {
        label: 'REAL',
        badge: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300',
    },
    simulated: {
        label: 'SIMULATED',
        badge: 'bg-violet-100 text-violet-800 dark:bg-violet-950 dark:text-violet-300',
    },
    unverified: {
        label: 'NOT VERIFIED',
        badge: 'bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300',
    },
};
</script>

<template>
    <section class="grid gap-6 rounded-xl border bg-card p-5 lg:grid-cols-2">
        <div class="flex flex-col gap-4">
            <div>
                <h3 class="text-lg font-semibold">Why this recommendation</h3>
                <p class="mt-1 text-sm leading-relaxed text-muted-foreground">
                    {{ shipment.recommendation.summary }}
                </p>
            </div>

            <ol class="flex flex-col gap-2">
                <li v-for="reason in shipment.reasons" :key="reason.n">
                    <button
                        type="button"
                        class="w-full rounded-lg border p-3 text-left transition-colors hover:bg-accent"
                        :class="[
                            selected === reason.n
                                ? 'border-sky-600 bg-sky-50 dark:bg-sky-950/40'
                                : '',
                            reason.kind === 'unverified'
                                ? 'border-dashed border-red-500/60'
                                : '',
                        ]"
                        @click="selected = reason.n"
                    >
                        <div class="flex items-start gap-3">
                            <span class="font-mono text-sm font-bold">{{
                                reason.n
                            }}</span>
                            <div class="flex-1">
                                <div class="text-sm font-medium">
                                    {{ reason.text }}
                                </div>
                                <div
                                    class="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground"
                                >
                                    <span
                                        class="rounded px-1.5 py-0.5 font-semibold"
                                        :class="kindStyles[reason.kind].badge"
                                    >
                                        {{ kindStyles[reason.kind].label }}
                                    </span>
                                    <span>{{ reason.source }}</span>
                                    <span
                                        >·
                                        {{
                                            formatDateTime(
                                                reason.at,
                                                shipment.timezone,
                                            )
                                        }}</span
                                    >
                                </div>
                            </div>
                        </div>
                    </button>
                </li>
            </ol>
        </div>

        <div class="flex flex-col gap-4">
            <div>
                <div class="text-sm text-muted-foreground">
                    Signal for <b class="text-foreground">{{ selected }}</b>
                    <template v-if="signal"> · {{ signal.title }}</template>
                    <template
                        v-else-if="selectedReason?.signal === 'temperature'"
                    >
                        · Product temperature</template
                    >
                </div>
                <div class="mt-2 rounded-lg border p-2">
                    <SignalChart v-if="signal" :signal="signal" />
                    <TemperatureChart
                        v-else-if="selectedReason?.signal === 'temperature'"
                        :points="shipment.temperature.points"
                        :exposures="shipment.temperature.exposures"
                        :band="shipment.temperature.band"
                        :now="shipment.asOf"
                        :timezone="shipment.timezone"
                    />
                    <div
                        v-else
                        class="flex h-40 items-center justify-center text-sm text-muted-foreground"
                    >
                        {{ selectedReason?.source }}
                    </div>
                </div>
            </div>

            <div>
                <div class="text-sm font-semibold">Would change if</div>
                <ul class="mt-1 list-disc pl-5 text-sm text-muted-foreground">
                    <li v-for="item in shipment.wouldChangeIf" :key="item">
                        {{ item }}
                    </li>
                </ul>
            </div>
        </div>
    </section>
</template>
