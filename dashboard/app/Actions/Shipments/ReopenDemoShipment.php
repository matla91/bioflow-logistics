<?php

declare(strict_types=1);

namespace App\Actions\Shipments;

use App\Enums\ShipmentStatus;
use App\Exceptions\DecisionNotAllowed;
use App\Models\Shipment;
use Illuminate\Support\Facades\DB;

final class ReopenDemoShipment
{
    /**
     * Remove the decisions on a demo scene so it can be rehearsed again.
     *
     * @throws DecisionNotAllowed
     */
    public function handle(Shipment $shipment): void
    {
        if ($shipment->scenario === null) {
            throw new DecisionNotAllowed('Only demo scenes can be reopened.');
        }

        DB::transaction(function () use ($shipment): void {
            $shipment->decisions()->delete();
            $shipment->update([
                'status' => $shipment->arrived_at === null ? ShipmentStatus::Suspended : ShipmentStatus::Arrived,
            ]);
        });
    }
}
