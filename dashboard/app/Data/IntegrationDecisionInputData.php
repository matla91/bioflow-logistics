<?php

declare(strict_types=1);

namespace App\Data;

use App\Enums\ShipmentAction;
use App\Enums\Verdict;
use Spatie\LaravelData\Data;

final class IntegrationDecisionInputData extends Data
{
    /** @param array<string, mixed> $identity */
    public function __construct(
        public array $identity,
        public Verdict $verdict,
        public ShipmentAction $selectedAction,
        public string $reason,
    ) {}
}
