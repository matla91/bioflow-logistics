<?php

declare(strict_types=1);

namespace App\Data;

use App\Enums\ShipmentAction;
use App\Enums\Verdict;
use Spatie\LaravelData\Data;

final class DecisionInputData extends Data
{
    public function __construct(
        public int $assessmentId,
        public Verdict $verdict,
        public ShipmentAction $action,
        public string $reason,
    ) {}
}
