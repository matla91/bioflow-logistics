<script setup lang="ts">
import { computed } from 'vue';
import type { Signal } from '@/types/console';

const props = defineProps<{ signal: Signal }>();

const W = 360;
const H = 170;
const PAD = { top: 12, right: 10, bottom: 30, left: 34 };

const domain = computed(() => {
    const values = props.signal.points.map((p) => p.v);
    const threshold = props.signal.threshold?.v;
    const lo = Math.min(...values, threshold ?? Infinity);
    const hi = Math.max(...values, threshold ?? -Infinity);
    const pad = (hi - lo) * 0.1 || 1;

    return { v0: lo - pad, v1: hi + pad, n: props.signal.points.length };
});

const x = (i: number) =>
    PAD.left +
    (i / Math.max(1, domain.value.n - 1)) * (W - PAD.left - PAD.right);

const y = (v: number) => {
    const { v0, v1 } = domain.value;

    return PAD.top + (1 - (v - v0) / (v1 - v0)) * (H - PAD.top - PAD.bottom);
};

const line = computed(() =>
    props.signal.points
        .map((p, i) => `${x(i).toFixed(1)},${y(p.v).toFixed(1)}`)
        .join(' '),
);

const last = computed(() => {
    const i = props.signal.points.length - 1;

    return {
        cx: x(i),
        cy: y(props.signal.points[i].v),
        v: props.signal.points[i].v,
    };
});
</script>

<template>
    <svg
        :viewBox="`0 0 ${W} ${H}`"
        class="w-full"
        role="img"
        :aria-label="signal.title"
    >
        <g v-if="signal.threshold">
            <line
                :x1="PAD.left"
                :x2="W - PAD.right"
                :y1="y(signal.threshold.v)"
                :y2="y(signal.threshold.v)"
                stroke-dasharray="5 4"
                class="stroke-red-600 dark:stroke-red-400"
            />
            <line
                :x1="PAD.left"
                :x2="PAD.left + 18"
                :y1="H - 8"
                :y2="H - 8"
                stroke-dasharray="5 4"
                class="stroke-red-600 dark:stroke-red-400"
            />
            <text
                :x="PAD.left + 24"
                :y="H - 4"
                class="fill-red-600 text-[10px] dark:fill-red-400"
            >
                {{ signal.threshold.label }} · {{ signal.threshold.v }}
                {{ signal.unit }}
            </text>
        </g>
        <text :x="2" :y="PAD.top + 8" class="fill-muted-foreground text-[10px]">
            {{ Math.round(domain.v1) }}
        </text>
        <text
            :x="2"
            :y="H - PAD.bottom"
            class="fill-muted-foreground text-[10px]"
        >
            {{ Math.round(domain.v0) }}
        </text>
        <polyline
            :points="line"
            fill="none"
            stroke-width="2"
            stroke-linejoin="round"
            class="stroke-foreground"
        />
        <circle
            :cx="last.cx"
            :cy="last.cy"
            r="5"
            class="fill-sky-600 dark:fill-sky-400"
        />
        <text
            :x="last.cx - 6"
            :y="last.cy - 9"
            text-anchor="end"
            class="fill-sky-700 text-[11px] font-semibold dark:fill-sky-300"
        >
            {{ last.v }} {{ signal.unit }}
        </text>
    </svg>
</template>
