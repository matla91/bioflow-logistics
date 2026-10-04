<?php

declare(strict_types=1);

namespace App\Models;

use App\Enums\ShipmentAction;
use App\Enums\UserRole;
use App\Enums\Verdict;
use Carbon\CarbonInterface;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

/**
 * A human decision on an immutable Python record, never a Laravel shipment.
 *
 * @property-read int $id
 * @property string $assessment_id
 * @property string $input_sha256
 * @property string $model_version
 * @property string $scenario
 * @property string $external_shipment_id
 * @property ShipmentAction $recommended_action
 * @property Verdict $verdict
 * @property ShipmentAction $selected_action
 * @property int $user_id
 * @property UserRole $role
 * @property string $reason
 * @property array<string, mixed> $assessment_snapshot
 * @property CarbonInterface $decided_at
 * @property-read User $user
 * @property-read CarbonInterface $created_at
 * @property-read CarbonInterface $updated_at
 */
final class IntegrationDecision extends Model
{
    /** @return BelongsTo<User, $this> */
    public function user(): BelongsTo
    {
        return $this->belongsTo(User::class);
    }

    /** @return array<string, string> */
    protected function casts(): array
    {
        return [
            'recommended_action' => ShipmentAction::class,
            'selected_action' => ShipmentAction::class,
            'verdict' => Verdict::class,
            'role' => UserRole::class,
            'assessment_snapshot' => 'array',
            'decided_at' => 'datetime',
        ];
    }
}
