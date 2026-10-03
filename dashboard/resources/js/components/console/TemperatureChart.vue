<script setup lang="ts">
import { computed } from 'vue';
import type { Exposure, TemperaturePoint } from '@/types/console';
import { formatTime } from './format';

const props = defineProps<{
    points: TemperaturePoint[];
    exposures: Exposure[];
    band: [number, number];
    now: string;
    timezone: string;
}>();

const W = 600;
const H = 160;
const PAD = { top: 12, right: 8, bottom: 22, left: 28 };

const domain = computed(() => {
    const times = props.points.map((p) => new Date(p.at).getTime());
    const temps = props.points.map((p) => p.c);

    return {
        t0: Math.min(...times),
        t1: Math.max(...times),
        c0: Math.min(0, ...temps) - 1,
        c1: Math.max(props.band[1] + 4, ...temps) + 1,
    };
});

const x = (iso: string) => {
    const { t0, t1 } = domain.value;

    return (
        PAD.left +
        ((new Date(iso).getTime() - t0) / (t1 - t0)) *
            (W - PAD.left - PAD.right)
    );
};

const y = (c: number) => {
    const { c0, c1 } = domain.value;

    return PAD.top + (1 - (c - c0) / (c1 - c0)) * (H - PAD.top - PAD.bottom);
};

const line = computed(() =>
    props.points
        .map((p) => `${x(p.at).toFixed(1)},${y(p.c).toFixed(1)}`)
        .join(' '),
);

const outOfBand = computed(() =>
    props.points.filter((p) => p.c > props.band[1] || p.c < props.band[0]),
);

const ticks = computed(() => {
    const { t0, t1 } = domain.value;

    return [0, 0.25, 0.5, 0.75, 1].map((f) =>
        new Date(t0 + f * (t1 - t0)).toISOString(),
    );
});

const nowX = computed(() => {
    const t = new Date(props.now).getTime();
    const { t0, t1 } = domain.value;

    return t >= t0 && t <= t1 ? x(props.now) : null;
});
</script>

<template>
    <svg
        :viewBox="`0 0 ${W} ${H}`"
        class="w-full"
        role="img"
        :aria-label="`Product temperature against the ${band[0]}–${band[1]} °C band`"
    >
        <rect
            :x="PAD.left"
            :y="y(band[1])"
            :width="W - PAD.left - PAD.right"
            :height="y(band[0]) - y(band[1])"
            class="fill-sky-100 dark:fill-sky-950/60"
        />
        <g v-for="e in exposures" :key="e.from">
            <rect
                :x="x(e.from)"
                :y="PAD.top"
                :width="Math.max(3, x(e.to) - x(e.from))"
                :height="H - PAD.top - PAD.bottom"
                class="fill-amber-200/70 dark:fill-amber-500/25"
            />
            <text
                :x="x(e.from) + 3"
                :y="PAD.top + 10"
                class="fill-amber-700 text-[10px] dark:fill-amber-300"
            >
                {{ e.label }}
            </text>
        </g>
        <text
            :x="2"
            :y="y(band[1]) + 4"
            class="fill-muted-foreground text-[10px]"
        >
            {{ band[1] }}°
        </text>
        <text
            :x="2"
            :y="y(band[0]) + 4"
            class="fill-muted-foreground text-[10px]"
        >
            {{ band[0] }}°
        </text>
        <polyline
            :points="line"
            fill="none"
            stroke-width="2"
            stroke-linejoin="round"
            class="stroke-foreground"
        />
        <circle
            v-for="p in outOfBand"
            :key="p.at"
            :cx="x(p.at)"
            :cy="y(p.c)"
            r="2.5"
            class="fill-red-600 dark:fill-red-400"
        />
        <g v-if="nowX !== null">
            <line
                :x1="nowX"
                :x2="nowX"
                :y1="PAD.top"
                :y2="H - PAD.bottom"
                stroke-width="1.5"
                class="stroke-red-600 dark:stroke-red-400"
            />
            <text
                :x="nowX + 4"
                :y="H - PAD.bottom - 4"
                class="fill-red-600 text-[10px] dark:fill-red-400"
            >
                now
            </text>
        </g>
        <text
            v-for="(t, i) in ticks"
            :key="t"
            :x="x(t)"
            :y="H - 6"
            :text-anchor="
                i === 0 ? 'start' : i === ticks.length - 1 ? 'end' : 'middle'
            "
            class="fill-muted-foreground text-[10px]"
        >
            {{ formatTime(t, timezone) }}
        </text>
    </svg>
</template>
