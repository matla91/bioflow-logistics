<?php

declare(strict_types=1);

namespace App\Actions\Shipments;

use App\Data\ShipmentListItemData;
use App\Models\Shipment;
use Illuminate\Database\Eloquent\Builder;
use Illuminate\Support\Collection;

final class ListShipments
{
    /**
     * Open shipments soonest first, and decided shipments newest first.
     *
     * @return array{upcoming: Collection<int, ShipmentListItemData>, history: Collection<int, ShipmentListItemData>}
     */
    public function handle(): array
    {
        return [
            'upcoming' => $this->items(Shipment::query()->open()->oldest('charge_at')),
            'history' => $this->items(Shipment::query()->closed()->latest('charge_at')),
        ];
    }

    /**
     * @param  Builder<Shipment>  $query
     * @return Collection<int, ShipmentListItemData>
     */
    private function items(Builder $query): Collection
    {
        return $query
            ->with(['latestAssessment', 'decision.user'])
            ->get()
            ->map(ShipmentListItemData::fromModel(...));
    }
}
