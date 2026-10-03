<?php

declare(strict_types=1);

namespace App\Models;

use App\Enums\ShipmentStatus;
use Carbon\CarbonInterface;
use Database\Factories\ShipmentFactory;
use Illuminate\Database\Eloquent\Attributes\Scope;
use Illuminate\Database\Eloquent\Builder;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\HasMany;
use Illuminate\Database\Eloquent\Relations\HasOne;

/**
 * @property-read int $id
 * @property string $lot
 * @property ?string $external_ref
 * @property ?string $scenario
 * @property bool $simulated
 * @property string $material
 * @property string $origin
 * @property string $reactor
 * @property string $timezone
 * @property CarbonInterface $departed_at
 * @property CarbonInterface $charge_at
 * @property ?CarbonInterface $eta
 * @property ?CarbonInterface $arrived_at
 * @property ShipmentStatus $status
 * @property string $current_segment
 * @property float $route_progress
 * @property-read ?Assessment $latestAssessment
 * @property-read ?Decision $decision
 * @property-read CarbonInterface $created_at
 * @property-read CarbonInterface $updated_at
 */
final class Shipment extends Model
{
    /** @use HasFactory<ShipmentFactory> */
    use HasFactory;

    /**
     * @return HasMany<ShipmentObservation, $this>
     */
    public function observations(): HasMany
    {
        return $this->hasMany(ShipmentObservation::class)->orderBy('observed_at');
    }

    /**
     * @return HasMany<Assessment, $this>
     */
    public function assessments(): HasMany
    {
        return $this->hasMany(Assessment::class);
    }

    /**
     * @return HasOne<Assessment, $this>
     */
    public function latestAssessment(): HasOne
    {
        return $this->hasOne(Assessment::class)->latestOfMany('assessed_at');
    }

    /**
     * @return HasMany<Decision, $this>
     */
    public function decisions(): HasMany
    {
        return $this->hasMany(Decision::class)->latest('decided_at');
    }

    /**
     * @return HasOne<Decision, $this>
     */
    public function decision(): HasOne
    {
        return $this->hasOne(Decision::class)->latestOfMany('decided_at');
    }

    /**
     * Shipments still waiting for an operator decision.
     *
     * @param  Builder<self>  $query
     */
    #[Scope]
    protected function open(Builder $query): void
    {
        $query->where('status', '!=', ShipmentStatus::Closed);
    }

    /**
     * Shipments with a recorded decision.
     *
     * @param  Builder<self>  $query
     */
    #[Scope]
    protected function closed(Builder $query): void
    {
        $query->where('status', ShipmentStatus::Closed);
    }

    /**
     * @return array<string, string>
     */
    protected function casts(): array
    {
        return [
            'simulated' => 'boolean',
            'departed_at' => 'datetime',
            'charge_at' => 'datetime',
            'eta' => 'datetime',
            'arrived_at' => 'datetime',
            'status' => ShipmentStatus::class,
            'route_progress' => 'float',
        ];
    }
}
