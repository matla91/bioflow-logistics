<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { Button } from '@/components/ui/button';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog';
import type { ActionKey, ActionOption } from '@/types/console';
import { actionLabels } from './format';

const props = defineProps<{
    open: boolean;
    verdict: 'APPROVE' | 'OVERRIDE';
    action: ActionKey;
    options: ActionOption[];
    error?: string;
    processing?: boolean;
}>();

const emit = defineEmits<{
    'update:open': [value: boolean];
    confirm: [payload: { action: ActionKey; reason: string }];
}>();

const reason = ref('');
const chosen = ref<ActionKey>(props.action);

watch(
    () => props.open,
    (open) => {
        if (open) {
            reason.value = '';
            chosen.value = props.action;
        }
    },
);

const alternatives = computed(() =>
    props.options.filter((o) => !o.recommended),
);

const valid = computed(() => reason.value.trim().length > 0);

function submit(): void {
    if (valid.value) {
        emit('confirm', { action: chosen.value, reason: reason.value.trim() });
    }
}
</script>

<template>
    <Dialog :open="open" @update:open="emit('update:open', $event)">
        <DialogContent>
            <DialogHeader>
                <DialogTitle>
                    {{
                        verdict === 'APPROVE'
                            ? `Approve ${actionLabels[action]}`
                            : 'Override the recommendation'
                    }}
                </DialogTitle>
                <DialogDescription>
                    Every decision is logged with your reason and a fingerprint
                    of the evidence shown.
                </DialogDescription>
            </DialogHeader>

            <div v-if="verdict === 'OVERRIDE'" class="flex flex-wrap gap-2">
                <button
                    v-for="option in alternatives"
                    :key="option.action"
                    type="button"
                    class="rounded-md border px-3 py-1.5 text-sm"
                    :class="
                        chosen === option.action
                            ? 'border-foreground bg-accent font-semibold'
                            : 'text-muted-foreground'
                    "
                    @click="chosen = option.action"
                >
                    {{ option.label }}
                </button>
            </div>

            <label class="flex flex-col gap-1.5 text-sm">
                <span class="font-medium">Reason (required)</span>
                <textarea
                    v-model="reason"
                    v-focus
                    rows="3"
                    class="rounded-md border bg-background px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
                    placeholder="Why are you making this call?"
                />
            </label>

            <p
                v-if="error"
                class="text-sm text-red-600 dark:text-red-400"
                role="alert"
            >
                {{ error }}
            </p>

            <DialogFooter>
                <Button variant="outline" @click="emit('update:open', false)"
                    >Cancel</Button
                >
                <Button :disabled="!valid || processing" @click="submit">
                    {{
                        verdict === 'APPROVE'
                            ? 'Approve'
                            : `Override with ${actionLabels[chosen]}`
                    }}
                </Button>
            </DialogFooter>
        </DialogContent>
    </Dialog>
</template>
