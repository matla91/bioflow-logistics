<?php

declare(strict_types=1);

namespace App\Data;

use App\Enums\ShipmentAction;
use App\Enums\ShipmentStatus;
use App\Enums\UserRole;
use App\Models\Shipment;
use Spatie\LaravelData\Data;

final class ShipmentListItemData extends Data
{
    public function __construct(
        public int $id,
        public string $lot,
        public ?string $scenario,
        public string $reactor,
        public string $chargeAt,
        public string $timezone,
        public ShipmentStatus $status,
        public string $currentSegment,
        public float $routeProgress,
        public ?ShipmentAction $recommendedAction,
        public ?UserRole $approverRole,
        public ?AnswersData $answers,
        public ?ShipmentDecisionData $decision,
    ) {}

    public static function fromModel(Shipment $shipment): self
    {
        $assessment = $shipment->latestAssessment;

        return new self(
            id: $shipment->id,
            lot: $shipment->lot,
            scenario: $shipment->scenario,
            reactor: $shipment->reactor,
            chargeAt: $shipment->charge_at->toIso8601String(),
            timezone: $shipment->timezone,
            status: $shipment->status,
            currentSegment: $shipment->current_segment,
            routeProgress: $shipment->route_progress,
            recommendedAction: $assessment?->recommended_action,
            approverRole: $assessment?->approver_role,
            answers: $assessment?->answers,
            decision: $shipment->decision === null ? null : ShipmentDecisionData::fromModel($shipment->decision),
        );
    }
}
