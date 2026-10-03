<?php

declare(strict_types=1);

namespace App\Models;

use App\Enums\ShipmentAction;
use App\Enums\UserRole;
use App\Enums\Verdict;
use Carbon\CarbonInterface;
use Database\Factories\DecisionFactory;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

/**
 * A person's approval or override of an assessment's recommendation.
 *
 * @property-read int $id
 * @property int $shipment_id
 * @property int $assessment_id
 * @property int $user_id
 * @property UserRole $role
 * @property Verdict $verdict
 * @property ShipmentAction $action
 * @property string $reason
 * @property string $snapshot_sha256
 * @property CarbonInterface $decided_at
 * @property-read User $user
 * @property-read Shipment $shipment
 * @property-read Assessment $assessment
 * @property-read CarbonInterface $created_at
 * @property-read CarbonInterface $updated_at
 */
final class Decision extends Model
{
    /** @use HasFactory<DecisionFactory> */
    use HasFactory;

    /**
     * @return BelongsTo<Shipment, $this>
     */
    public function shipment(): BelongsTo
    {
        return $this->belongsTo(Shipment::class);
    }

    /**
     * @return BelongsTo<Assessment, $this>
     */
    public function assessment(): BelongsTo
    {
        return $this->belongsTo(Assessment::class);
    }

    /**
     * @return BelongsTo<User, $this>
     */
    public function user(): BelongsTo
    {
        return $this->belongsTo(User::class);
    }

    /**
     * @return array<string, string>
     */
    protected function casts(): array
    {
        return [
            'role' => UserRole::class,
            'verdict' => Verdict::class,
            'action' => ShipmentAction::class,
            'decided_at' => 'datetime',
        ];
    }
}
