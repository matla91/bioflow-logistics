<script setup lang="ts">
import { Head, Link, router, useForm, usePage } from '@inertiajs/vue3';
import { computed, reactive, watch } from 'vue';
import ShipmentDecisionController from '@/actions/App/Http/Controllers/ShipmentDecisionController';
import AnswerCard from '@/components/console/AnswerCard.vue';
import DecisionLog from '@/components/console/DecisionLog.vue';
import EvidenceLedger from '@/components/console/EvidenceLedger.vue';
import {
    formatCountdown,
    formatTime,
    roleLabels,
} from '@/components/console/format';
import JourneyRail from '@/components/console/JourneyRail.vue';
import OptionsBoard from '@/components/console/OptionsBoard.vue';
import VerdictDialog from '@/components/console/VerdictDialog.vue';
import { index } from '@/routes/shipments';
import type { ActionKey, ShipmentConsole } from '@/types/console';

const props = defineProps<{ shipment: ShipmentConsole }>();

defineOptions({
    layout: {
        breadcrumbs: [{ title: 'Shipments', href: index() }],
    },
});

const page = usePage();
const role = computed(() => page.props.auth.user.role);
const decided = computed(() => props.shipment.status === 'closed');

const dialog = reactive<{
    open: boolean;
    verdict: 'APPROVE' | 'OVERRIDE';
    action: ActionKey;
}>({
    open: false,
    verdict: 'APPROVE',
    action: 'RUN_AS_PLANNED',
});

const form = useForm({
    assessment_id: props.shipment.assessmentId,
    verdict: 'APPROVE' as 'APPROVE' | 'OVERRIDE',
    action: props.shipment.recommendation.action,
    reason: '',
});

const formError = computed(() => {
    const errors: Record<string, string | undefined> = form.errors;

    return (
        errors.decision ??
        errors.reason ??
        errors.action ??
        errors.assessment_id
    );
});

watch(
    () => dialog.open,
    (open) => {
        if (open) {
            form.clearErrors();
        }
    },
);

function openApprove(): void {
    Object.assign(dialog, {
        open: true,
        verdict: 'APPROVE',
        action: props.shipment.recommendation.action,
    });
}

function openOverride(action: ActionKey): void {
    Object.assign(dialog, { open: true, verdict: 'OVERRIDE', action });
}

function record({
    action,
    reason,
}: {
    action: ActionKey;
    reason: string;
}): void {
    form.assessment_id = props.shipment.assessmentId;
    form.verdict = dialog.verdict;
    form.action = action;
    form.reason = reason;
    form.submit(ShipmentDecisionController.store(props.shipment.id), {
        preserveScroll: true,
        onSuccess: () => {
            dialog.open = false;
        },
    });
}

function reopen(): void {
    router.visit(ShipmentDecisionController.destroy(props.shipment.id), {
        preserveScroll: true,
    });
}
</script>

<template>
    <div class="mx-auto flex w-full max-w-7xl flex-1 flex-col gap-5 p-4 md:p-6">
        <Head :title="`Lot ${shipment.lot}`" />

        <header class="flex flex-wrap items-center justify-between gap-3">
            <div class="flex flex-wrap items-center gap-2 text-sm">
                <Link
                    :href="index()"
                    class="text-muted-foreground hover:text-foreground"
                >
                    ← Shipments
                </Link>
                <span class="font-semibold"
                    >Rhine → {{ shipment.reactor }} · lot
                    {{ shipment.lot }}</span
                >
                <span
                    v-if="shipment.simulated"
                    class="rounded border-2 border-dashed border-foreground/60 px-2 py-0.5 text-xs font-semibold"
                >
                    SIMULATED SHIPMENT
                </span>
                <span
                    v-if="shipment.scenario"
                    class="rounded bg-sky-100 px-2 py-0.5 text-xs font-semibold text-sky-800 dark:bg-sky-950 dark:text-sky-300"
                >
                    Demo scene
                </span>
            </div>
            <span
                class="rounded-lg border px-2.5 py-1 text-sm text-muted-foreground"
            >
                Signed in as
                <b class="text-foreground">{{ roleLabels[role] }}</b>
            </span>
        </header>

        <div class="flex flex-wrap items-baseline justify-between gap-2">
            <h1 class="text-2xl font-bold tracking-tight">
                Batch charges {{ shipment.reactor }} at
                {{ formatTime(shipment.chargeAt, shipment.timezone) }} Basel
            </h1>
            <div class="text-sm text-muted-foreground">
                in
                <b class="text-2xl text-foreground">{{
                    formatCountdown(shipment.asOf, shipment.chargeAt)
                }}</b>
                · as of {{ formatTime(shipment.asOf, shipment.timezone) }}
            </div>
        </div>

        <div class="grid gap-4 sm:grid-cols-2">
            <AnswerCard :answer="shipment.answers.arrival" />
            <AnswerCard :answer="shipment.answers.quality" />
        </div>

        <OptionsBoard
            :shipment="shipment"
            :acting-as="role"
            :decided="decided"
            @approve="openApprove"
            @choose="openOverride"
        />

        <EvidenceLedger :shipment="shipment" />

        <JourneyRail :shipment="shipment" />

        <div class="flex flex-col gap-2">
            <DecisionLog
                :entries="shipment.log"
                :timezone="shipment.timezone"
            />
            <button
                v-if="decided && shipment.scenario"
                type="button"
                class="self-end text-xs text-muted-foreground underline-offset-2 hover:underline"
                @click="reopen"
            >
                Reopen demo scene
            </button>
        </div>

        <VerdictDialog
            v-model:open="dialog.open"
            :verdict="dialog.verdict"
            :action="dialog.action"
            :options="shipment.options"
            :error="formError"
            :processing="form.processing"
            @confirm="record"
        />
    </div>
</template>
