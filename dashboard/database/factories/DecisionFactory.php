<?php

declare(strict_types=1);

namespace Database\Factories;

use App\Enums\ShipmentAction;
use App\Enums\UserRole;
use App\Enums\Verdict;
use App\Models\Assessment;
use App\Models\Decision;
use App\Models\User;
use Illuminate\Database\Eloquent\Factories\Factory;

/**
 * @extends Factory<Decision>
 */
final class DecisionFactory extends Factory
{
    /**
     * Define the model's default state.
     *
     * @return array<string, mixed>
     */
    public function definition(): array
    {
        return [
            'assessment_id' => Assessment::factory(),
            'shipment_id' => fn (array $attributes): int => Assessment::query()->findOrFail($attributes['assessment_id'])->shipment_id,
            'user_id' => User::factory(),
            'role' => UserRole::Operator,
            'verdict' => Verdict::Approve,
            'action' => ShipmentAction::RunAsPlanned,
            'reason' => fake()->sentence(),
            'snapshot_sha256' => hash('sha256', fake()->uuid()),
            'decided_at' => now(),
        ];
    }
}
