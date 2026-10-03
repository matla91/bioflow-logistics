<?php

declare(strict_types=1);

namespace App\Data;

use App\Enums\ShipmentAction;
use App\Enums\UserRole;
use App\Enums\Verdict;
use App\Models\Decision;
use Spatie\LaravelData\Data;

final class ShipmentDecisionData extends Data
{
    public function __construct(
        public Verdict $verdict,
        public ShipmentAction $action,
        public UserRole $role,
        public string $by,
        public string $reason,
        public string $decidedAt,
    ) {}

    public static function fromModel(Decision $decision): self
    {
        return new self(
            verdict: $decision->verdict,
            action: $decision->action,
            role: $decision->role,
            by: $decision->user->name,
            reason: $decision->reason,
            decidedAt: $decision->decided_at->toIso8601String(),
        );
    }
}
