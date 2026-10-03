<?php

declare(strict_types=1);

namespace App\Models;

use App\Data\ActionOptionData;
use App\Data\AnswersData;
use App\Data\BriefingData;
use App\Data\ReasonData;
use App\Enums\ShipmentAction;
use App\Enums\UserRole;
use Carbon\CarbonInterface;
use Database\Factories\AssessmentFactory;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasOne;
use Spatie\LaravelData\DataCollection;

/**
 * An ML prediction for a shipment plus the rule-based recommendation derived from it.
 *
 * @property-read int $id
 * @property int $shipment_id
 * @property CarbonInterface $assessed_at
 * @property string $model
 * @property float $p_miss_slot
 * @property float $p_excursion
 * @property float $budget_used
 * @property ?CarbonInterface $eta_p50
 * @property ?CarbonInterface $eta_p90
 * @property ShipmentAction $recommended_action
 * @property UserRole $approver_role
 * @property AnswersData $answers
 * @property DataCollection<int, ActionOptionData> $options
 * @property DataCollection<int, ReasonData> $reasons
 * @property list<string> $would_change_if
 * @property ?array<string, array<string, mixed>> $signals
 * @property ?BriefingData $briefing
 * @property string $snapshot_sha256
 * @property-read Shipment $shipment
 * @property-read CarbonInterface $created_at
 * @property-read CarbonInterface $updated_at
 */
final class Assessment extends Model
{
    /** @use HasFactory<AssessmentFactory> */
    use HasFactory;

    /**
     * @return BelongsTo<Shipment, $this>
     */
    public function shipment(): BelongsTo
    {
        return $this->belongsTo(Shipment::class);
    }

    /**
     * @return HasOne<Decision, $this>
     */
    public function decision(): HasOne
    {
        return $this->hasOne(Decision::class);
    }

    /**
     * @return array<string, string>
     */
    protected function casts(): array
    {
        return [
            'assessed_at' => 'datetime',
            'p_miss_slot' => 'float',
            'p_excursion' => 'float',
            'budget_used' => 'float',
            'eta_p50' => 'datetime',
            'eta_p90' => 'datetime',
            'recommended_action' => ShipmentAction::class,
            'approver_role' => UserRole::class,
            'answers' => AnswersData::class,
            'options' => DataCollection::class.':'.ActionOptionData::class,
            'reasons' => DataCollection::class.':'.ReasonData::class,
            'would_change_if' => 'array',
            'signals' => 'array',
            'briefing' => BriefingData::class,
        ];
    }
}
