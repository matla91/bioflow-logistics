<script setup lang="ts">
import { Head } from '@inertiajs/vue3';
import type {
    OperationalDataset,
    StoredLogisticsAssessment,
} from '@/types/integration';

defineProps<{
    assessments: StoredLogisticsAssessment[];
    operations: OperationalDataset[];
    unavailable: boolean;
}>();

defineOptions({
    layout: {
        breadcrumbs: [{ title: 'Logistics analysis', href: '/integration' }],
    },
});
const percent = (value: number) => `${(100 * value).toFixed(1)}%`;
</script>

<template>
    <Head title="Logistics analysis" />
    <div class="mx-auto flex w-full max-w-7xl flex-col gap-6 p-6">
        <h1 class="text-2xl font-bold">Logistics analysis</h1>
        <p v-if="unavailable" role="status">
            Stored analysis is currently unavailable. Try again shortly.
        </p>
        <p v-else-if="assessments.length === 0">
            No stored logistics assessments are available yet.
        </p>
        <section
            v-for="record in assessments"
            :key="record.assessment_id"
            class="rounded-xl border bg-card p-5"
        >
            <h2 class="text-lg font-semibold">
                {{ record.scenario }} ·
                {{
                    record.result.recommendation.action ?? 'No eligible action'
                }}
            </h2>
            <p class="text-sm text-muted-foreground">
                Scenario assessment at {{ record.result.as_of }} · Evidence
                confidence: {{ record.result.recommendation.confidence }}
            </p>
            <p class="my-3">{{ record.result.recommendation.reason }}</p>
            <div class="overflow-x-auto">
                <table class="w-full text-left text-sm">
                    <thead>
                        <tr>
                            <th>Action</th>
                            <th>Eligible</th>
                            <th>Production continuity</th>
                            <th>Arrival by deadline</th>
                            <th>Ambient exposure risk</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr
                            v-for="action in record.result.actions"
                            :key="action.action"
                        >
                            <td class="py-2">{{ action.action }}</td>
                            <td>{{ action.eligible ? 'Yes' : 'No' }}</td>
                            <td>
                                {{
                                    percent(
                                        action.production_continuity_probability,
                                    )
                                }}
                            </td>
                            <td>
                                {{
                                    percent(action.on_time_arrival_probability)
                                }}
                            </td>
                            <td>
                                {{
                                    percent(
                                        action.cold_chain_exposure_proxy_risk,
                                    )
                                }}
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
            <ul class="mt-3 list-disc pl-5 text-sm text-muted-foreground">
                <li v-for="limit in record.result.limitations" :key="limit">
                    {{ limit }}
                </li>
            </ul>
        </section>
        <section
            v-for="dataset in operations"
            :key="dataset.dataset_id"
            class="rounded-xl border bg-card p-5"
        >
            <h2 class="text-lg font-semibold">Simulated operations</h2>
            <p>
                {{ dataset.batches.length }} batches ·
                {{ dataset.shipments.length }} shipments ·
                {{ dataset.inventory.length }} inventory lots
            </p>
            <p class="text-sm text-muted-foreground">
                Reference time: {{ dataset.reference_at }}. These records are
                separate from the scenario assessments above.
            </p>
        </section>
    </div>
</template>
