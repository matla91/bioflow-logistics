<?php

declare(strict_types=1);

namespace App\Data;

use App\Enums\ShipmentAction;
use Spatie\LaravelData\Data;

/**
 * Validated decision boundary for the unchanged StoredLogisticsAssessment contract.
 */
final class IntegrationAssessmentData extends Data
{
    /**
     * @param  array{assessment_id: string, input_sha256: string, model_version: string, scenario: string, external_shipment_id: string, recommended_action: ?string}  $identity
     * @param  list<array{action: string, eligible: bool}>  $actions
     * @param  array<string, mixed>  $snapshot
     */
    public function __construct(
        public array $identity,
        public array $actions,
        public array $snapshot,
        public bool $demo,
    ) {}

    public function isEligible(ShipmentAction $action): bool
    {
        return collect($this->actions)->contains(
            fn (array $option): bool => $option['action'] === $action->value && $option['eligible'] === true,
        );
    }

    /** @param array<string, mixed> $identity */
    public function matches(array $identity): bool
    {
        foreach ($this->identity as $key => $value) {
            if (! array_key_exists($key, $identity) || $identity[$key] !== $value) {
                return false;
            }
        }

        return true;
    }
}
