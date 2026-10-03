<?php

declare(strict_types=1);

namespace Database\Factories;

use App\Enums\EvidenceKind;
use App\Enums\ShipmentAction;
use App\Enums\UserRole;
use App\Models\Assessment;
use App\Models\Shipment;
use Illuminate\Database\Eloquent\Factories\Factory;

/**
 * @extends Factory<Assessment>
 */
final class AssessmentFactory extends Factory
{
    /**
     * Define the model's default state.
     *
     * @return array<string, mixed>
     */
    public function definition(): array
    {
        return [
            'shipment_id' => Shipment::factory(),
            'assessed_at' => now(),
            'model' => 'factory',
            'p_miss_slot' => 0.02,
            'p_excursion' => 0.01,
            'budget_used' => 0,
            'recommended_action' => ShipmentAction::RunAsPlanned,
            'approver_role' => UserRole::Operator,
            'answers' => [
                'arrival' => ['question' => 'Will it be here?', 'verdict' => 'yes', 'detail' => 'On schedule'],
                'quality' => ['question' => 'Still good to use?', 'verdict' => 'yes', 'detail' => 'Within budget'],
            ],
            'options' => array_map(fn (ShipmentAction $action): array => [
                'action' => $action->value,
                'label' => $action->label(),
                'pMissSlot' => 0.02,
                'expDelayMin' => 0,
                'pExcursion' => 0.01,
                'stockAfter' => 2,
                'recommended' => $action === ShipmentAction::RunAsPlanned,
                'note' => '',
            ], ShipmentAction::cases()),
            'reasons' => [[
                'n' => 1,
                'text' => '2% chance of missing the slot',
                'kind' => EvidenceKind::Simulated->value,
                'source' => 'factory',
                'at' => now()->toIso8601String(),
            ]],
            'would_change_if' => [],
            'snapshot_sha256' => hash('sha256', fake()->uuid()),
        ];
    }
}
