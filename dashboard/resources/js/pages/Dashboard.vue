<script setup lang="ts">
import { Head, Link } from '@inertiajs/vue3';
import { computed } from 'vue';
import {
    actionLabels,
    formatDateTime,
    roleLabels,
} from '@/components/console/format';
import { dashboard } from '@/routes';
import { index, show } from '@/routes/shipments';
import type {
    ActionKey,
    ShipmentListItem,
    ShipmentOverview,
} from '@/types/console';

const props = defineProps<{ overview: ShipmentOverview }>();

defineOptions({
    layout: {
        breadcrumbs: [{ title: 'Overview', href: dashboard() }],
    },
});

const share = (count: number) =>
    props.overview.recent.decided === 0
        ? '—'
        : `${Math.round((count / props.overview.recent.decided) * 100)}%`;

const openTiles = computed(() => [
    {
        label: 'Need your approval',
        value: props.overview.open.needsYou,
        emphasis: props.overview.open.needsYou > 0,
    },
    { label: 'Open shipments', value: props.overview.open.open },
    { label: 'At risk', value: props.overview.open.atRisk },
    { label: 'Suspended', value: props.overview.open.suspended },
]);

const recentTiles = computed(() => [
    { label: 'Decided', value: String(props.overview.recent.decided) },
    { label: 'Arrived on time', value: share(props.overview.recent.onTime) },
    {
        label: 'Within temperature budget',
        value: share(props.overview.recent.withinBudget),
    },
    { label: 'Overrides', value: String(props.overview.recent.overrides) },
]);

const actionBars = computed(() => {
    const entries = Object.entries(props.overview.decisionsByAction) as [
        ActionKey,
        number,
    ][];
    const max = Math.max(1, ...entries.map(([, count]) => count));

    return entries.map(([action, count]) => ({
        action,
        count,
        width: `${(count / max) * 100}%`,
    }));
});

function nextLabel(item: ShipmentListItem): string {
    return item.recommendedAction ? actionLabels[item.recommendedAction] : '—';
}
</script>

<template>
    <div class="mx-auto flex w-full max-w-7xl flex-1 flex-col gap-6 p-4 md:p-6">
        <Head title="Overview" />

        <div>
            <h1 class="text-2xl font-bold tracking-tight">Overview</h1>
            <p class="text-sm text-muted-foreground">
                All shipments heading to R2 and recent decisions.
            </p>
        </div>

        <section class="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <div
                v-for="tile in openTiles"
                :key="tile.label"
                class="rounded-xl border bg-card p-4"
                :class="tile.emphasis ? 'border-sky-600/60' : ''"
            >
                <div class="text-sm text-muted-foreground">
                    {{ tile.label }}
                </div>
                <div
                    class="text-3xl font-bold tabular-nums"
                    :class="
                        tile.emphasis ? 'text-sky-700 dark:text-sky-400' : ''
                    "
                >
                    {{ tile.value }}
                </div>
            </div>
        </section>

        <div class="grid gap-6 lg:grid-cols-2">
            <section class="flex flex-col gap-3 rounded-xl border bg-card p-5">
                <h2 class="text-lg font-semibold">Needs your approval</h2>
                <p
                    v-if="overview.needsYou.length === 0"
                    class="text-sm text-muted-foreground"
                >
                    Nothing waiting for you.
                </p>
                <ul v-else class="flex flex-col divide-y">
                    <li v-for="item in overview.needsYou" :key="item.id">
                        <Link
                            :href="show(item.id)"
                            class="flex items-baseline justify-between gap-3 py-2 text-sm hover:text-sky-700 dark:hover:text-sky-400"
                        >
                            <span>
                                <span class="font-mono">{{ item.lot }}</span>
                                · {{ nextLabel(item) }}
                            </span>
                            <span class="text-muted-foreground">{{
                                formatDateTime(item.chargeAt, item.timezone)
                            }}</span>
                        </Link>
                    </li>
                </ul>
            </section>

            <section class="flex flex-col gap-3 rounded-xl border bg-card p-5">
                <div class="flex items-baseline justify-between">
                    <h2 class="text-lg font-semibold">Next charges</h2>
                    <Link
                        :href="index()"
                        class="text-sm text-sky-700 hover:underline dark:text-sky-400"
                        >All shipments</Link
                    >
                </div>
                <ul class="flex flex-col divide-y">
                    <li v-for="item in overview.nextCharges" :key="item.id">
                        <Link
                            :href="show(item.id)"
                            class="flex items-baseline justify-between gap-3 py-2 text-sm hover:text-sky-700 dark:hover:text-sky-400"
                        >
                            <span>
                                <span class="font-mono">{{ item.lot }}</span>
                                · {{ nextLabel(item) }}
                                <span
                                    v-if="item.approverRole"
                                    class="text-xs text-muted-foreground"
                                >
                                    ({{ roleLabels[item.approverRole] }})
                                </span>
                            </span>
                            <span class="text-muted-foreground">{{
                                formatDateTime(item.chargeAt, item.timezone)
                            }}</span>
                        </Link>
                    </li>
                </ul>
            </section>
        </div>

        <section class="flex flex-col gap-4 rounded-xl border bg-card p-5">
            <h2 class="text-lg font-semibold">
                Last {{ overview.recent.days }} days
            </h2>
            <div class="grid grid-cols-2 gap-3 lg:grid-cols-4">
                <div v-for="tile in recentTiles" :key="tile.label">
                    <div class="text-sm text-muted-foreground">
                        {{ tile.label }}
                    </div>
                    <div class="text-2xl font-bold tabular-nums">
                        {{ tile.value }}
                    </div>
                </div>
            </div>

            <div>
                <h3 class="mb-2 text-sm font-medium">Decisions by action</h3>
                <ul class="flex flex-col gap-2">
                    <li
                        v-for="bar in actionBars"
                        :key="bar.action"
                        class="grid grid-cols-[8rem_1fr_2rem] items-center gap-3 text-sm"
                        :title="`${actionLabels[bar.action]}: ${bar.count}`"
                    >
                        <span class="text-muted-foreground">{{
                            actionLabels[bar.action]
                        }}</span>
                        <span class="h-3 rounded-r bg-muted">
                            <span
                                class="block h-full rounded-r bg-sky-600 dark:bg-sky-500"
                                :style="{ width: bar.width }"
                            />
                        </span>
                        <span class="text-right tabular-nums">{{
                            bar.count
                        }}</span>
                    </li>
                </ul>
            </div>
        </section>
    </div>
</template>
