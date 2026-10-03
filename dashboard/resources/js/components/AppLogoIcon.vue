<script setup lang="ts">
import type { HTMLAttributes } from 'vue';

defineOptions({ inheritAttrs: false });
defineProps<{ className?: HTMLAttributes['class'] }>();
</script>

<template>
    <img
        src="/brand/smartflow-mark.png"
        alt="Smartflow"
        width="40"
        height="40"
        :class="className"
        v-bind="$attrs"
    />
</template>
