<?php

declare(strict_types=1);

namespace App\Http\Requests;

use App\Data\DecisionInputData;
use App\Enums\ShipmentAction;
use App\Enums\Verdict;
use Illuminate\Contracts\Validation\ValidationRule;
use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;

final class StoreDecisionRequest extends FormRequest
{
    /**
     * @return array<string, ValidationRule|array<mixed>|string>
     */
    public function rules(): array
    {
        return [
            'assessment_id' => ['required', 'integer'],
            'verdict' => ['required', Rule::enum(Verdict::class)],
            'action' => ['required', Rule::enum(ShipmentAction::class)],
            'reason' => ['required', 'string', 'max:1000'],
        ];
    }

    public function toData(): DecisionInputData
    {
        return new DecisionInputData(
            assessmentId: $this->integer('assessment_id'),
            verdict: $this->enum('verdict', Verdict::class) ?? Verdict::Approve,
            action: $this->enum('action', ShipmentAction::class) ?? ShipmentAction::RunAsPlanned,
            reason: $this->string('reason')->trim()->toString(),
        );
    }
}
