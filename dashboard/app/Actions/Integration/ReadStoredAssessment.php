<?php

declare(strict_types=1);

namespace App\Actions\Integration;

use App\Data\IntegrationAssessmentData;
use App\Exceptions\DecisionNotAllowed;
use Illuminate\Http\Client\ConnectionException;
use Illuminate\Http\Client\RequestException;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Validator;
use Illuminate\Validation\Rule;

final class ReadStoredAssessment
{
    /**
     * Fetch fresh evidence by its external hash. Never use browser evidence as truth.
     *
     * @throws DecisionNotAllowed
     */
    public function handle(string $assessmentId): IntegrationAssessmentData
    {
        try {
            $base = mb_rtrim((string) config('integration.url'), '/');
            $payload = Http::acceptJson()->timeout(5)
                ->get($base.'/api/integration/assessments/'.rawurlencode($assessmentId))->throw()->json();
        } catch (ConnectionException|RequestException) {
            throw new DecisionNotAllowed('The stored assessment is unavailable. Reload before deciding.');
        }

        if (! is_array($payload) || $this->validator($payload)->fails() || $payload['assessment_id'] !== $assessmentId) {
            throw new DecisionNotAllowed('The stored assessment is invalid or has changed. Reload before deciding.');
        }

        $result = $payload['result'];
        if ($result['shipment_id'] !== $result['simulated_shipment']['shipment_id']) {
            throw new DecisionNotAllowed('The stored shipment identity has changed. Reload before deciding.');
        }

        return new IntegrationAssessmentData(
            identity: [
                'assessment_id' => $payload['assessment_id'],
                'input_sha256' => $payload['input_sha256'],
                'model_version' => $payload['model_version'],
                'scenario' => $payload['scenario'],
                'external_shipment_id' => $result['shipment_id'],
                'recommended_action' => $result['recommendation']['action'],
            ],
            actions: $result['actions'],
            snapshot: $payload,
            demo: ($result['simulated_shipment']['simulated'] ?? false) === true
                && config('integration.demo_shipments.'.$payload['scenario']) === $result['shipment_id'],
        );
    }

    /** @param array<string, mixed> $payload */
    private function validator(array $payload): \Illuminate\Contracts\Validation\Validator
    {
        // These are the existing Python logistics actions, without QA disposition.
        $actions = ['BUFFER', 'EXPEDITE', 'REROUTE'];

        return Validator::make($payload, [
            'assessment_id' => ['required', 'string', 'regex:/^[0-9a-f]{64}$/'],
            'input_sha256' => ['required', 'string', 'regex:/^[0-9a-f]{64}$/'],
            'model_version' => ['required', 'string', 'max:255'],
            'scenario' => ['required', Rule::in(['normal', 'disruption', 'severe'])],
            'result.shipment_id' => ['required', 'string', 'max:255'],
            'result.simulated_shipment.shipment_id' => ['required', 'string', 'max:255'],
            'result.simulated_shipment.simulated' => ['sometimes', 'boolean'],
            'result.recommendation.action' => ['present', 'nullable', Rule::in($actions)],
            'result.actions' => ['required', 'array', 'min:1'],
            'result.actions.*.action' => ['required', 'distinct:strict', Rule::in($actions)],
            'result.actions.*.eligible' => ['required', 'boolean'],
        ]);
    }
}
