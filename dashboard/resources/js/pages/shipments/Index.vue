<script setup lang="ts">
import { Head, Link, usePage } from '@inertiajs/vue3';
import { computed, ref } from 'vue';
import {
    actionLabels,
    formatDateTime,
    roleLabels,
} from '@/components/console/format';
import { index, show } from '@/routes/shipments';
import type {
    ShipmentListItem,
    ShipmentStatus,
    Verdict,
} from '@/types/console';

const props = defineProps<{
    upcoming: ShipmentListItem[];
    history: ShipmentListItem[];
}>();

defineOptions({
    layout: {
        breadcrumbs: [{ title: 'Shipments', href: index() }],
    },
});

const page = usePage();
const role = computed(() => page.props.auth.user.role);

const tab = ref<'upcoming' | 'history'>('upcoming');
const rows = computed(() =>
    tab.value === 'upcoming' ? props.upcoming : props.history,
);

const statusLabels: Record<ShipmentStatus, string> = {
    in_transit: 'In transit',
    suspended: 'Suspended',
    arrived: 'Arrived',
    closed: 'Closed',
};

const verdictDot: Record<Verdict, string> = {
    yes: 'bg-emerald-500',
    no: 'bg-red-500',
    at_risk: 'bg-amber-500',
};
</script>

<template>
    <div class="mx-auto flex w-full max-w-7xl flex-1 flex-col gap-5 p-4 md:p-6">
        <Head title="Shipments" />

        <div class="flex flex-wrap items-end justify-between gap-3">
            <div>
                <h1 class="text-2xl font-bold tracking-tight">Shipments</h1>
                <p class="text-sm text-muted-foreground">
                    Lots heading to R2 and the decisions made on them.
                </p>
            </div>
            <div class="flex rounded-lg border p-0.5 text-sm" role="tablist">
                <button
                    v-for="t in ['upcoming', 'history'] as const"
                    :key="t"
                    type="button"
                    role="tab"
                    :aria-selected="tab === t"
                    class="rounded-md px-3 py-1"
                    :class="
                        tab === t
                            ? 'bg-foreground text-background'
                            : 'text-muted-foreground hover:text-foreground'
                    "
                    @click="tab = t"
                >
                    {{ t === 'upcoming' ? 'Upcoming' : 'History' }}
                    <span class="ml-1 opacity-60">{{
                        t === 'upcoming' ? upcoming.length : history.length
                    }}</span>
                </button>
            </div>
        </div>

        <div class="overflow-x-auto rounded-xl border">
            <table class="w-full text-left text-sm">
                <thead class="bg-muted/50 text-xs text-muted-foreground">
                    <tr>
                        <th class="px-4 py-2 font-medium">Charge</th>
                        <th class="px-4 py-2 font-medium">Lot</th>
                        <th class="px-4 py-2 font-medium">Here? · Good?</th>
                        <th class="px-4 py-2 font-medium">Recommended</th>
                        <th class="px-4 py-2 font-medium">
                            {{ tab === 'upcoming' ? 'Status' : 'Decision' }}
                        </th>
                        <th class="px-4 py-2" />
                    </tr>
                </thead>
                <tbody class="divide-y">
                    <tr
                        v-for="item in rows"
                        :key="item.id"
                        class="align-top"
                        :class="
                            tab === 'upcoming' && item.approverRole === role
                                ? 'bg-sky-50/60 dark:bg-sky-950/20'
                                : ''
                        "
                    >
                        <td class="px-4 py-3 whitespace-nowrap">
                            {{ formatDateTime(item.chargeAt, item.timezone) }}
                            <div class="text-xs text-muted-foreground">
                                {{ item.reactor }}
                            </div>
                        </td>
                        <td class="px-4 py-3 whitespace-nowrap">
                            <span class="font-mono">{{ item.lot }}</span>
                            <div
                                v-if="item.scenario"
                                class="text-xs text-sky-700 dark:text-sky-400"
                            >
                                Demo scene
                            </div>
                        </td>
                        <td class="px-4 py-3">
                            <div v-if="item.answers" class="flex gap-3">
                                <span
                                    v-for="answer in [
                                        item.answers.arrival,
                                        item.answers.quality,
                                    ]"
                                    :key="answer.question"
                                    class="flex items-center gap-1.5"
                                    :title="`${answer.question} ${answer.detail}`"
                                >
                                    <span
                                        class="size-2.5 rounded-full"
                                        :class="verdictDot[answer.verdict]"
                                    />
                                    {{
                                        answer.verdict === 'at_risk'
                                            ? 'risk'
                                            : answer.verdict
                                    }}
                                </span>
                            </div>
                        </td>
                        <td class="px-4 py-3 whitespace-nowrap">
                            <template v-if="item.recommendedAction">
                                {{ actionLabels[item.recommendedAction] }}
                                <div
                                    v-if="
                                        tab === 'upcoming' && item.approverRole
                                    "
                                    class="text-xs"
                                    :class="
                                        item.approverRole === role
                                            ? 'font-semibold text-sky-700 dark:text-sky-400'
                                            : 'text-muted-foreground'
                                    "
                                >
                                    {{
                                        item.approverRole === role
                                            ? 'Needs your approval'
                                            : `Needs ${roleLabels[item.approverRole]}`
                                    }}
                                </div>
                            </template>
                        </td>
                        <td class="px-4 py-3">
                            <template v-if="tab === 'upcoming'">
                                <span
                                    class="rounded px-1.5 py-0.5 text-xs font-semibold"
                                    :class="
                                        item.status === 'suspended'
                                            ? 'bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300'
                                            : 'bg-muted'
                                    "
                                >
                                    {{ statusLabels[item.status] }}
                                </span>
                                <div class="mt-1 text-xs text-muted-foreground">
                                    {{
                                        item.currentSegment.replaceAll('_', ' ')
                                    }}
                                    ·
                                    {{ Math.round(item.routeProgress * 100) }}%
                                </div>
                            </template>
                            <template v-else-if="item.decision">
                                <span
                                    class="rounded px-1.5 py-0.5 text-xs font-semibold"
                                    :class="
                                        item.decision.verdict === 'APPROVE'
                                            ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300'
                                            : 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300'
                                    "
                                >
                                    {{
                                        item.decision.verdict === 'APPROVE'
                                            ? 'Approved'
                                            : `Overrode → ${actionLabels[item.decision.action]}`
                                    }}
                                </span>
                                <div class="mt-1 text-xs text-muted-foreground">
                                    {{ item.decision.by }} ·
                                    {{ roleLabels[item.decision.role] }}
                                </div>
                                <div
                                    class="mt-0.5 max-w-xs text-xs text-muted-foreground"
                                >
                                    “{{ item.decision.reason }}”
                                </div>
                            </template>
                        </td>
                        <td class="px-4 py-3 text-right">
                            <Link
                                :href="show(item.id)"
                                class="text-sm font-medium text-sky-700 hover:underline dark:text-sky-400"
                            >
                                Open
                            </Link>
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>
</template>
