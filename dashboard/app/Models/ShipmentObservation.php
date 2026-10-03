<?php

declare(strict_types=1);

namespace App\Models;

use Carbon\CarbonInterface;
use Database\Factories\ShipmentObservationFactory;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

/**
 * @property-read int $id
 * @property int $shipment_id
 * @property CarbonInterface $observed_at
 * @property string $segment
 * @property float $route_progress
 * @property bool $refrigerated
 * @property float $product_temp_c
 * @property ?float $ambient_c
 * @property ?float $river_level_cm
 * @property float $excursion_min
 * @property float $budget_used
 */
final class ShipmentObservation extends Model
{
    /** @use HasFactory<ShipmentObservationFactory> */
    use HasFactory;

    public $timestamps = false;

    /**
     * @return BelongsTo<Shipment, $this>
     */
    public function shipment(): BelongsTo
    {
        return $this->belongsTo(Shipment::class);
    }

    /**
     * @return array<string, string>
     */
    protected function casts(): array
    {
        return [
            'observed_at' => 'datetime',
            'route_progress' => 'float',
            'refrigerated' => 'boolean',
            'product_temp_c' => 'float',
            'ambient_c' => 'float',
            'river_level_cm' => 'float',
            'excursion_min' => 'float',
            'budget_used' => 'float',
        ];
    }
}
