<script setup lang="ts">
import { computed } from 'vue';
import { Button } from '@/components/ui/button';
import type { ActionKey, ShipmentConsole, Role } from '@/types/console';
import { formatDelay, formatPercent, roleLabels } from './format';

const props = defineProps<{
    shipment: ShipmentConsole;
    actingAs: Role;
    decided: boolean;
}>();

const emit = defineEmits<{ approve: []; choose: [action: ActionKey] }>();

const approver = computed(() => props.shipment.recommendation.approver);
const canApprove = computed(() => props.actingAs === approver.value);
</script>

<template>
    <section
        class="flex flex-col gap-4 rounded-xl border-2 border-sky-600/60 bg-card p-5"
    >
        <div class="flex flex-wrap items-end justify-between gap-2">
            <div>
                <div
                    class="text-xs font-semibold tracking-wide text-sky-700 uppercase dark:text-sky-400"
                >
                    Recommendation · {{ roleLabels[approver] }} decides
                </div>
                <h2
                    class="mt-1 text-3xl leading-tight font-bold tracking-tight"
                >
                    {{ shipment.recommendation.title }}
                </h2>
                <p class="mt-1 text-sm text-muted-foreground">
                    {{ shipment.recommendation.glance }}
                </p>
            </div>
            <span class="text-sm text-muted-foreground">
                2,000 simulated journeys per action
            </span>
        </div>

        <div class="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            <div
                v-for="option in shipment.options"
                :key="option.action"
                class="flex flex-col gap-1.5 rounded-xl border-2 p-3 text-sm"
                :class="
                    option.recommended
                        ? 'col-span-2 border-sky-600 bg-sky-50 sm:col-span-1 dark:bg-sky-950/40'
                        : 'text-muted-foreground'
                "
            >
                <b
                    class="text-base"
                    :class="
                        option.recommended
                            ? 'text-sky-700 dark:text-sky-400'
                            : 'text-foreground'
                    "
                >
                    <span v-if="option.recommended">★ </span>{{ option.label }}
                </b>
                <span>miss slot {{ formatPercent(option.pMissSlot) }}</span>
                <span>delay {{ formatDelay(option.expDelayMin) }}</span>
                <span>excursion {{ formatPercent(option.pExcursion) }}</span>
                <span>stock → {{ option.stockAfter }}</span>
                <span
                    class="mt-1 text-xs"
                    :class="
                        option.recommended
                            ? 'text-sky-700 dark:text-sky-400'
                            : ''
                    "
                >
                    {{ option.recommended ? '' : '✕ ' }}{{ option.note }}
                </span>
                <div class="mt-auto flex flex-col gap-1 pt-2">
                    <template v-if="option.recommended">
                        <Button
                            class="w-full bg-sky-600 text-white hover:bg-sky-700 dark:bg-sky-500 dark:hover:bg-sky-600"
                            :disabled="!canApprove || decided"
                            @click="emit('approve')"
                        >
                            {{ decided ? 'Decision recorded' : 'Approve' }}
                        </Button>
                        <span
                            v-if="!canApprove && !decided"
                            class="text-xs text-amber-700 dark:text-amber-400"
                        >
                            Needs {{ roleLabels[approver] }} approval
                        </span>
                    </template>
                    <Button
                        v-else
                        variant="outline"
                        class="w-full"
                        :disabled="decided"
                        @click="emit('choose', option.action)"
                    >
                        Override
                    </Button>
                </div>
            </div>
        </div>

        <p class="text-xs text-muted-foreground">
            Choosing another option overrides the recommendation and needs a
            reason.
        </p>
    </section>
</template>
