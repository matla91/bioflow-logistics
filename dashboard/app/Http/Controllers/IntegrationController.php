<?php

declare(strict_types=1);

namespace App\Http\Controllers;

use Illuminate\Http\Client\ConnectionException;
use Illuminate\Http\Client\RequestException;
use Illuminate\Support\Facades\Http;
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
}
