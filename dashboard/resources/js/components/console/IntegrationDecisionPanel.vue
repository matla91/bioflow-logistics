<script setup lang="ts">
import { useForm, usePage } from '@inertiajs/vue3';
import { computed, reactive } from 'vue';
import IntegrationDecisionController from '@/actions/App/Http/Controllers/IntegrationDecisionController';
import { Button } from '@/components/ui/button';
import { formatBaselTime } from '@/lib/batch-display';
import {
    integrationDecisionOptions,
    isNamedIntegrationDemo,
} from '@/lib/integration-decisions';
import type { ActionKey, HumanDecision } from '@/types/console';
import type { StoredLogisticsAssessment } from '@/types/integration';
import type {
    IntegrationActionRoles,
    IntegrationDemoShipments,
} from '@/types/integration-decisions';
import DecisionLog from './DecisionLog.vue';
import { roleLabels } from './format';
import VerdictDialog from './VerdictDialog.vue';

const props = defineProps<{
    assessment: StoredLogisticsAssessment;
    decision: HumanDecision | null;
    actionRoles: IntegrationActionRoles;
    demoShipments: IntegrationDemoShipments;
}>();

const page = usePage();
const role = computed(() => page.props.auth.user.role);
const recommended = computed(
    () => props.assessment.result.recommendation.action,
);
const options = computed(() =>
    integrationDecisionOptions(props.assessment, props.actionRoles),
);
const alternatives = computed(() =>
    options.value.filter((option) => !option.recommended),
);
const approver = computed(() =>
    recommended.value ? props.actionRoles[recommended.value] : null,
);
const canApprove = computed(
    () =>
        role.value === approver.value &&
        options.value.some((option) => option.recommended),
);
const canReopen = computed(
    () =>
        props.decision?.role === role.value &&
        isNamedIntegrationDemo(props.assessment, props.demoShipments),
);

const dialog = reactive({
    open: false,
    verdict: 'APPROVE' as 'APPROVE' | 'OVERRIDE',
    action:
        props.assessment.result.recommendation.action ??
        ('BUFFER' as ActionKey),
});
const form = useForm({
    assessment_id: props.assessment.assessment_id,
    input_sha256: props.assessment.input_sha256,
    model_version: props.assessment.model_version,
    scenario: props.assessment.scenario,
    external_shipment_id: props.assessment.result.shipment_id,
    recommended_action: props.assessment.result.recommendation.action,
    verdict: 'APPROVE' as 'APPROVE' | 'OVERRIDE',
    selected_action: props.assessment.result.recommendation
        .action as ActionKey | null,
    reason: '',
});
const formError = computed(() => Object.values(form.errors)[0]);

function openApprove(): void {
    if (!recommended.value || !canApprove.value) return;
    form.clearErrors();
    Object.assign(dialog, {
        open: true,
        verdict: 'APPROVE',
        action: recommended.value,
    });
}

function openOverride(): void {
    const option =
        alternatives.value.find((item) => item.requiredRole === role.value) ??
        alternatives.value[0];
    if (!option) return;
    form.clearErrors();
    Object.assign(dialog, {
        open: true,
        verdict: 'OVERRIDE',
        action: option.action,
    });
}

function record({
    action,
    reason,
}: {
    action: ActionKey;
    reason: string;
}): void {
    form.verdict = dialog.verdict;
    form.selected_action = action;
    form.reason = reason;
    form.submit(
        IntegrationDecisionController.store(props.assessment.assessment_id),
        {
            preserveScroll: true,
            onSuccess: () => {
                dialog.open = false;
            },
        },
    );
}

function reopen(): void {
    form.clearErrors();
    form.submit(
        IntegrationDecisionController.destroy(props.assessment.assessment_id),
        { preserveScroll: true },
    );
}
</script>

<template>
    <section
        aria-label="Operator decision"
        class="mt-3 border-t border-border pt-3"
    >
        <h3 class="text-sm font-semibold">Operator decision</h3>
        <template v-if="decision">
            <p class="mt-1 text-sm font-semibold" role="status">
                Decision recorded · {{ decision.action }}
            </p>
            <p class="mt-1 text-xs text-muted-foreground">
                {{ decision.verdict === 'APPROVE' ? 'Approved' : 'Overridden' }}
                by {{ decision.by }} · {{ roleLabels[decision.role] }}
            </p>
            <time
                :datetime="decision.decidedAt"
                class="mt-1 block text-xs text-muted-foreground"
            >
                {{ formatBaselTime(decision.decidedAt) }}
            </time>
            <div class="mt-2 flex flex-wrap items-start gap-3">
                <details class="min-w-0 flex-1 text-xs">
                    <summary class="cursor-pointer font-medium">
                        View decision log
                    </summary>
                    <DecisionLog
                        :entries="[decision]"
                        timezone="Europe/Zurich"
                    />
                </details>
                <button
                    v-if="canReopen"
                    type="button"
                    class="text-xs text-muted-foreground underline underline-offset-2"
                    :disabled="form.processing"
                    @click="reopen"
                >
                    Reopen demo decision
                </button>
            </div>
        </template>
        <template v-else-if="recommended">
            <div class="mt-2 flex flex-wrap gap-2">
                <Button
                    :disabled="!canApprove || form.processing"
                    @click="openApprove"
                >
                    Approve {{ recommended }}
                </Button>
                <Button
                    variant="outline"
                    :disabled="!alternatives.length || form.processing"
                    @click="openOverride"
                >
                    Override recommendation
                </Button>
            </div>
            <p class="mt-2 text-xs text-muted-foreground">
                <template v-if="approver && role !== approver"
                    >Needs {{ roleLabels[approver] }} approval.
                </template>
                Reason required · human decision recorded separately.
            </p>
        </template>
        <p v-else class="mt-2 text-xs text-muted-foreground">
            No actionable recommendation. Reload after reassessment.
        </p>
        <p
            v-if="formError && !dialog.open"
            role="alert"
            class="mt-2 text-sm text-destructive"
        >
            {{ formError }}
        </p>

        <VerdictDialog
            v-model:open="dialog.open"
            :verdict="dialog.verdict"
            :action="dialog.action"
            :options="options"
            :acting-as="role"
            :error="formError"
            :processing="form.processing"
            @confirm="record"
        />
    </section>
</template>
