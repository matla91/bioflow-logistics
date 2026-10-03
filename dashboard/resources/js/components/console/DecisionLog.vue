<script setup lang="ts">
import type { ShipmentDecision } from '@/types/console';
import { actionLabels, formatDateTime, roleLabels } from './format';

defineProps<{ entries: ShipmentDecision[]; timezone: string }>();
</script>

<template>
    <section class="flex flex-col gap-3 rounded-xl border bg-card p-5">
        <h3 class="text-lg font-semibold">Decision log</h3>
        <p v-if="entries.length === 0" class="text-sm text-muted-foreground">
            No decisions recorded for this lot yet.
        </p>
        <ul v-else class="flex flex-col divide-y">
            <li
                v-for="entry in entries"
                :key="entry.decidedAt"
                class="flex flex-wrap items-baseline gap-x-3 gap-y-1 py-2 text-sm"
            >
                <span class="text-muted-foreground">{{
                    formatDateTime(entry.decidedAt, timezone)
                }}</span>
                <span
                    class="rounded px-1.5 py-0.5 text-xs font-semibold"
                    :class="
                        entry.verdict === 'APPROVE'
                            ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300'
                            : 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300'
                    "
                >
                    {{ entry.verdict }}
                </span>
                <b>{{ actionLabels[entry.action] }}</b>
                <span class="text-muted-foreground"
                    >by {{ entry.by }} · {{ roleLabels[entry.role] }}</span
                >
                <span class="basis-full text-muted-foreground"
                    >“{{ entry.reason }}”</span
                >
            </li>
        </ul>
    </section>
</template>
