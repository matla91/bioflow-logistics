<?php

declare(strict_types=1);

namespace App\Http\Controllers;

use Illuminate\Http\Client\ConnectionException;
use Illuminate\Http\Client\RequestException;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Str;
use Inertia\Inertia;
use Inertia\Response;

final class IntegrationController extends Controller
{
    public function __invoke(): Response
    {
        try {
            $base = mb_rtrim((string) config('integration.url'), '/');
            $assessments = Http::acceptJson()->timeout(5)
                ->get($base.'/api/integration/assessments')->throw()->json();
            $operations = Http::acceptJson()->timeout(5)
                ->get($base.'/api/integration/operations')->throw()->json();

            return Inertia::render('Integration', [
                'assessments' => $assessments,
                'operations' => $operations,
                'unavailable' => false,
            ]);
        } catch (ConnectionException|RequestException) {
            return Inertia::render('Integration', [
                'assessments' => [],
                'operations' => [],
                'unavailable' => true,
            ]);
        }
    }

    public function batches(Request $request): Response
    {
        /** @var array{batch_id?: string|null} $selection */
        $selection = $request->validate(['batch_id' => ['nullable', 'string', 'max:255']]);
        $selectedBatchId = $selection['batch_id'] ?? null;
        $props = [
            'assessment' => null,
            'batches' => [],
            'selectedBatchId' => $selectedBatchId,
            'unavailable' => false,
            'missing' => false,
        ];

        try {
            $base = mb_rtrim((string) config('integration.url'), '/');
            /** @var list<array{batch_id: string, dataset_id: string}> $records */
            $records = Http::acceptJson()->timeout(5)
                ->get($base.'/api/integration/batch-assessments')->throw()->json();
            $batches = collect($records)->unique('batch_id')->sortBy('batch_id')->values();
            $props['batches'] = $batches->map(fn (array $record): array => [
                'id' => $record['batch_id'],
                'label' => 'Batch '.Str::afterLast($record['batch_id'], '-'),
            ])->all();
            $selectedBatchId ??= $batches->first()['batch_id'] ?? null;
            $props['selectedBatchId'] = $selectedBatchId;
            $selected = $batches->firstWhere('batch_id', $selectedBatchId);

            if ($selected !== null) {
                $response = Http::acceptJson()->timeout(5)->get(
                    $base.'/api/integration/batches/'.rawurlencode($selected['batch_id']).'/assessments/latest',
                    ['dataset_id' => $selected['dataset_id']],
                );
                if ($response->notFound()) {
                    $props['missing'] = true;
                } else {
                    $props['assessment'] = $response->throw()->json();
                }
            } else {
                $props['missing'] = $selectedBatchId !== null;
            }
        } catch (ConnectionException|RequestException) {
            $props['unavailable'] = true;
        }

        return Inertia::render('BatchAssessment', $props);
    }
}
