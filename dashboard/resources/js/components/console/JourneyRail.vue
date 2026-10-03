<script setup lang="ts">
import { computed } from 'vue';
import type { ShipmentConsole } from '@/types/console';
import { formatPercent } from './format';
import TemperatureChart from './TemperatureChart.vue';

const props = defineProps<{ shipment: ShipmentConsole }>();

const W = 600;
const X0 = 16;
const X1 = W - 16;
const x = (position: number) => X0 + position * (X1 - X0);

const progressX = computed(() => x(props.shipment.journey.progress));

const budgetPct = computed(() =>
    Math.min(100, props.shipment.budget.usedFraction * 100),
);

const budgetTone = computed(() => {
    const used = props.shipment.budget.usedFraction;

    if (used > 1) {
        return 'bg-red-600 dark:bg-red-500';
    }

    return used >= 0.8 ? 'bg-amber-500' : 'bg-emerald-600 dark:bg-emerald-500';
});
</script>

<template>
    <section class="flex flex-col gap-4 rounded-xl border bg-card p-5">
        <h3 class="text-lg font-semibold">Shipment journey</h3>

        <svg
            :viewBox="`0 0 ${W} 72`"
            class="w-full"
            role="img"
            aria-label="Route progress"
        >
            <line
                :x1="X0"
                :x2="X1"
                y1="30"
                y2="30"
                stroke-width="2"
                stroke-dasharray="6 6"
                class="stroke-muted-foreground/50"
            />
            <line
                :x1="X0"
                :x2="progressX"
                y1="30"
                y2="30"
                stroke-width="3"
                class="stroke-foreground"
            />
            <g v-for="stop in shipment.journey.stops" :key="stop.id">
                <circle
                    :cx="x(stop.position)"
                    cy="30"
                    :r="
                        stop.state === 'blocked' || stop.state === 'current'
                            ? 9
                            : 6
                    "
                    stroke-width="2"
                    :class="{
                        'fill-foreground stroke-foreground':
                            stop.state === 'done',
                        'fill-red-600 stroke-red-600 dark:fill-red-500':
                            stop.state === 'blocked',
                        'fill-sky-600 stroke-sky-600 dark:fill-sky-500':
                            stop.state === 'current',
                        'fill-background stroke-muted-foreground':
                            stop.state === 'pending',
                    }"
                />
                <text
                    :x="x(stop.position)"
                    y="60"
                    :text-anchor="
                        stop.position === 0
                            ? 'start'
                            : stop.position === 1
                              ? 'end'
                              : 'middle'
                    "
                    class="text-[12px]"
                    :class="
                        stop.state === 'blocked'
                            ? 'fill-red-600 font-semibold dark:fill-red-400'
                            : 'fill-foreground'
                    "
                >
                    {{
                        stop.state === 'blocked'
                            ? `stuck · ${stop.label}`
                            : stop.label
                    }}
                </text>
            </g>
        </svg>

        <div>
            <div class="text-sm text-muted-foreground">
                Product temperature · {{ shipment.temperature.band[0] }}–{{
                    shipment.temperature.band[1]
                }}
                °C band · amber = exposed handover
            </div>
            <div class="mt-2 rounded-lg border p-2">
                <TemperatureChart
                    :points="shipment.temperature.points"
                    :exposures="shipment.temperature.exposures"
                    :band="shipment.temperature.band"
                    :now="shipment.asOf"
                    :timezone="shipment.timezone"
                />
            </div>
        </div>

        <div class="flex items-center gap-3 text-sm">
            <span class="shrink-0">Excursion budget</span>
            <div class="h-3 flex-1 overflow-hidden rounded-full bg-muted">
                <div
                    class="h-full rounded-full"
                    :class="budgetTone"
                    :style="{ width: `${budgetPct}%` }"
                />
            </div>
            <span class="w-40 shrink-0 text-right">
                {{ formatPercent(shipment.budget.usedFraction) }} of
                {{ shipment.budget.budgetMin }} min
            </span>
        </div>
    </section>
</template>
