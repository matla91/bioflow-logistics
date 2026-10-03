<?php

declare(strict_types=1);

namespace Database\Factories;

use App\Models\Shipment;
use App\Models\ShipmentObservation;
use Illuminate\Database\Eloquent\Factories\Factory;

/**
 * @extends Factory<ShipmentObservation>
 */
final class ShipmentObservationFactory extends Factory
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
            'observed_at' => now(),
            'segment' => 'barge',
            'route_progress' => 0.5,
            'refrigerated' => true,
            'product_temp_c' => fake()->randomFloat(2, 4, 6),
            'ambient_c' => fake()->randomFloat(2, 5, 25),
            'river_level_cm' => fake()->randomFloat(1, 80, 160),
            'excursion_min' => 0,
            'budget_used' => 0,
        ];
    }
}
