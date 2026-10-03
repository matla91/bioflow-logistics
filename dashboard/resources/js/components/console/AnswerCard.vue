<script setup lang="ts">
import { computed } from 'vue';
import type { Answer } from '@/types/console';

const props = defineProps<{ answer: Answer }>();

const tone = computed(
    () =>
        ({
            yes: {
                word: 'YES',
                text: 'text-emerald-700 dark:text-emerald-400',
                ring: 'border-emerald-600/40',
            },
            no: {
                word: 'NO',
                text: 'text-red-700 dark:text-red-400',
                ring: 'border-red-600/50',
            },
            at_risk: {
                word: 'AT RISK',
                text: 'text-amber-700 dark:text-amber-400',
                ring: 'border-amber-500/50',
            },
        })[props.answer.verdict],
);
</script>

<template>
    <div class="rounded-xl border-2 bg-card p-4" :class="tone.ring">
        <div class="text-sm text-muted-foreground">{{ answer.question }}</div>
        <div
            class="text-4xl leading-tight font-bold tracking-tight"
            :class="tone.text"
        >
            {{ tone.word }}
        </div>
        <div class="mt-1 text-sm">{{ answer.detail }}</div>
    </div>
</template>
