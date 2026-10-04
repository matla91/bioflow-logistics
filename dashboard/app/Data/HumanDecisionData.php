<?php

declare(strict_types=1);

namespace App\Data;

use App\Enums\ShipmentAction;
use App\Enums\UserRole;
use App\Enums\Verdict;
use App\Models\Decision;
use App\Models\IntegrationDecision;
use Spatie\LaravelData\Data;

final class HumanDecisionData extends Data
{
    public function __construct(
        public Verdict $verdict,
        public ShipmentAction $action,
        public UserRole $role,
        public string $by,
        public string $reason,
        public string $decidedAt,
    ) {}

    public static function fromModel(Decision|IntegrationDecision $decision): self
    {
        return new self(
            verdict: $decision->verdict,
            action: $decision instanceof IntegrationDecision ? $decision->selected_action : $decision->action,
            role: $decision->role,
            by: $decision->user->name,
            reason: $decision->reason,
            decidedAt: $decision->decided_at->toIso8601String(),
        );
    }
}
