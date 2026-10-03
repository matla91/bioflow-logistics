<?php

declare(strict_types=1);

namespace Database\Factories;

use App\Enums\ShipmentStatus;
use App\Models\Shipment;
use Illuminate\Database\Eloquent\Factories\Factory;

/**
 * @extends Factory<Shipment>
 */
final class ShipmentFactory extends Factory
{
    /**
     * Define the model's default state.
     *
     * @return array<string, mixed>
     */
    public function definition(): array
    {
        $chargeAt = now()->addDays(fake()->numberBetween(1, 5))->setTime(6, 0);

        return [
            'lot' => 'SIM-'.fake()->unique()->numerify('##-####'),
            'simulated' => true,
            'material' => '2–8 °C pharma intermediate',
            'origin' => 'Shanghai',
            'reactor' => 'R2',
            'departed_at' => $chargeAt->copy()->subDays(40),
            'charge_at' => $chargeAt,
            'status' => ShipmentStatus::InTransit,
            'current_segment' => 'barge',
            'route_progress' => 0.5,
        ];
    }

    /**
     * Indicate that the shipment has a recorded decision.
     */
    public function closed(): static
    {
        return $this->state(fn (array $attributes): array => [
            'status' => ShipmentStatus::Closed,
            'charge_at' => now()->subDays(fake()->numberBetween(1, 20))->setTime(6, 0),
            'current_segment' => 'dock',
            'route_progress' => 1,
        ]);
    }
}
