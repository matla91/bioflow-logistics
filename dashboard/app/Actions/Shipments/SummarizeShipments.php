<?php

declare(strict_types=1);

namespace App\Actions\Shipments;

use App\Data\ShipmentListItemData;
use App\Data\ShipmentOverviewData;
use App\Enums\ShipmentAction;
use App\Enums\ShipmentStatus;
use App\Enums\Verdict;
use App\Models\Shipment;
use App\Models\User;

final class SummarizeShipments
{
    private const int RECENT_DAYS = 30;

    private const int NEXT_CHARGES = 5;

    public function handle(User $user): ShipmentOverviewData
    {
        $open = Shipment::query()->open()->with(['latestAssessment', 'decision.user'])->oldest('charge_at')->get();
        $recent = Shipment::query()
            ->closed()
            ->where('charge_at', '>=', now()->subDays(self::RECENT_DAYS))
            ->with(['latestAssessment', 'decision'])
            ->get();

        $needsYou = $open->filter(fn (Shipment $s): bool => $s->latestAssessment?->approver_role === $user->role);
        $atRisk = $open->filter(fn (Shipment $s): bool => $s->latestAssessment !== null
            && ($s->latestAssessment->answers->arrival->verdict !== 'yes' || $s->latestAssessment->answers->quality->verdict !== 'yes'));

        $decisionsByAction = [];
        foreach (ShipmentAction::cases() as $action) {
            $decisionsByAction[$action->value] = $recent->filter(fn (Shipment $s): bool => $s->decision?->action === $action)->count();
        }

        return new ShipmentOverviewData(
            open: [
                'open' => $open->count(),
                'needsYou' => $needsYou->count(),
                'suspended' => $open->where('status', ShipmentStatus::Suspended)->count(),
                'atRisk' => $atRisk->count(),
            ],
            recent: [
                'days' => self::RECENT_DAYS,
                'decided' => $recent->count(),
                'overrides' => $recent->filter(fn (Shipment $s): bool => $s->decision?->verdict === Verdict::Override)->count(),
                'onTime' => $recent->filter(fn (Shipment $s): bool => $s->latestAssessment?->answers->arrival->verdict === 'yes')->count(),
                'withinBudget' => $recent->filter(fn (Shipment $s): bool => $s->latestAssessment?->answers->quality->verdict === 'yes')->count(),
            ],
            decisionsByAction: $decisionsByAction,
            needsYou: array_values($needsYou->map(ShipmentListItemData::fromModel(...))->all()),
            nextCharges: array_values($open->take(self::NEXT_CHARGES)->map(ShipmentListItemData::fromModel(...))->all()),
        );
    }
}
