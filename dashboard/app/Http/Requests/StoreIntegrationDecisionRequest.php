<?php

declare(strict_types=1);

namespace App\Http\Requests;

use App\Data\IntegrationDecisionInputData;
use App\Enums\ShipmentAction;
use App\Enums\Verdict;
use Illuminate\Contracts\Validation\ValidationRule;
use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;

final class StoreIntegrationDecisionRequest extends FormRequest
{
    /** @return array<string, ValidationRule|array<mixed>|string> */
    public function rules(): array
    {
        return [
            'assessment_id' => ['required', 'string', 'regex:/^[0-9a-f]{64}$/'],
            'input_sha256' => ['required', 'string', 'regex:/^[0-9a-f]{64}$/'],
            'model_version' => ['required', 'string', 'max:255'],
            'scenario' => ['required', Rule::in(['normal', 'disruption', 'severe'])],
            'external_shipment_id' => ['required', 'string', 'max:255'],
            'recommended_action' => ['required', Rule::enum(ShipmentAction::class)],
            'verdict' => ['required', Rule::enum(Verdict::class)],
            'selected_action' => ['required', Rule::enum(ShipmentAction::class)],
            'reason' => ['required', 'string', 'max:1000'],
        ];
    }

    public function toData(): IntegrationDecisionInputData
    {
        return new IntegrationDecisionInputData(
            identity: $this->safe()->only([
                'assessment_id', 'input_sha256', 'model_version', 'scenario', 'external_shipment_id', 'recommended_action',
            ]),
            verdict: $this->enum('verdict', Verdict::class) ?? Verdict::Approve,
            selectedAction: $this->enum('selected_action', ShipmentAction::class) ?? ShipmentAction::Buffer,
            reason: $this->string('reason')->trim()->toString(),
        );
    }
}
